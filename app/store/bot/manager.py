import json
import typing
from enum import Enum
from logging import getLogger
from types import NoneType
import random

from app.store.vk_api.dataclasses import Message, Update

if typing.TYPE_CHECKING:
    from app.web.app import Application


class MessageToSend(Enum):
    start_additions_member = "{first_name} {last_name} начал набор игроков!!!"
    cards_member = "{name}, карты: {cards}"
    member_makes_move ="[{domain_queue}|{full_name_queue}] делает ход"

    cards_player = "Карты игрока [{domain_queue}|{full_name_queue}]: " \
                                       "%0A{cards}"
    cards_diller = "Карты диллера: %0A{cards}"

    member_loss = "Игрок [{domain_queue}|{full_name_queue}] проиграл"

    new_cards_diller = "Новые карты диллера: %0A{cards}"
    new_cards_member = "Новые карты игрока [{domain_queue}|{full_name_queue}]: " \
                        "%0A{cards}"
    member_already_exists = "Этот игрок уже участвует"
    new_member = "[{domain}|{last_name} {first_name}] участвует"
    list_members = "Набор игроков окончен%0AУчастники: %0A{members}"
    end_game = "Конец игры"

class Buttons(Enum):
    player_add_buttons = json.dumps({"buttons": [[{"action": {"type": "text",
                                                              "payload": json.dumps({"key": "I play"}),
                                                              "label": "I play"}}],
                                                 [{"action": {"type": "text",
                                                              "payload":
                                                                  json.dumps({"key": "Finish recruiting players"}),
                                                              "label": "Finish recruiting players"
                                                              }
                                                   }]]})
    game_process_buttons = json.dumps({"buttons": [[{"action": {"type": "text",
                                                                "payload": json.dumps({"key": "Another card"}),
                                                                "label": "Ещё карту"}}],
                                                   [{"action": {"type": "text",
                                                                "payload": json.dumps(
                                                                    {"key": "Pass"}),
                                                                "label": "Пас"}}]]})


class State(Enum):
    GAME_OFF = 0
    PLAYER_ADD = 1
    CARD_DISTRIBUTION = 2
    START_GAME = 3


class BotManager:
    def __init__(self, app: "Application"):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")
        self.table: dict | None = {}
        self.updates: list[Update] | None = list[Update]()
        self.user_id: int | None = int()
        self.peer_id: int | None = int()
        self.chat_id: int | None = int()
        self.event_id: str | None = str()
        self.type: str | None = str()
        self.card_deck: dict | None = dict()
        self.received_message: str | None = str()
        self.domain: str | None = str()
        self.first_name: str | None = str()
        self.last_name: str | None = str()
        self.send_answer_message: str | None = str()
        self.message_to_send: str | None = str()
        self.members: dict | None = dict()
        self.queue: int | None = 0
        self.host: str | None = str()
        self.state: int | None = 0
        self.generate_card_deck()

    async def state_machine(self):
        if self.state == State.GAME_OFF.value:
            await self._start_additions_member()
        elif self.state == State.PLAYER_ADD.value:
            await self._additions_member()
        elif self.state == State.CARD_DISTRIBUTION.value:
            await self._start_distribution_card()
        elif self.state == State.START_GAME.value:
            await self.start_game()
            # TODO начинаешь играть
            list_members = list(self.members.items())
            num_members = len(list_members)

            if self.queue >= num_members:
                self.queue = 0

            current_domain = list_members[self.queue][0]

            # TODO До условий не должно быть действий
            # list_status_members = list(map(lambda x: x.get("status"), self.table.values()))
            # if "in game" not in list_status_members:
            #     print("Вызов конца игры!!!")

            # TODO Меняется очередь если у текущего пользователя status не равен "in game"
            # while self.table[current_domain]["status"] != "in game":
            #     print(self.table.values())
            #     self.queue += 1

            if current_domain != self.domain:
                return

            full_name_queue = list_members[self.queue][1]
            # self.give_cadr_member(domain_queue)
            payload = self.updates[0].object.body.get("message").get("payload")
            if payload is None:
                return
            payload = json.loads(payload).get("key")

            # TODO Декомпозировать в функцию _start_game() (Придумай другое имя)
            if payload == "Another card":
                self.give_cadr_member(current_domain)
                message_to_send = MessageToSend.cards_player.value.format(domain_queue=current_domain,
                                                                          full_name_queue=full_name_queue,
                                                                          cards='%0A'.join(self.table[current_domain]['cards']))
                await self.send_message(message_text=message_to_send)
            elif payload == "Pass":
                # TODO После пасса нужно чистить руку игрока который сделал пасс
                #  или чистить все руки включая диллера если все сделали пасс
                self.table[current_domain]["status"] = "pass"

                list_status_members = list(map(lambda x: x.get("status"), self.table.values()))
                message_to_send = MessageToSend.cards_diller.value.format(
                                    cards='%0A'.join(self.table["Diller"]['cards']))
                if "in game" not in list_status_members:
                    # TODO Вызов логики пасс у всех!!!
                    await self.send_message(message_to_send)
                    list_pass_members = list(map(lambda x: x.get("status") == "pass", self.table.values()))
                    # for i in self.table:
                    #     print(i-)

                else:
                    message_to_send = MessageToSend.cards_player.value.format(domain_queue=current_domain,
                                                                              full_name_queue=full_name_queue,
                                                                              cards='%0A'.join(self.table[current_domain]['cards']))
                    await self.send_message(message_text=message_to_send)
                    # await self.autopsy_result()
            # if
            self.queue += 1
            # TODO Декомпозировать в функцию autopsy_result()
            if self.table[current_domain]["sum_cards"] > 21:
                self.table[current_domain]["status"] = "lost"
                message_to_send = MessageToSend.member_loss.value.format(domain_queue=current_domain,
                                                                         full_name_queue=full_name_queue)
                await self.send_message(message_text=message_to_send)
                self.clear_hand_member(current_domain)
                if "in game" not in self.members.keys():
                    self.clear_all_hands()
                self.give_cards()
                message_to_send = MessageToSend.new_cards_diller.value.format(cards='%0A'.join(self.table['Diller']['cards']))
                await self.send_message(message_text=message_to_send)
                message_to_send = MessageToSend.new_cards_member.value.format(domain_queue=current_domain,
                                                                              full_name_queue=full_name_queue,
                                                                              cards='%0A'.join(self.table[current_domain]['cards']))
                await self.send_message(message_text=message_to_send)

                self.queue += 1

            message_to_send = MessageToSend.member_makes_move.value.format(domain_queue=current_domain,
                                                                           full_name_queue=full_name_queue)
            await self.send_message(message_text=message_to_send)

    async def _start_additions_member(self):
        if self.received_message == "/start":
            self.host = self.domain
            message_to_send = MessageToSend.start_additions_member.value.format(first_name=self.first_name,
                                                                                last_name=self.last_name)
            await self.send_message(message_text=message_to_send,
                                    buttons=Buttons.player_add_buttons.value)
            self.state = 1

    async def start_distribution_card(self):
        self.generate_table()
        self.give_cards()
        for member_k, member_v in self.table.items():
            name = f"[{member_k}|{member_v.get('full_name')}]"
            if member_k == "Diller":
                name = member_k
            message_to_send = MessageToSend.cards_member.value.format(name=name,
                                                                      cards=', '.join(member_v['cards']))
            await self.send_message(message_text=message_to_send,
                                    buttons=Buttons.game_process_buttons.value)
        self.state = 3
        await self.state_machine()

    async def autopsy_result(self, domain_queue, full_name_queue):
        if self.table[domain_queue]["sum_cards"] > 21:
            self.table[domain_queue]["status"] = "lost"
            self.message_to_send = f"Игрок [{domain_queue}|{full_name_queue}] проиграл"

            self.clear_hand_member(domain_queue)
            if "in game" not in self.members.keys():
                self.clear_all_hands()
            self.give_cards()
            await self.send_message()

            self.message_to_send = f"Новые карты диллера: %0A{'%0A'.join(self.table['Diller']['cards'])}"
            await self.send_message()
            self.message_to_send = f"Новые карты игрока [{domain_queue}|{full_name_queue}]: " \
                                   f"%0A{'%0A'.join(self.table[domain_queue]['cards'])}"
            await self.send_message()

            self.queue += 1

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
            await self.send_message(message_text=message_to_send,
                                    buttons=Buttons.game_process_buttons.value)
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
                    kwargs={"buttons": buttons}
                )
            )

    async def _additions_member(self):
        payload = self.updates[0].object.body.get("message").get("payload")
        if not payload:
            return
        payload_key = json.loads(payload)["key"]
        if payload_key == "I play":
            if self.domain in self.members:
                message_to_send = MessageToSend.member_already_exists.value
            else:
                self.members[self.domain] = f"{self.last_name} {self.first_name}"
                self.message_to_send = f"[{self.domain}|{self.last_name} {self.first_name}] участвует"
                message_to_send = MessageToSend.new_member.value.format(domain=self.domain,
                                                                        last_name=self.last_name,
                                                                        first_name=self.first_name)
            await self.send_message(message_text=message_to_send)
        elif payload_key == "Finish recruiting players" and self.domain == self.host:
            string_members = ""
            for member_k, member_v in self.members.items():
                string_members += f"[{member_k}|{member_v}]%0A"
            # self.message_to_send = f"Набор игроков окончен%0AУчастники: %0A{string_members}"
            message_to_send = MessageToSend.list_members.value.format(members=string_members)
            await self.send_message(message_text=message_to_send)
            self.state = 2
            await self.state_machine()

    async def close_game(self):
        self.state = 0
        self.members = dict()
        self.host = str()
        self.card_deck = dict()

    async def send_answer(self):
        for update in self.updates:
            await self.app.store.vk_api.send_message_event_answer(
                Message(
                    peer_id=self.peer_id,
                    chat_id=self.peer_id - 2000000000,
                    text=self.send_answer_message,
                    user_id=update.object.body["user_id"],
                    kwargs={
                        "event_id": update.object.body["event_id"],
                        "event_data": "new_message"
                    },
                )
            )

    def generate_table(self):
        self.table["Diller"] = {"cards": [], "sum_cards": 0}
        for member_k, member_v in self.members.items():
            self.table[member_k] = {"full_name": member_v, "cards": [], "sum_cards": 0, "status": "in game"}

    def clear_all_hands(self):
        self.generate_table()

    def clear_hand_member(self, member):
        self.table[member]["cards"] = []
        self.table[member]["sum_cards"] = 0

    def give_cards(self):
        for member_k, member_v in self.table.items():
            if member_k == "Diller":
                self.give_cadr_member(member_k, 2, 17)
            else:
                self.give_cadr_member(member_k, 2, 21)

    def give_cadr_member(self, name, count_cards=1, limit=None):
        if len(self.card_deck) <= 2:
            self.generate_card_deck()
        mixed_deck = list(self.card_deck)
        limit = 100 if limit is None else limit
        hand = self.table[name]
        price_cards_in_hand = hand["sum_cards"]
        cards_in_hand = hand["cards"]
        for _ in range(count_cards):
            ready = False
            while not ready:
                number_first_card = random.randint(0, len(self.card_deck)) - 1
                random_card = mixed_deck[number_first_card]
                # TODO Здесь иногда срабатывает ошибка, типа:
                #  File "D:\py_projects\vk_blackjack\vk_blackjack\app\store\bot\manager.py", line 295, in give_cards
                #     self.give_cadr_member(member_k, 2, 21)
                #   File "D:\py_projects\vk_blackjack\vk_blackjack\app\store\bot\manager.py", line 310, in give_cadr_member
                #     random_card_price = self.card_deck[random_card]
                #  KeyError: '9 Черви'
                #  Исправь
                if not self.card_deck.get(random_card):
                    print("")
                random_card_price = self.card_deck[random_card]
                if 3 <= (price_cards_in_hand + int(random_card_price)) <= limit:
                    cards_in_hand.append(random_card)
                    hand["sum_cards"] += random_card_price
                    self.card_deck.pop(random_card)
                    ready = True

    def generate_card_deck(self) -> dict:
        cards = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 'Валет', 'Дама', 'Король', 'Туз']
        types_cards = ['Бубны', 'Черви', 'Пики', 'Крести']
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
