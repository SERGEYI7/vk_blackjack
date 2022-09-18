import json
import typing
from enum import Enum
from logging import getLogger
from types import NoneType
import random

from app.store.vk_api.dataclasses import Message, Update

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
        self.current_domain = ""
        self.full_name_queue = ""
        self.generate_card_deck()

    async def state_machine(self):
        if self.state == State.GAME_OFF.value:
            await self._start_additions_member()
        elif self.state == State.PLAYER_ADD.value:
            await self._additions_member()
        elif self.state == State.CARD_DISTRIBUTION.value:
            await self._start_distribution_card()
        elif self.state == State.START_GAME.value:
            await self._start_game()

    async def _start_additions_member(self):
        if self.received_message == "/start":
            self.host = self.domain
            message_to_send = MessageToSend.start_additions_member.format(
                first_name=self.first_name, last_name=self.last_name
            )
            await self.send_message(
                message_text=message_to_send, buttons=Buttons.player_add_buttons
            )
            self.state = 1

    async def _additions_member(self):
        payload = self.updates[0].object.body.get("message").get("payload")
        if not payload:
            return
        payload_key = json.loads(payload)["key"]
        if payload_key == "I play":
            if self.domain in self.members:
                message_to_send = MessageToSend.member_already_exists
            else:
                self.members[self.domain] = {
                    "full_name": f"{self.last_name} {self.first_name}",
                    "status": "in_game",
                }
                self.message_to_send = (
                    f"[{self.domain}|{self.last_name} {self.first_name}] участвует"
                )
                message_to_send = MessageToSend.new_member.format(
                    domain=self.domain,
                    last_name=self.last_name,
                    first_name=self.first_name,
                )
            await self.send_message(message_text=message_to_send)
        elif payload_key == "Finish recruiting players" and self.domain == self.host:
            string_members = ""
            for member_k, member_v in self.members.items():
                string_members += f"[{member_k}|{member_v['full_name']}]%0A"
            message_to_send = MessageToSend.list_members.format(members=string_members)
            await self.send_message(message_text=message_to_send)
            self.state = 2
            await self.state_machine()

    async def _start_distribution_card(self):
        self.generate_table()
        self.give_cards()
        for member_k, member_v in self.table.items():
            name = f"[{member_k}|{member_v.get('full_name')}]"
            cards = self.cards_member(member_k)
            if member_k == "Diller":
                name = member_k
                cards = self.cards_diller(all_=False)
            message_to_send = MessageToSend.cards_member.format(name=name, cards=cards)
            await self.send_message(
                message_text=message_to_send, buttons=Buttons.game_process_buttons
            )

        self.state = 3

        self.next_queue()
        message_to_send = MessageToSend.member_makes_move.format(
            domain_queue=self.current_domain, full_name_queue=self.full_name_queue
        )
        await self.send_message(message_text=message_to_send)

    async def _start_game(self):

        if self.current_domain != self.domain:
            return

        payload = self.updates[0].object.body.get("message").get("payload")
        if payload is None:
            return
        payload = json.loads(payload).get("key")

        if payload == "Another card":
            self.give_cadr_member(self.current_domain)
            message_to_send = MessageToSend.cards_player.format(
                domain_queue=self.current_domain,
                full_name_queue=self.full_name_queue,
                cards=self.cards_member(self.current_domain),
            )
            await self.send_message(message_text=message_to_send)
        elif payload == "Pass":
            self.table[self.current_domain]["status"] = "pass"
            self.members[self.current_domain]["status"] = "pass"

            message_to_send = MessageToSend.player_pass.format(
                domain_queue=self.current_domain, full_name_queue=self.full_name_queue
            )
            await self.send_message(message_text=message_to_send)

            message_to_send = MessageToSend.cards_player.format(
                domain_queue=self.current_domain,
                full_name_queue=self.full_name_queue,
                cards=self.cards_member(self.current_domain),
            )

            await self.send_message(message_text=message_to_send)

        await self.over21()

        await self.card_opening_result()

    async def over21(self):
        if self.table[self.current_domain]["sum_cards"] > 21:
            self.table[self.current_domain]["status"] = "lost"
            self.members[self.current_domain]["status"] = "lost"
            message_to_send = MessageToSend.member_loss.format(
                domain_queue=self.current_domain, full_name_queue=self.full_name_queue
            )
            await self.send_message(message_text=message_to_send)

    async def card_opening_result(self):
        list_members_pass = [
            member
            for member in self.members.items()
            if member[1]["status"] == MemberStatus.pass_
        ]
        list_members_in_game = [
            member
            for member in self.members.items()
            if member[1]["status"] == MemberStatus.in_game
        ]
        if not list_members_in_game:
            message_to_send = MessageToSend.cards_diller.format(
                cards=self.cards_diller(all_=True)
            )
            await self.send_message(message_to_send)
            for i_domain in list_members_pass:
                full_name = self.table[i_domain[0]]["full_name"]
                cards = self.table[i_domain[0]]["cards"]
                message_to_send = MessageToSend.cards_player.format(
                    domain_queue=i_domain[0], full_name_queue=full_name, cards=cards
                )
                await self.send_message(message_text=message_to_send)

                if i_domain != "Diller":
                    sum_cards_member = []
                    for member_k, member_v in self.table.items():
                        if member_k != "Diller":
                            sum_cards_member.append(member_v["sum_cards"])
                    max_sum_cards_member = max(sum_cards_member)
                    sum_cards_diller = self.table["Diller"]["sum_cards"]
                    if max_sum_cards_member > sum_cards_diller:
                        message_to_send = MessageToSend.win.format(
                            domain_queue=i_domain[0], full_name_queue=full_name
                        )
                    elif max_sum_cards_member == sum_cards_diller:
                        message_to_send = MessageToSend.tie.format(
                            domain_queue=i_domain[0], full_name_queue=full_name
                        )
                    else:
                        message_to_send = MessageToSend.loss.format(
                            domain_queue=i_domain[0], full_name_queue=full_name
                        )

                    await self.send_message(message_text=message_to_send)

            self.clear_all_hands()
            self.give_cards()
            for member_k, member_v in self.table.items():
                if member_k != "Diller":
                    message_to_send = MessageToSend.new_cards_member.format(
                        domain_queue=member_k,
                        full_name_queue=member_v["full_name"],
                        cards=self.cards_member(member_k),
                    )
                    await self.send_message(message_text=message_to_send)
            message_to_send = MessageToSend.new_cards_diller.format(
                cards=self.cards_diller(all_=False)
            )
            await self.send_message(message_text=message_to_send)

        if self.current_domain == self.domain:
            self.next_queue()

        message_to_send = MessageToSend.member_makes_move.format(
            domain_queue=self.current_domain, full_name_queue=self.full_name_queue
        )
        await self.send_message(message_text=message_to_send)

    def next_queue(self):
        self.queue += 1
        self.number_members_in_game = len(
            [
                member
                for member in self.members.items()
                if member[1]["status"] == MemberStatus.in_game
            ]
        )
        if self.queue >= self.number_members_in_game:
            self.queue = 0
        list_members_in_game = [
            member
            for member in self.members.items()
            if member[1]["status"] == MemberStatus.in_game
        ]
        self.current_domain = list_members_in_game[self.queue][0]
        self.full_name_queue = list_members_in_game[self.queue][1]["full_name"]

    async def handle_updates(self, updates: list[Update]):
        if isinstance(updates, NoneType) or not updates:
            return
        self.updates = updates
        user = await self.app.store.vk_api.user(updates[0].object.user_id)
        user = user.get("response")[0]
        self.first_name = user.get("first_name")
        self.last_name = user.get("last_name")
        self.domain = user.get("domain")
        message_body = updates[0].object.body.get("message")
        if updates[0].object.body.get("message"):
            self.received_message = message_body.get("text")
            self.peer_id = message_body.get("peer_id")
            self.event_id = message_body.get("event_id")
        if self.host == self.domain and self.received_message == "/end":
            await self.close_game()
            message_to_send = MessageToSend.end_game.value
            await self.send_message(
                message_text=message_to_send, buttons=Buttons.game_process_buttons
            )
            return
        self.type = updates[0].type
        self.user_id = updates[0].object.user_id
        self.chat_id = self.peer_id - 2000000000
        await self.state_machine()

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

    def generate_table(self):
        self.table["Diller"] = {"cards": [], "sum_cards": 0}
        for member_k, member_v in self.members.items():
            self.table[member_k] = {
                "full_name": member_v["full_name"],
                "cards": [],
                "sum_cards": 0,
                "status": "in_game",
            }
            if member_k != "Diller":
                self.members[member_k]["status"] = "in_game"

    def clear_all_hands(self):
        self.generate_table()

    def clear_hand_member(self, domain):
        self.table[domain]["cards"] = []
        self.table[domain]["sum_cards"] = 0
        if domain != "Diller":
            self.table[domain]["status"] = "in_game"
            self.members[domain]["status"] = "in_game"

    def give_cards(self):
        for member_k, member_v in self.table.items():
            if member_k == "Diller":
                self.give_cadr_member(member_k, 2, 17)
            else:
                self.give_cadr_member(member_k, 2, 21)

    def give_cadr_member(self, domain, count_cards=1, limit=None):
        if len(self.card_deck) <= 2:
            self.generate_card_deck()
        mixed_deck = list(self.card_deck)
        limit = 100 if limit is None else limit
        hand = self.table[domain]
        price_cards_in_hand = hand["sum_cards"]
        cards_in_hand = hand["cards"]
        for _ in range(count_cards):
            ready = False
            try:
                while not ready:
                    number_first_card = random.randint(0, len(self.card_deck) - 1)
                    random_card = mixed_deck[number_first_card]
                    random_card_price = self.card_deck[random_card]
                    if 3 <= (price_cards_in_hand + int(random_card_price)) <= limit:
                        cards_in_hand.append(random_card)
                        hand["sum_cards"] += random_card_price
                        self.card_deck.pop(random_card)
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

    def cards_diller(self, all_=False):
        number = 0
        if all_ is True:
            number = 0
        elif all_ is False:
            number = 1
        return "%0A".join(self.table["Diller"]["cards"][number:])

    def cards_member(self, domain):
        return "%0A".join(self.table[domain]["cards"])
