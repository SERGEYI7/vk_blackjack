from typing import Optional, TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import select, text
from sqlalchemy.pool import NullPool

from app.store.database import db

if TYPE_CHECKING:
    from app.web.app import Application


class Database:
    def __init__(self, app: "Application"):
        self.app = app
        self._engine: Optional[AsyncEngine] = None
        self._db: Optional[declarative_base] = None
        self.session: Optional[AsyncSession] = None

    async def connect(self, *_: list, **__: dict) -> None:
        self._db = db
        self._engine = create_async_engine(
            "postgresql+asyncpg://kts_user:kts_pass@localhost/kts"
        )  # , poolclass=NullPool)
        self.session = sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )
        # self.session = sessionmaker(self._engine, class_=AsyncSession)

    async def disconnect(self, *_: list, **__: dict) -> None:
        if self.session:
            await self.session().close()
        if self._engine:
            await self._engine.dispose()
