"""`TokenVerifier` thật của app (BE-00 §2.2, §5): B0-06 tự nhận qua `build_verifier(app)`.

Hai tầng, đúng thứ tự:

1. **token** — `decode_token("access", …)`: HS256, `aud="access"`, đủ claim, `exp`/`iat`
   so với `Clock` tiêm (PyJWT không bao giờ so giờ thật); hỏng → 401 `UNAUTHENTICATED`;
2. **phiên** — `check_session`: phiên còn sống, người `active`, `ver` khớp; hỏng → 401
   `SESSION_REVOKED`. Vai lấy ở đây, từ DB/cache, không từ claim (K04, K34).
"""

from fastapi import FastAPI
from starlette.requests import Request

from apps.api.auth.services import AuthServices
from apps.api.auth.sessions import check_session
from apps.api.auth.tokens import decode_token
from apps.api.core.auth import Principal, TokenVerifier


class JwtTokenVerifier:
    """Verifier của mọi route được bảo vệ."""

    def __init__(self, services: AuthServices) -> None:
        """Giữ `AuthServices`; tài nguyên được đọc lúc gọi, sau `lifespan`."""
        self._services = services

    async def verify(self, token: str, request: Request) -> Principal:
        """Access token → `Principal`, hoặc 401 (`UNAUTHENTICATED` / `SESSION_REVOKED`), 503 khi DB hỏng."""
        claims = decode_token("access", token, self._services.clock.now())
        return await check_session(self._services, user_id=claims.user_id, sid=claims.sid, ver=claims.ver)


def build_verifier(app: FastAPI) -> TokenVerifier:
    """Gọi trong `create_app`, trước `lifespan`: chỉ dựng, không đọc cấu hình, không kết nối."""
    return JwtTokenVerifier(AuthServices(app))
