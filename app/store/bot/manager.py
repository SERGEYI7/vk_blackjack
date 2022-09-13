import json
import typing
from logging import getLogger
from types import NoneType
import random

from app.store.vk_api.dataclasses import Message, Update

if typing.TYPE_CHECKING:
    from app.web.app import Application


class BotManager:
    def __init__(self, app: "Application"):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")
        self.table = {}
        self.updates = list[Update]
        self.user_id = int()
        self.peer_id = int()
        self.chat_id = int()
        self.event_id = str()
        self.type = str()
        self.card_deck = dict()
        self.received_message = str()
        self.domain = str()
        self.first_name = str()
        self.last_name = str()
        self.send_answer_message = str()
        self.message_to_send = str()
        self.members = {}
        self.queue = 0
        self.host = str()
        self.buttons = None
        self.state = 0
        self.generate_card_deck()

    async def state_machine(self):
        if self.state == 0:
            if self.received_message == "\\start":
                # self.send_message = f"{self.card_deck}"
                # TODO вызов набора игроков
                self.host = self.domain
                self.buttons = json.dumps({"buttons": [[{"action": {"type": "text",
                                                                    "payload": json.dumps({"key": "I play"}),
                                                                    "label": "I play"}}],
                                                       [{"action": {"type": "text",
                                                                    "payload": json.dumps(
                                                                        {"key": "Finish recruiting players"}),
                                                                    "label": "Finish recruiting players"
                                                                    }
                                                         }]]

                                           }
                                          )
                self.message_to_send = f"{self.first_name} {self.last_name} начал набор игроков!!!"
                await self.send_message()
                self.state = 1
        elif self.state == 1:
            payload = self.updates[0].object.body.get("message").get("payload")
            print(payload)
            if not payload:
                return
            payload_key = json.loads(payload)["key"]
            if payload_key == "I play":
                if self.domain in self.members:
                    self.message_to_send = "Этот игрок уже участвует"
                else:
                    self.members[self.domain] = f"{self.last_name} {self.first_name}"
                    self.message_to_send = f"[{self.domain}|{self.last_name} {self.first_name}] участвует"  # str(self.members)
                await self.send_message()
            elif payload_key == "Finish recruiting players" and self.domain == self.host:
                # TODO Это условие выполнится только если команду "Закончить набор игроков" вызовет хост
                # TODO Тут идёт набор игкроков
                print("Закончить набор игроков")
                string_members = ""
                for member_k, member_v in self.members.items():
                    string_members += f"[{member_k}|{member_v}]%0A"
                self.message_to_send = f"Набор игроков окончен%0AУчастники: %0A{string_members}"
                await self.send_message()
                self.state = 2

                await self.state_machine()
        elif self.state == 2:
            print("State 2")
            # TODO Раскладываешь карты игрокам
            self.generate_table()
            self.give_cards()
            self.buttons = json.dumps({"buttons": [
                [{"action": {"type": "text",
                             "payload": json.dumps({"key": "I play"}),
                             "label": "Ещё карту"}}],
                [{"action": {"type": "text",
                             "payload": json.dumps(
                                 {"key": "Finish recruiting players"}),
                             "label": "Пас"}}]]})
            for member_k, member_v in self.table.items():
                name = f"[{member_k}|{member_v.get('full_name')}]"
                if member_k == "Diller":
                    name = member_k
                self.message_to_send = f"{name}, карты: {', '.join(member_v['cards'])}"
                await self.send_message()
            self.state = 3
            await self.state_machine()
        elif self.state == 3:
            # TODO начинаешь играть
            list_members = list(self.members.items())
            num_members = len(list_members)
            if self.queue > num_members:
                self.queue = 0
            domain_queue = list_members[self.queue][0]
            full_name_queue = list_members[self.queue][1]
            self.message_to_send = f"[{domain_queue}|{full_name_queue}] делает ход"
            if domain_queue != self.domain:
                return
            self.give_cadr_member(domain_queue)
            if self.table[domain_queue]["sum_cards"] > 24:
                self.message_to_send = f"Игрок [{domain_queue}|{full_name_queue}] проиграл"
                for i in range(2):
                    self.give_cadr_member(domain_queue)
                self.queue += 1
            await self.send_message()

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
        self.type = updates[0].type
        self.user_id = updates[0].object.user_id
        self.chat_id = self.peer_id - 2000000000
        await self.state_machine()

    async def send_message(self):
        for update in self.updates:
            await self.app.store.vk_api.send_message(
                Message(
                    user_id=update.object.user_id,
                    text=self.message_to_send,  # f"[{domain}|{first_name} {last_name}], Какая прикольная штука))",
                    peer_id=self.peer_id,
                    chat_id=self.peer_id - 2000000000,
                    kwargs={"buttons": self.buttons}
                )
            )

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
        self.table["Diller"] = {"cards": [], "sum_cards": []}
        for member_k, member_v in self.members.items():
            self.table[member_k] = {"full_name": member_v, "cards": [], "sum_cards": []}

    def give_cards(self, limit=None):
        print(self.card_deck)

        for member_k, member_v in self.table.items():
            if member_k == "Diller":
                self.give_cadr_member(member_k, member_v, 17)
            else:
                self.give_cadr_member(member_k, member_v, 24)
            print(self.table)

    def give_cadr_member(self, name, hand=None, limit=None):
        mixed_deck = list(self.card_deck)
        ready = False
        limit = 100 if limit is None else limit
        while not ready:
            number_first_card = random.randint(0, len(self.card_deck)) - 1
            number_second_card = random.randint(0, len(self.card_deck)) - 1
            print(mixed_deck[number_first_card])
            print(mixed_deck[number_second_card])
            first_card = self.card_deck[mixed_deck[number_first_card]]
            second_card = self.card_deck[mixed_deck[number_second_card]]
            cards = [first_card, second_card]
            if 3 <= sum(cards) <= limit:
                self.table[name]["cards"] = [mixed_deck[number_first_card], mixed_deck[number_second_card]]
                print(first_card, second_card)
                self.table[name]["sum_cards"] = first_card + second_card
                self.card_deck.pop(mixed_deck[number_first_card])
                self.card_deck.pop(mixed_deck[number_second_card])
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
