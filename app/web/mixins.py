from aiohttp.abc import StreamResponse
from aiohttp.web_exceptions import HTTPUnauthorized
from base64 import b64decode


class AuthRequiredMixin:
    async def _iter(self) -> StreamResponse:
        if not getattr(self.request, "admin", None) and not self.request.cookies:
            raise HTTPUnauthorized
        cookie = self.request.cookies.get("session_id")
        email, password = b64decode(cookie).decode().split(':')

        return await super(AuthRequiredMixin, self)._iter()
