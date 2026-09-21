"""Token của cookie luồng SSE: JWT `aud="stream"`, khoá `stream` (BE-00 §5).

Cùng khuôn claim với access token nhưng khoá con khác (không khoá nào dùng cho hai việc):
một access token không mở được luồng, một token luồng lọt ra không gọi được API. Chỉ kiểm
chữ ký và thời gian; phiên còn sống hay không là việc của B4-01 (`check_session`).
"""

from apps.api.auth.services import AuthServices
from apps.api.auth.settings import get_auth_settings
from apps.api.auth.tokens import TokenClaims, decode_token, issue_token
from packages.core.clock import Clock

StreamClaims = TokenClaims


def issue_stream_token(*, user_id: str, sid: str, ver: int, clock: Clock) -> str:
    """Token luồng mới, sống `STREAM_TOKEN_TTL_S`."""
    token, _ = issue_token(
        "stream", user_id=user_id, sid=sid, ver=ver, now=clock.now(), ttl_s=get_auth_settings().stream_token_ttl_s
    )
    return token


def verify_stream_token(services: AuthServices, token: str) -> StreamClaims:
    """Claim của token luồng, `exp` so với đồng hồ của app; hỏng → 401 `UNAUTHENTICATED`."""
    return decode_token("stream", token, services.clock.now())
