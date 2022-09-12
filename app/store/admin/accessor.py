import typing

from sqlalchemy import select
from json import loads

from app.admin.models import Admin, AdminModel
from app.base.base_accessor import BaseAccessor

class AdminAccessor(BaseAccessor):
    async def get_by_email(self, email: str) -> Admin | None:
        async with self.app.database.session.begin() as session:
            result = await session.execute(select(AdminModel).where(AdminModel.email == email))
            result_repr = result.fetchone()
            if not result_repr:
                return None
            admin_json = loads(str(result_repr[0]))
            admin = Admin(**admin_json["Admin"])
            return admin

    async def create_admin(self, email: str, password: str) -> Admin:
        new_admin = AdminModel(
            email=email,
            password=password,
        )

        async with self.app.database.session.begin() as session:
            session.add(new_admin)
        return new_admin
