"""Người gọi đã xác thực và cổng `TokenVerifier` (BE-00 §2.2, §5, W10).

Khung chỉ khai **cổng**: giải mã JWT, kiểm phiên và vai nằm ở `apps/api/auth`
(B1-01) và vào app qua `apps.api.auth.verifier.build_verifier(app)`. Nhờ vậy
`apps/api/core` không phải nhập `jwt` hay chạm bảng phiên.

Mọi thông tin người thực hiện lấy từ `Principal` (K05, W18); thân request không
bao giờ là nguồn của `user_id`.
"""

from dataclasses import dataclass
from typing import Final, Literal, Protocol, cast, get_args

from starlette.requests import Request

from packages.core.error_codes import UNAUTHENTICATED
from packages.core.ids import is_id

Role = Literal["admin", "engineer", "viewer"]
ROLES: Final = frozenset(get_args(Role))

FAKE_PREFIX: Final = "fake:"
_FAKE_PARTS: Final = 4


@dataclass(frozen=True, slots=True)
class Principal:
    """Người gọi của một request đã xác thực; vai lấy từ DB/cache, không từ claim (K34)."""

    user_id: str
    session_id: str
    role: Role

    def __post_init__(self) -> None:
        if not is_id("usr", self.user_id):
            raise ValueError(f"user_id sai mẫu usr_<ULID>: {self.user_id!r}")
        if not self.session_id:
            raise ValueError("session_id không được rỗng")
        if self.role not in ROLES:
            raise ValueError(f"vai lạ: {self.role!r}")


class TokenVerifier(Protocol):
    """Đổi access token thành `Principal`, hoặc ném `AppError` 401 (W10, K30).

    Nhận cả `request` để đọc `request.app.state.clock`: PyJWT so giờ thật, còn hiến
    chương đòi so với `Clock` tiêm được (BE-00 §5).
    """

    async def verify(self, token: str, request: Request) -> Principal: ...


class DenyAllTokenVerifier:
    """Mặc định ở `dev`/`ci`/`test` khi chưa có B1-01: mọi token đều 401."""

    async def verify(self, token: str, request: Request) -> Principal:
        raise UNAUTHENTICATED.error()


class FakeTokenVerifier:
    """Token `fake:<usr_…>:<sid>:<role>` — chỉ vào app khi `APP_ENV=test` (BE-00 §2.2)."""

    async def verify(self, token: str, request: Request) -> Principal:
        parts = token.split(":")
        if len(parts) != _FAKE_PARTS or parts[0] != FAKE_PREFIX.rstrip(":"):
            raise UNAUTHENTICATED.error()
        try:
            return Principal(user_id=parts[1], session_id=parts[2], role=_role(parts[3]))
        except ValueError as exc:
            raise UNAUTHENTICATED.error() from exc


def _role(value: str) -> Role:
    """Ép chuỗi về `Role`; `Principal.__post_init__` từ chối giá trị lạ."""
    if value not in ROLES:
        raise ValueError(f"vai lạ: {value!r}")
    return cast("Role", value)


def fake_token(principal: Principal) -> str:
    """Token mà `FakeTokenVerifier` nhận cho một `Principal` (fixture của test dùng)."""
    return f"{FAKE_PREFIX}{principal.user_id}:{principal.session_id}:{principal.role}"


def current_principal(request: Request) -> Principal:
    """Dependency: người gọi của route **được bảo vệ** (`AppRoute` đã gắn trước khi đọc thân)."""
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):
        raise RuntimeError("current_principal chỉ dùng được trên route được bảo vệ")
    return principal
