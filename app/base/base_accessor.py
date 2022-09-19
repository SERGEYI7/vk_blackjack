import typing
from logging import getLogger
from sqlalchemy import select, text, delete, table
from asyncpg.exceptions import UndefinedTableError
from sqlalchemy.exc import ProgrammingError
from app.admin.models import AdminModel
from app.quiz.models import AnswerModel, QuestionModel, ThemeModel

if typing.TYPE_CHECKING:
    from app.web.app import Application


class BaseAccessor:
    def __init__(self, app: "Application", *args, **kwargs):
        self.app = app
        self.logger = getLogger("accessor")
        app.on_startup.append(self.connect)
        app.on_cleanup.append(self.disconnect)

    async def connect(self, app: "Application"):
        async with self.app.database.session.begin() as session:
            result = await session.execute(select(AdminModel))
            if not result.fetchall():
                await self.app.store.admins.create_admin(
                    self.app.config.admin.email, self.app.config.admin.password
                )

    async def disconnect(self, app: "Application"):
        async with self.app.database.session.begin() as session:
            pass
            # await session.execute(delete(AdminModel))
            # await session.execute(delete(AnswerModel))
            # await session.execute(delete(QuestionModel))
            # await session.execute(delete(ThemeModel))

            # await session.execute(text("delete from admins"))
            # await session.execute(text("delete from answers"))
            # await session.execute(text("delete from questions"))
            # await session.execute(text("delete from themes"))
