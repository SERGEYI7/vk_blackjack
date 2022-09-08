import base64

from aiohttp.web import HTTPForbidden, HTTPUnauthorized
from aiohttp_apispec import request_schema, response_schema
from aiohttp_session import new_session

from app.admin.schemes import AdminSchema
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
        session_id = base64.b64encode(f"{admin.email}:{admin.password}".encode("utf-8")).decode()
        response.set_cookie("session_id", session_id)

        return response


class AdminCurrentView(View):
    @response_schema(AdminSchema, 200)
    async def get(self):
        raise NotImplementedError
