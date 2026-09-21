"""JWT access/luồng và token refresh xoay vòng tất định (BE-00 §5, K10, K20, K35).

**JWT** (HS256): claim đúng `sub`, `sid`, `ver`, `iat`, `exp`, `aud` — **không** có vai
(K04, K34: vai đọc từ DB mỗi request). Ký bằng `current_key`, kiểm lần lượt với
`verification_keys` (xoay `SECRET_KEY` không đăng xuất ai). PyJWT so `exp`/`iat` với giờ
**thật**, nên cả ba kiểm thời gian của nó bị tắt và so lại với `Clock` tiêm (K20).

**Refresh**: token 32 byte ngẫu nhiên (base64url, 43 ký tự) trong cookie `<sid>.<token>`.
Token kế tiếp = `base64url(HMAC-SHA256(K_refresh, token))`, tính lại được từ token trước,
nên DB chỉ giữ SHA-256 của token (hiện hành và ngay trước) — không bao giờ bản rõ.
"""

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal
from uuid import UUID

import jwt
from jwt.types import Options

from packages.core.error_codes import UNAUTHENTICATED
from packages.core.ids import is_id
from packages.core.keys import current_key, verification_keys

type Audience = Literal["access", "stream"]

ALGORITHM: Final = "HS256"
REQUIRED_CLAIMS: Final = ("exp", "iat", "sub", "sid", "ver")
IAT_LEEWAY_S: Final = 30
"""`iat` được phép sớm hơn đồng hồ tối đa 30 s (lệch giờ giữa các tiến trình API)."""

REFRESH_TOKEN_BYTES: Final = 32
_COOKIE_RE: Final = re.compile(
    r"(?P<sid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.(?P<token>[A-Za-z0-9_-]{43})"
)
_DECODE_OPTIONS: Final[Options] = {
    "verify_exp": False,
    "verify_iat": False,
    "verify_nbf": False,
    "require": list(REQUIRED_CLAIMS),
}


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Claim đã kiểm của một JWT access hay luồng."""

    user_id: str
    sid: str
    ver: int
    iat: int
    exp: int


def issue_token(
    audience: Audience, *, user_id: str, sid: str, ver: int, now: datetime, ttl_s: int
) -> tuple[str, datetime]:
    """JWT mới và thời điểm hết hạn của nó (`exp` là giây nguyên, nên `expiresAt` luôn `.000Z`)."""
    iat = int(now.timestamp())
    exp = iat + ttl_s
    claims = {"sub": user_id, "sid": sid, "ver": ver, "iat": iat, "exp": exp, "aud": audience}
    return jwt.encode(claims, current_key(audience), algorithm=ALGORITHM), datetime.fromtimestamp(exp, UTC)


def decode_token(audience: Audience, token: str, now: datetime) -> TokenClaims:
    """Giải và kiểm một JWT; hỏng chữ ký, `aud`, `alg`, claim hay thời gian → 401 `UNAUTHENTICATED`.

    Chỉ lỗi **chữ ký** mới thử khoá kế tiếp: token hỏng dạng hay sai `aud` thì khoá nào cũng
    hỏng như nhau.
    """
    for key in verification_keys(audience):
        try:
            payload = jwt.decode(token, key, algorithms=[ALGORITHM], audience=audience, options=_DECODE_OPTIONS)
        except jwt.InvalidSignatureError:
            continue
        except jwt.PyJWTError as exc:
            raise UNAUTHENTICATED.error() from exc
        return _checked(payload, now)
    raise UNAUTHENTICATED.error()


def _checked(payload: dict[str, object], now: datetime) -> TokenClaims:
    """Kiểu của từng claim và hai mốc thời gian so với `Clock` tiêm."""
    sub, sid, ver, iat, exp = (payload[name] for name in ("sub", "sid", "ver", "iat", "exp"))
    if not (isinstance(sub, str) and is_id("usr", sub) and isinstance(sid, str) and is_session_id(sid)):
        raise UNAUTHENTICATED.error()
    if not (isinstance(ver, int) and isinstance(iat, int) and isinstance(exp, int)):
        raise UNAUTHENTICATED.error()
    moment = now.timestamp()
    if any(isinstance(value, bool) for value in (ver, iat, exp)):
        raise UNAUTHENTICATED.error()  # `bool` là lớp con của `int`: `true` không phải số
    if ver < 0 or exp <= moment or iat > moment + IAT_LEEWAY_S:
        raise UNAUTHENTICATED.error()
    return TokenClaims(user_id=sub, sid=sid, ver=ver, iat=iat, exp=exp)


def is_session_id(value: str) -> bool:
    """`sid` là UUID dạng chuẩn chữ thường — đúng dạng `str(uuid4())` in ra."""
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def new_refresh_token() -> str:
    """Token refresh mới: 32 byte ngẫu nhiên, base64url không đệm."""
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def next_refresh_token(token: str, key: bytes) -> str:
    """Token kế tiếp của chuỗi xoay: `base64url(HMAC-SHA256(key, token))`, tất định."""
    digest = hmac.new(key, token.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def token_hash(token: str) -> str:
    """SHA-256 hex của token — dạng duy nhất của token nằm trong DB."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def refresh_cookie_value(sid: UUID, token: str) -> str:
    """Giá trị cookie refresh `<sid>.<token>` (BE-00 §5)."""
    return f"{sid}.{token}"


def parse_refresh_cookie(value: str | None) -> tuple[UUID, str] | None:
    """`(sid, token)` của cookie refresh, hay `None` khi thiếu hoặc sai mẫu."""
    if value is None:
        return None
    match = _COOKIE_RE.fullmatch(value)
    if match is None:
        return None
    return UUID(match.group("sid")), match.group("token")
