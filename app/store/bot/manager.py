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
        self.user_id = int()
        self.peer_id = int()
        self.chat_id = int()
        self.event_id = str()
        self.type = str()
        self.card_deck = dict()
        self.message = str()
        self.send_message = str()
        self.state = 0
        self.generate_card_deck()

    async def state_machine(self):
        if self.state == 0:
            if self.message == "\\играть":
                self.send_message = f"{self.card_deck}"
                self.state = 1
            # TODO вызов набора игроков
            pass
        elif self.state == 1:
            self.send_message = "Состояние 1!"
            # TODO Ожидание команды конца набор игроков от того кто запустил набор игроков
            pass
        elif self.state == 2:
            # TODO Раскладываешь карты
            pass
        elif self.state == 3:
            # TODO начинаешь играть
            pass

    async def passs(self):
        pass

    async def handle_updates(self, updates: list[Update]):
        if isinstance(updates, NoneType) or not updates:
            return
        user = await self.app.store.vk_api.user(updates[0].object.user_id)
        user = user.get("response")[0]
        first_name = user.get("first_name")
        last_name = user.get("last_name")
        domain = user.get("domain")
        self.type = updates[0].type
        self.user_id = updates[0].object.user_id
        self.message = updates[0].object.body.get("message").get("text")
        self.peer_id = updates[0].object.body.get("message").get("peer_id")
        self.event_id = updates[0].object.body.get("message").get("event_id")
        self.chat_id = self.peer_id - 2000000000
        await self.state_machine()
        for update in updates:
            await self.app.store.vk_api.send_message(
                Message(
                    user_id=update.object.user_id,
                    text=self.send_message,#f"[{domain}|{first_name} {last_name}], Какая прикольная штука))",
                    peer_id=self.peer_id,
                    chat_id=self.peer_id - 2000000000,
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
