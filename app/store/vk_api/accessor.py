import json
import random
import typing
from types import NoneType, coroutine
from typing import Optional

from aiohttp import TCPConnector, ClientResponse
from aiohttp.client import ClientSession

from app.base.base_accessor import BaseAccessor
from app.store.vk_api.dataclasses import Message, Update, UpdateObject
from app.store.vk_api.poller import Poller

if typing.TYPE_CHECKING:
    from app.web.app import Application

API_PATH = "https://api.vk.com/method/"


class VkApiAccessor(BaseAccessor):
    def __init__(self, app: "Application", *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        self.session: Optional[ClientSession] = None
        self.key: Optional[str] = None
        self.server: Optional[str] = None
        self.poller: Optional[Poller] = None
        self.ts: Optional[int] = None

    async def connect(self, app: "Application"):
        self.session = ClientSession(connector=TCPConnector(verify_ssl=False, ))
        try:
            await self._get_long_poll_service()
        except Exception as e:
            self.logger.error("Exception", exc_info=e)
        self.poller = Poller(app.store)
        self.logger.info("start polling")
        await self.poller.start()

    async def disconnect(self, app: "Application"):
        if self.session:
            await self.session.close()
        if self.poller:
            await self.poller.stop()

    @staticmethod
    def _build_query(host: str, method: str, params: dict) -> str:
        url = host + method + "?"
        if "v" not in params:
            params["v"] = "5.131"
        url += "&".join([f"{k}={v}" for k, v in params.items()])
        return url

    async def _get_long_poll_service(self):
        async with self.session.get(
                self._build_query(
                    host=API_PATH,
                    method="groups.getLongPollServer",
                    params={
                        "group_id": self.app.config.bot.group_id,
                        "access_token": self.app.config.bot.token,
                    },
                )
        ) as resp:
            data = (await resp.json())["response"]
            self.logger.info(data)
            if data.get("failed") == 2:
                print("")
                await self._get_long_poll_service()
            self.key = data["key"]
            self.server = data["server"]
            self.ts = data["ts"]
            self.logger.info(self.server)

    async def poll(self):
        async with self.session.get(
                self._build_query(
                    host=self.server,
                    method="",
                    params={
                        "act": "a_check",
                        "key": self.key,
                        "ts": self.ts,
                        "wait": 30,
                    },
                )
        ) as resp:
            data = await resp.json()
            self.logger.info(data)
            self.ts = data["ts"]
            raw_updates = data.get("updates", [])
            updates = []
            for update in raw_updates:
                type = update["type"]
                if type == "message_new":
                    updates.append(
                        Update(
                            type=type,
                            object=UpdateObject(
                                id=update["object"]["message"]["id"],
                                user_id=update["object"]["message"]["from_id"],
                                body=update["object"],
                            ),
                        )
                    )
                elif type == "message_event":
                    updates.append(
                        Update(
                            type=type,
                            object=UpdateObject(
                                id=None,
                                user_id=update["object"]["user_id"],
                                body=update["object"],
                            ),
                        )
                    )
            await self.app.store.bots_manager.handle_updates(updates)

    async def send_message(self, message: Message) -> None:
        async with self.session.get(
                self._build_query(
                    API_PATH,
                    "messages.send",
                    params={
                        # "user_id": message.user_id,
                        "random_id": random.randint(1, 2 ** 32),
                        "peer_id": message.peer_id,#"-" + str(self.app.config.bot.group_id),
                        "chat_id": message.chat_id,
                        "message": message.text,
                        "keyboard": message.kwargs["buttons"],
                        "access_token": self.app.config.bot.token,
                    },
                )
        ) as resp:
            data = await resp.json()
            self.logger.info(data)

    async def send_message_event_answer(self, message):
        async with self.session.get(
            self._build_query(
                API_PATH,
                "messages.sendMessageEventAnswer",
                params={
                    "event_id": message.kwargs["event_id"],
                    "user_id": message.user_id,
                    "peer_id": message.peer_id,
                    "event_data": json.dumps({
                        "type": "show_snackbar",
                        "text": message.text
                        }),
                    "access_token": self.app.config.bot.token
                },
            )
        ) as event_answer:
            print(await event_answer.json())

    async def user(self, user_id):
        async with self.session.get(
            self._build_query(
                API_PATH,
                "users.get",
                params={"user_ids": user_id,
                        "fields": "domain",
                        "access_token": self.app.config.bot.token}
            )
        ) as resp:
            response = await resp.json()
            return response
