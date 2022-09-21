import json
import typing
from enum import Enum
from logging import getLogger
from types import NoneType
import random

from sqlalchemy import select, update, delete

from app.store.vk_api.dataclasses import Message, Update
from app.quiz.models import (
    Users,
    UsersModel,
    StatisticsModel,
    GameUser,
    GameUserModel,
    CurrentGame,
    CurrentGameModel,
    ChatModel,
)

if typing.TYPE_CHECKING:
    from app.web.app import Application


class MessageToSend(str, Enum):
    start_additions_member = "{first_name} {last_name} начал набор игроков!!!"
    cards_member = "{name}, карты: {cards}"
    member_makes_move = "[{domain_queue}|{full_name_queue}] делает ход"

    player_pass = "Игрок [{domain_queue}|{full_name_queue}] пассанул"
    cards_player = "Карты игрока [{domain_queue}|{full_name_queue}]: " "%0A{cards}"
    cards_diller = "Карты диллера: %0A{cards}"

    member_loss = "Игрок [{domain_queue}|{full_name_queue}] проиграл"

    new_cards_diller = "Новые карты диллера: %0A{cards}"
    new_cards_member = (
        "Новые карты игрока [{domain_queue}|{full_name_queue}]: " "%0A{cards}"
    )
    member_already_exists = "Этот игрок уже участвует"
    new_member = "[{domain}|{last_name} {first_name}] участвует"
    list_members = "Набор игроков окончен%0AУчастники: %0A{members}"
    end_game = "Конец игры"
    win = "[{domain_queue}|{full_name_queue}], вы выйграли"
    tie = "[{domain_queue}|{full_name_queue}], ничья"
    loss = "[{domain_queue}|{full_name_queue}], вы проиграли"


class Buttons(str, Enum):
    player_add_buttons = json.dumps(
        {
            "buttons": [
                [
                    {
                        "action": {
                            "type": "text",
                            "payload": json.dumps({"key": "I play"}),
                            "label": "I play",
                        }
                    }
                ],
                [
                    {
                        "action": {
                            "type": "text",
                            "payload": json.dumps({"key": "Finish recruiting players"}),
                            "label": "Finish recruiting players",
                        }
                    }
                ],
            ]
        }
    )
    game_process_buttons = json.dumps(
        {
            "buttons": [
                [
                    {
                        "action": {
                            "type": "text",
                            "payload": json.dumps({"key": "Another card"}),
                            "label": "Ещё карту",
                        }
                    }
                ],
                [
                    {
                        "action": {
                            "type": "text",
                            "payload": json.dumps({"key": "Pass"}),
                            "label": "Пас",
                        }
                    }
                ],
            ]
        }
    )


class State(int, Enum):
    GAME_OFF = 0
    PLAYER_ADD = 1
    CARD_DISTRIBUTION = 2
    START_GAME = 3


class MemberStatus(str, Enum):
    in_game = "in_game"
    lost = "lost"
    pass_ = "pass"


class BotManager:
    def __init__(self, app: "Application"):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")
        self.table: dict = {}
        self.updates: list[Update] = []
        self.user_id: int = 0
        self.peer_id: int = 0
        self.chat_id: int = 0
        self.event_id: str = ""
        self.type: str = ""
        self.card_deck: dict = {}
        self.received_message: str = ""
        self.domain: str = ""
        self.first_name: str = ""
        self.last_name: str = ""
        self.send_answer_message: str = ""
        self.message_to_send: str = ""
        self.members: dict = {}
        self.queue: int = 0
        self.host: str = ""
        self.state: int = 0
        self.number_members_in_game: int = 0
        self.queue_domain = ""
        self.full_name_queue = ""
        self.current_game_id = 0
        self.generate_card_deck()

    async def handle_updates(self, updates: list[Update]):
        if isinstance(updates, NoneType) or not updates:
            return

        self.updates = updates
        user = await self.app.store.vk_api.user(updates[0].object.user_id)
        user = user.get("response")[0]
        self.first_name = user.get("first_name")
        self.last_name = user.get("last_name")
        self.domain = user.get("domain")
        await self.add_users_model(self.last_name, self.first_name, self.domain)
        message_body = updates[0].object.body.get("message")
        if updates[0].object.body.get("message"):
            self.received_message = message_body.get("text")
            self.peer_id = message_body.get("peer_id")
            self.event_id = message_body.get("event_id")
        async with self.app.database.session.begin() as session:
            raw_current_game = await session.execute(select(CurrentGameModel))
            fetch = raw_current_game.fetchall()
            if fetch:
                current_game = CurrentGame(
                    **json.loads(str(fetch[0][-1]))["CurrentGame"]
                )
                if current_game.host == self.domain and self.received_message == "/end":
                    await self.close_game()
                    message_to_send = MessageToSend.end_game.value
                    await self.send_message(
                        message_text=message_to_send,
                        buttons=Buttons.game_process_buttons,
                    )
                    return
        self.type = updates[0].type
        self.user_id = updates[0].object.user_id
        chat_id = self.peer_id - 2000000000
        await self.add_current_game_model(chat_id)
        await self.state_machine()

    async def state_machine(self):
        if self.state == State.GAME_OFF:
            await self._start_additions_member()
        elif self.state == State.PLAYER_ADD:
            await self._additions_member()
        elif self.state == State.CARD_DISTRIBUTION:
            await self._start_distribution_card()
        elif self.state == State.START_GAME:
            await self._start_game()

    async def _start_additions_member(self):
        if self.received_message == "/start":
            message_to_send = MessageToSend.start_additions_member.format(
                first_name=self.first_name, last_name=self.last_name
            )
            await self.send_message(
                message_text=message_to_send, buttons=Buttons.player_add_buttons
            )
            async with self.app.database.session.begin() as session:
                await session.execute(
                    update(CurrentGameModel)
                    .where(CurrentGameModel.id == self.current_game_id)
                    .values(state=1, host=self.domain)
                )

    async def _additions_member(self):
        payload = self.updates[0].object.body.get("message").get("payload")
        if not payload:
            return

        async with self.app.database.session.begin() as session:
            raw_current_game = await session.execute(select(CurrentGameModel))
            fetch = raw_current_game.fetchall()
        current_game = CurrentGame(
            **json.loads(str(fetch[0][-1]))["CurrentGame"]
        )
        payload_key = json.loads(payload)["key"]
        if payload_key == "I play":
            async with self.app.database.session.begin() as session:
                raw_users = await session.execute(
                    select(UsersModel).where(UsersModel.vk_id == self.domain)
                )
                users = Users(**json.loads(str(raw_users.fetchone()[0]))["Users"])

            async with self.app.database.session.begin() as session:
                raw_game_user = await session.execute(
                    select(GameUserModel).where(GameUserModel.user_id == users.id)
                )
            if raw_game_user.fetchall():
                message_to_send = MessageToSend.member_already_exists
            else:

                async with self.app.database.session.begin() as session:
                    raw_users = await session.execute(
                        select(UsersModel).where(UsersModel.vk_id == self.domain)
                    )
                    users = Users(**json.loads(str(raw_users.fetchone()[0]))["Users"])

                async with self.app.database.session.begin() as session:
                    game_user = GameUserModel(
                        user_id=users.id,
                        status="in_game",
                        current_game_id=self.current_game_id,
                    )
                    session.add(game_user)
                self.message_to_send = (
                    f"[{self.domain}|{self.last_name} {self.first_name}] участвует"
                )
                message_to_send = MessageToSend.new_member.format(
                    domain=self.domain,
                    last_name=self.last_name,
                    first_name=self.first_name,
                )
            await self.send_message(message_text=message_to_send)
        elif payload_key == "Finish recruiting players" and self.domain == current_game.host:
            string_members = ""
            async with self.app.database.session.begin() as session:
                raw_game_users = await session.execute(select(GameUserModel))

            for game_user in raw_game_users.fetchall():
                game_user = GameUser(**json.loads(str(game_user[0]))["GameUser"])
                async with self.app.database.session.begin() as session:
                    raw_user = await session.execute(
                        select(UsersModel).where(UsersModel.id == game_user.user_id)
                    )
                    fetch_raw_user = raw_user.fetchone()
                    if fetch_raw_user:
                        user = Users(**json.loads(str(fetch_raw_user[0]))["Users"])
                        string_members += f"[{user.vk_id}|{user.full_name}]%0A"
            message_to_send = MessageToSend.list_members.format(members=string_members)
            await self.send_message(message_text=message_to_send)
            async with self.app.database.session.begin() as session:
                await session.execute(
                    update(CurrentGameModel)
                    .where(CurrentGameModel.id == self.current_game_id)
                    .values(state=2)
                )
            self.state = 2
            await self.state_machine()

    async def _start_distribution_card(self):
        await self.generate_table()
        await self.give_cards()

        async with self.app.database.session.begin() as session:
            raw_game_users = await session.execute(select(GameUserModel))
        game_users = [
            GameUser(**json.loads(str(user[0]))["GameUser"])
            for user in raw_game_users.fetchall()
        ]

        for game_user in game_users:

            async with self.app.database.session.begin() as session:
                raw_users = await session.execute(select(UsersModel).where(UsersModel.id == game_user.user_id))
            user = Users(**json.loads(str(raw_users.fetchone()[0]))["Users"])

            member_k = user.vk_id
            full_name = user.full_name
            name = f"[{member_k}|{full_name}]"
            cards = await self.cards_member(member_k)
            if member_k == "Diller":
                name = member_k
                cards = await self.cards_diller(all_=False)
            message_to_send = MessageToSend.cards_member.format(name=name, cards=cards)
            await self.send_message(
                message_text=message_to_send, buttons=Buttons.game_process_buttons
            )

        await self.next_queue()
        message_to_send = MessageToSend.member_makes_move.format(
            domain_queue=self.queue_domain, full_name_queue=self.full_name_queue
        )
        await self.send_message(message_text=message_to_send)

        async with self.app.database.session.begin() as session:
            await session.execute(
                update(CurrentGameModel)
                .where(CurrentGameModel.id == self.current_game_id)
                .values(state=3)
            )
        self.state = 3

    async def _start_game(self):

        if self.queue_domain != self.domain:
            return

        async with self.app.database.session.begin() as session:
            raw_user = await session.execute(
                select(UsersModel).where(UsersModel.vk_id == self.queue_domain)
            )
        user = Users(**json.loads(str(raw_user.fetchone()[0]))["Users"])
        async with self.app.database.session.begin() as session:
            raw_game_user = await session.execute(
                select(GameUserModel).where(GameUserModel.user_id == user.id)
            )
        game_user = GameUser(**json.loads(str(raw_game_user.fetchone()[0]))["GameUser"])

        payload = self.updates[0].object.body.get("message").get("payload")
        if payload is None:
            return
        payload = json.loads(payload).get("key")

        if payload == "Another card":
            await self.give_cadr_member(self.queue_domain)
            message_to_send = MessageToSend.cards_player.format(
                domain_queue=self.queue_domain,
                full_name_queue=self.full_name_queue,
                cards=await self.cards_member(self.queue_domain),
            )
            await self.send_message(message_text=message_to_send)
        elif payload == "Pass":

            async with self.app.database.session.begin() as session:
                await session.execute(
                    update(GameUserModel)
                    .where(GameUserModel.user_id == user.id)
                    .values(status="pass")
                )

            message_to_send = MessageToSend.player_pass.format(
                domain_queue=self.queue_domain, full_name_queue=self.full_name_queue
            )
            await self.send_message(message_text=message_to_send)

            message_to_send = MessageToSend.cards_player.format(
                domain_queue=self.queue_domain,
                full_name_queue=self.full_name_queue,
                cards=await self.cards_member(self.queue_domain),
            )

            await self.send_message(message_text=message_to_send)

        await self.over21(game_user=game_user)

        await self.card_opening_result(game_user=game_user)

    async def over21(self, game_user):

        async with self.app.database.session.begin() as session:
            raw_game_user = await session.execute(
                select(GameUserModel).where(GameUserModel.id == game_user.id)
            )
        game_user = GameUser(**json.loads(str(raw_game_user.fetchone()[0]))["GameUser"])

        game_user_sum_price_cards = sum(
            [self.card_deck[card] for card in game_user.cards.split(", ")]
        )

        if game_user_sum_price_cards > 21:
            async with self.app.database.session.begin() as session:
                await session.execute(
                    update(GameUserModel)
                    .where(GameUserModel.id == game_user.id)
                    .values(status="lost")
                )
            message_to_send = MessageToSend.member_loss.format(
                domain_queue=self.queue_domain, full_name_queue=self.full_name_queue
            )
            await self.send_message(message_text=message_to_send)

    async def card_opening_result(self, game_user):
        async with self.app.database.session.begin() as session:
            raw_game_users = await session.execute(
                select(GameUserModel).where(GameUserModel.status == MemberStatus.pass_)
            )
        list_members_pass = [
            GameUser(**json.loads(str(user[0]))["GameUser"])
            for user in raw_game_users.fetchall()
        ]
        async with self.app.database.session.begin() as session:
            raw_game_users = await session.execute(
                select(GameUserModel).where(
                    GameUserModel.status == MemberStatus.in_game
                )
            )
        list_members_in_game = [
            GameUser(**json.loads(str(user[0]))["GameUser"])
            for user in raw_game_users.fetchall()
        ]
        if not list_members_in_game:
            message_to_send = MessageToSend.cards_diller.format(
                cards=await self.cards_diller(all_=True)
            )
            await self.send_message(message_to_send)
            for member in list_members_pass:
                async with self.app.database.session.begin() as session:
                    raw_user = await session.execute(
                        select(UsersModel).where(UsersModel.id == member.user_id)
                    )
                user = Users(**json.loads(str(raw_user.fetchone()[0]))["Users"])
                i_domain = user.vk_id
                full_name = user.full_name
                cards = member.cards
                message_to_send = MessageToSend.cards_player.format(
                    domain_queue=i_domain, full_name_queue=full_name, cards=cards
                )
                await self.send_message(message_text=message_to_send)

                if i_domain != "Diller":
                    sum_cards_member = sum(
                        [self.card_deck[card] for card in member.cards.split(", ")]
                    )
                    async with self.app.database.session.begin() as session:
                        raw_diller_user = await session.execute(
                            select(UsersModel).where(UsersModel.vk_id == "Diller")
                        )
                    diller_user = Users(
                        **json.loads(str(raw_diller_user.fetchone()[0]))["Users"]
                    )
                    async with self.app.database.session.begin() as session:
                        raw_diller_game_user = await session.execute(
                            select(GameUserModel).where(
                                GameUserModel.user_id == diller_user.id
                            )
                        )
                    diller_game_user = GameUser(
                        **json.loads(str(raw_diller_game_user.fetchone()[0]))[
                            "GameUser"
                        ]
                    )

                    sum_cards_diller = sum(
                        [
                            self.card_deck[card]
                            for card in diller_game_user.cards.split(", ")
                        ]
                    )
                    if sum_cards_member > sum_cards_diller:
                        async with self.app.database.session.begin() as session:
                            await session.execute(
                                update(StatisticsModel)
                                .where(StatisticsModel.id == user.statistic_id)
                                .values(total_wins=StatisticsModel.total_wins + 1)
                            )
                        message_to_send = MessageToSend.win.format(
                            domain_queue=i_domain, full_name_queue=full_name
                        )
                    elif sum_cards_diller == sum_cards_member:
                        async with self.app.database.session.begin() as session:
                            await session.execute(
                                update(StatisticsModel)
                                .where(StatisticsModel.id == user.statistic_id)
                                .values(total_draw=StatisticsModel.total_draw + 1)
                            )
                        message_to_send = MessageToSend.tie.format(
                            domain_queue=i_domain, full_name_queue=full_name
                        )
                    else:
                        async with self.app.database.session.begin() as session:
                            await session.execute(
                                update(StatisticsModel)
                                .where(StatisticsModel.id == user.statistic_id)
                                .values(total_losses=StatisticsModel.total_losses + 1)
                            )
                        message_to_send = MessageToSend.loss.format(
                            domain_queue=i_domain, full_name_queue=full_name
                        )

                    await self.send_message(message_text=message_to_send)

            await self.clear_all_hands()
            await self.give_cards()
            async with self.app.database.session.begin() as session:
                raw_game_users = await session.execute(select(GameUserModel))
            game_users = [
                GameUser(**json.loads(str(user[0]))["GameUser"])
                for user in raw_game_users.fetchall()
            ]
            for game_user in game_users:
                async with self.app.database.session.begin() as session:
                    raw_user = await session.execute(
                        select(UsersModel).where(UsersModel.id == game_user.user_id)
                    )
                user = Users(**json.loads(str(raw_user.fetchone()[0]))["Users"])
                member_k = user.vk_id
                full_name = user.full_name
                if member_k != "Diller":
                    message_to_send = MessageToSend.new_cards_member.format(
                        domain_queue=member_k,
                        full_name_queue=full_name,
                        cards=await self.cards_member(member_k),
                    )
                    await self.send_message(message_text=message_to_send)
            message_to_send = MessageToSend.new_cards_diller.format(
                cards=await self.cards_diller(all_=False)
            )
            await self.send_message(message_text=message_to_send)

        if self.queue_domain == self.domain:
            await self.next_queue()

        message_to_send = MessageToSend.member_makes_move.format(
            domain_queue=self.queue_domain, full_name_queue=self.full_name_queue
        )
        await self.send_message(message_text=message_to_send)

    async def next_queue(self):
        list_members_in_game = []
        async with self.app.database.session.begin() as session:
            raw_game_users = await session.execute(
                select(GameUserModel).where(GameUserModel.status == "in_game")
            )
        for raw_game_user in raw_game_users:
            game_user = GameUser(**json.loads(str(raw_game_user[0]))["GameUser"])
            list_members_in_game.append(game_user)

        async with self.app.database.session.begin() as session:
            await session.execute(
                update(CurrentGameModel)
                .where(CurrentGameModel.id == self.current_game_id)
                .values(queue=CurrentGameModel.queue + 1)
            )
        async with self.app.database.session.begin() as session:
            raw_current_game = await session.execute(
                select(CurrentGameModel).where(
                    CurrentGameModel.id == self.current_game_id
                )
            )
            current_game = CurrentGame(
                **json.loads(str(raw_current_game.fetchone()[0]))["CurrentGame"]
            )
            self.queue = current_game.queue
        self.number_members_in_game = len(list_members_in_game)
        if self.queue >= self.number_members_in_game:
            async with self.app.database.session.begin() as session:
                await session.execute(
                    update(CurrentGameModel)
                    .where(CurrentGameModel.id == self.current_game_id)
                    .values(queue=0)
                )
            self.queue = 0

        async with self.app.database.session.begin() as session:
            raw_user = await session.execute(
                select(UsersModel).where(
                    list_members_in_game[self.queue].user_id == UsersModel.id
                )
            )
            user = Users(**json.loads(str(raw_user.fetchone()[0]))["Users"])

        self.queue_domain = user.vk_id
        self.full_name_queue = user.full_name

    async def send_message(self, message_text, buttons="{}"):
        for update in self.updates:
            await self.app.store.vk_api.send_message(
                Message(
                    user_id=update.object.user_id,
                    text=message_text,
                    peer_id=self.peer_id,
                    chat_id=self.peer_id - 2000000000,
                    kwargs={"buttons": buttons},
                )
            )

    async def close_game(self):
        self.state = 0
        self.members = {}
        self.host = ""
        self.card_deck = {}
        self.table = {}
        async with self.app.database.session.begin() as session:
            await session.execute(delete(GameUserModel))
        async with self.app.database.session.begin() as session:
            await session.execute(delete(CurrentGameModel))
        async with self.app.database.session.begin() as session:
            await session.execute(delete(ChatModel))

    async def add_current_game_model(self, chat_id):
        async with self.app.database.session.begin() as session:
            result_raw = await session.execute(select(CurrentGameModel))
            raw_current_game = result_raw.fetchall()
        if not raw_current_game:
            async with self.app.database.session.begin() as session:
                chat_model = ChatModel(chat_id=chat_id)
                session.add(chat_model)
            async with self.app.database.session.begin() as session:
                raw_current_game = CurrentGameModel(
                    chat_id=chat_model.id
                )
                session.add(raw_current_game)
            current_game = CurrentGame(
                **json.loads(str(raw_current_game))["CurrentGame"]
            )
        else:
            current_game = CurrentGame(
                **json.loads(str(raw_current_game[0][-1]))["CurrentGame"]
            )
        self.state = current_game.state
        self.chat_id = current_game.chat_id
        self.current_game_id = current_game.id
        self.queue = current_game.queue

    async def add_users_model(self, last_name, first_name, domain):
        async with self.app.database.session.begin() as session:
            result_raw = await session.execute(
                select(UsersModel).where(UsersModel.vk_id == self.domain)
            )
            result_users = result_raw.fetchone()
        if not result_users:
            async with self.app.database.session.begin() as session:
                statistic_model = StatisticsModel()
                session.add(statistic_model)
            async with self.app.database.session.begin() as session:
                user_model = UsersModel(
                    full_name=f"{last_name} {first_name}",
                    vk_id=domain,
                    statistic_id=statistic_model.id,
                )
                session.add(user_model)
            users = Users(**json.loads(str(user_model))["Users"])

        else:
            users = Users(**json.loads(str(result_users[0]))["Users"])

    async def generate_table(self):
        async with self.app.database.session.begin() as session:
            raw_users = await session.execute(
                select(UsersModel).where(UsersModel.vk_id == "Diller")
            )
            fetch_user = raw_users.fetchone()
        if not fetch_user:
            async with self.app.database.session.begin() as session:
                user = UsersModel(vk_id="Diller")
                session.add(user)
        user = Users(**json.loads(str(fetch_user[0]))["Users"])
        async with self.app.database.session.begin() as session:
            game_user = GameUserModel(
                user_id=user.id, current_game_id=self.current_game_id
            )
            session.add(game_user)

    async def clear_all_hands(self):
        async with self.app.database.session.begin() as session:
            raw_users = await session.execute(select(UsersModel))
        users = [
            Users(**json.loads(str(user[0]))["Users"]) for user in raw_users.fetchall()
        ]
        for user in users:
            await self.clear_hand_member(user)

    async def clear_hand_member(self, user):
        domain = user.vk_id
        async with self.app.database.session.begin() as session:
            session.execute(
                update(GameUserModel)
                .where(GameUserModel.user_id == user.id)
                .values(cards="")
            )
        if domain != "Diller":
            async with self.app.database.session.begin() as session:
                await session.execute(
                    update(GameUserModel)
                    .where(GameUserModel.user_id == user.id)
                    .values(cards="", status="in_game")
                )
        else:
            async with self.app.database.session.begin() as session:
                await session.execute(
                    update(GameUserModel)
                    .where(GameUserModel.user_id == user.id)
                    .values(cards="")
                )

    async def give_cards(self):

        async with self.app.database.session.begin() as session:
            raw_game_users = await session.execute(select(GameUserModel))
            game_users = [
                GameUser(**json.loads(str(user[0]))["GameUser"]) for user in raw_game_users.fetchall()
            ]

        for game_user in game_users:
            async with self.app.database.session.begin() as session:
                raw_user = await session.execute(select(UsersModel).where(UsersModel.id == game_user.user_id))
            user = Users(**json.loads(str(raw_user.fetchone()[0]))["Users"])

            member_k = user.vk_id
            if member_k == "Diller":
                await self.give_cadr_member(member_k, 2, 17)
            else:
                await self.give_cadr_member(member_k, 2, 21)

    async def give_cadr_member(self, domain, count_cards=1, limit=None):
        if len(self.card_deck) <= 2:
            self.generate_card_deck()
        async with self.app.database.session.begin() as session:
            raw_user = await session.execute(
                select(UsersModel).where(UsersModel.vk_id == domain)
            )
        user = Users(**json.loads(str(raw_user.fetchone()[0]))["Users"])

        async with self.app.database.session.begin() as session:
            raw_game_user = await session.execute(
                select(GameUserModel).where(GameUserModel.user_id == user.id)
            )
        fetch_game_user = raw_game_user.fetchone()
        if not fetch_game_user:
            return
        game_user = GameUser(**json.loads(str(fetch_game_user[0]))["GameUser"])
        mixed_deck = list(self.card_deck)
        limit = 100 if limit is None else limit
        if game_user.cards == "":
            hand = []
        else:
            hand = game_user.cards.split(", ")
        price_cards_in_hand = [0]
        for card in hand:
            if card:
                price_cards_in_hand.append(self.card_deck[card])
        sum_price_cards_in_hand = sum(price_cards_in_hand)
        cards_in_hand = hand
        for _ in range(count_cards):
            ready = False
            try:
                while not ready:
                    number_first_card = random.randint(0, len(self.card_deck) - 1)
                    random_card = mixed_deck[number_first_card]
                    random_card_price = self.card_deck[random_card]
                    if 3 <= (sum_price_cards_in_hand + int(random_card_price)) <= limit:
                        cards_in_hand.append(random_card)
                        sum_price_cards_in_hand += random_card_price
                        async with self.app.database.session.begin() as session:
                            await session.execute(
                                update(GameUserModel)
                                .where(GameUserModel.user_id == user.id)
                                .values(cards=", ".join(hand))
                            )
                        ready = True
            except Exception as e:
                print(e)

    def generate_card_deck(self) -> dict:
        cards = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, "Валет", "Дама", "Король", "Туз"]
        types_cards = ["Бубны", "Черви", "Пики", "Крести"]
        self.card_deck = {}
        for card in cards:
            for type_card in types_cards:
                if isinstance(card, str) and card == "Туз":
                    card_price = 11
                elif isinstance(card, str) and card != "Туз":
                    card_price = 10
                else:
                    card_price = card
                self.card_deck[f"{card} {type_card}"] = card_price

        return self.card_deck

    async def cards_diller(self, all_=False):
        number = 0
        if all_ is True:
            number = 0
        elif all_ is False:
            number = 1
        async with self.app.database.session.begin() as session:
            raw_user = await session.execute(
                select(UsersModel).where(UsersModel.vk_id == "Diller")
            )
        user = Users(**json.loads(str(raw_user.fetchone()[0]))["Users"])
        async with self.app.database.session.begin() as session:
            raw_game_user = await session.execute(
                select(GameUserModel).where(GameUserModel.user_id == user.id)
            )
        game_user = GameUser(**json.loads(str(raw_game_user.fetchone()[0]))["GameUser"])
        cards = game_user.cards.split(", ")
        return "%0A".join(cards[number:])

    async def cards_member(self, domain):
        async with self.app.database.session.begin() as session:
            raw_user = await session.execute(
                select(UsersModel).where(UsersModel.vk_id == domain)
            )
        user = Users(**json.loads(str(raw_user.fetchone()[0]))["Users"])
        async with self.app.database.session.begin() as session:
            raw_game_user = await session.execute(
                select(GameUserModel).where(GameUserModel.user_id == user.id)
            )
        fetch_game_user = raw_game_user.fetchone()
        if not fetch_game_user:
            return
        game_user = GameUser(**json.loads(str(fetch_game_user[0]))["GameUser"])
        cards = game_user.cards.split(", ")
        return "%0A".join(cards)
