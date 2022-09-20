import base64
import json

from aiohttp.web import HTTPForbidden, HTTPUnauthorized
from aiohttp_apispec import request_schema, response_schema
from aiohttp_session import new_session
from sqlalchemy import select

from app.admin.schemes import AdminSchema
from app.quiz.models import StatisticsModel, Statistics
from app.web.app import View
from app.web.utils import json_response


class AdminLoginView(View):
    @request_schema(AdminSchema)
    @response_schema(AdminSchema, 200)
    async def post(self):
        email = self.data.get("email")
        password = self.data.get("password")
        admin = await self.store.admins.get_by_email(email)
        if admin is None:
            raise HTTPForbidden

        response = json_response(data={"id": admin.id, "email": admin.email})
        session_id = base64.b64encode(
            f"{admin.email}:{admin.password}".encode("utf-8")
        ).decode()
        response.set_cookie("session_id", session_id)

        return response


class AdminCurrentView(View):
    @response_schema(AdminSchema, 200)
    async def get(self):
        raise NotImplementedError


class AdminStatisticView(View):
    async def get(self):
        async with self.database.session.begin() as session:
            raw_statistics = await session.execute(select(StatisticsModel))
        statistics = [
            json.loads(str(stat[0]))["Statistics"] for stat in raw_statistics.fetchall()
        ]
        return json_response(data={"data": statistics})
