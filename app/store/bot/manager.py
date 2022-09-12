import json
import typing
from logging import getLogger
from types import NoneType

from app.store.vk_api.dataclasses import Message, Update

if typing.TYPE_CHECKING:
    from app.web.app import Application


class BotManager:
    def __init__(self, app: "Application"):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")
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
        self.members ={}
        self.buttons = None
        self.state = 0
        self.generate_card_deck()

    async def state_machine(self):
        if self.state == 0:
            if self.received_message == "\\играть":
                #TODO Запомнить кто хост (кто набрал \играть)
                # self.send_message = f"{self.card_deck}"
                self.buttons = json.dumps({"buttons": [[{"action": {"type": "text",
                                                                    "payload": json.dumps({"key": "Я участвую"}),
                                                                    "label": "Я участвую"}}],
                                                       [{"action": {"type": "text",
                                                                    "payload": json.dumps(
                                                                        {"key": "Закончить набор игроков"}),
                                                                    "label": "Закончить набор игроков"
                                                                    }
                                                         }]]

                                           }
                                          )
                self.message_to_send = f"{self.first_name} {self.last_name} начал набор игроков!!!"
                await self.send_message()
                self.state = 1
            # TODO вызов набора игроков
        elif self.state == 1:
            payload = self.updates[0].object.body.get("message").get("payload")
            if not payload:
                return
            payload_key = json.loads(payload)["key"]
            if payload_key == "Я участвую":
                if self.domain in self.members:
                    self.message_to_send = "Этот игрок уже участвует"
                else:
                    self.members[self.domain] = f"{self.last_name} {self.first_name}"
                    self.message_to_send = str(self.members)
                await self.send_message()
            elif payload_key == "Закончить набор игроков":
                # TODO Это условие выполнится только если команду "Закончить набор игроков" вызовет хост
                print("Закончить набор игроков")
                self.message_to_send = f"Набор игроков окончен%0AУчастники: {self.members}"
                await self.send_message()
                self.state = 2
            # TODO Тут идёт набор игкроков
        elif self.state == 2:
            # TODO Раскладываешь карты
            print("State 2")
            pass
        elif self.state == 3:
            # TODO начинаешь играть
            pass

    async def passs(self):
        pass

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
        # if self.type == "message_new":
        #     for update in updates:
        #         await self.app.store.vk_api.send_message(
        #             Message(
        #                 user_id=update.object.user_id,
        #                 text=self.message_to_send,#f"[{domain}|{first_name} {last_name}], Какая прикольная штука))",
        #                 peer_id=self.peer_id,
        #                 chat_id=self.peer_id - 2000000000,
        #                 kwargs={}
        #             )
        #         )
        # elif self.type == "message_event":
        #     print(updates)
        #     await self.app.store.vk_api.send_message_event_answer(
        #         Message(
        #             peer_id=self.peer_id,
        #             chat_id=self.peer_id - 2000000000,
        #             text=self.send_answer_message,
        #             user_id=updates[0].object.body["user_id"],
        #             kwargs={
        #                 "event_id": updates[0].object.body["event_id"],
        #                 "event_data": "new_message"
        #                 },
        #               )
        #     )

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
