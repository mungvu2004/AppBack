"""`POST /api/auth/password-reset`, `/password-reset/confirm`, `/invitations/accept` (B1-03 [2], HOP-DONG-MOI §3).

Ba route **công khai**, đều đòi `Origin` khớp `PUBLIC_BASE_URL` (case_gate áp C24 cho cả
nhóm C, kể cả N8 dù N8 không đặt/đọc cookie) và cùng chung một hạn mức `recovery_ip`.

- **N8** luôn 204 dù email có tồn tại hay không (C27, chống dò): tra người và tra token còn
  hiệu lực chạy **cùng dạng truy vấn** ở cả hai nhánh; nhánh không có người chạy truy vấn giả
  rồi PING `redis-broker` sau commit để cân thời gian với `send_task` thật của nhánh có
  người. Người `active` chưa có token `password_reset` còn hiệu lực (hoặc token đó đã qua
  cooldown) mới được cấp token mới; còn lại (không tồn tại/`pending`/`disabled`/trong
  cooldown) không tạo gì (C28).
- **N9**, **N10** đọc token trước, `await db.rollback()` rồi mới băm mật khẩu (K36), sau đó
  ghi trong một giao dịch theo thứ tự khoá `users` → `one_time_tokens` → `refresh_sessions`.
  Mọi đường hỏng (token không thấy/sai mục đích/hết hạn/đã dùng, người không đúng trạng
  thái) đều 422 mã riêng của route — không bao giờ 401 (K30).

Mọi quyết định (if/else) đọc dữ liệu vừa `await` được tách vào hàm **đồng bộ** riêng, gọi
qua đúng một dòng ngay sau `await` — coverage không đo được nhánh nằm ngay sau `await` của
SQLAlchemy async/greenlet (NO-130); hàm đồng bộ thuần thì đo bình thường.
"""

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, Final, Literal

from fastapi import Depends
from pydantic import Field, field_validator
from sqlalchemy import Row, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from apps.api.auth.cookies import clear_auth_cookies, refresh_cookie_of
from apps.api.auth.emails import validate_wire_email
from apps.api.auth.passwords import MIN_PASSWORD_LENGTH, hash_password
from apps.api.auth.sessions import revoke_sessions, start_session
from apps.api.auth_recovery.settings import get_recovery_settings
from apps.api.auth_recovery.tokens import active_clause, consume_token, find_active_token, issue_token, revoke_tokens
from apps.api.core.deps import ClockDep, DbSession
from apps.api.core.origin import require_origin
from apps.api.core.ratelimit import key_ip, rate_limit
from apps.api.core.routing import public_router
from apps.api.core.wire import WireRequest
from packages.core.clock import Clock
from packages.core.errors import ERRORS, ErrorCode
from packages.core.text import normalize_email
from packages.db.hooks import on_after_commit
from packages.db.models.auth import User
from packages.db.models.auth_recovery import OneTimeToken
from packages.messaging.redis import ProcessLocal, SyncRedis, broker_redis_sync

router = public_router(prefix="/auth", tags=["auth-recovery"])
ROUTERS: Final = (router,)

PASSWORD_RESET_TOKEN_INVALID: Final = ERRORS.define("PASSWORD_RESET_TOKEN_INVALID", 422)
INVITATION_TOKEN_INVALID: Final = ERRORS.define("INVITATION_TOKEN_INVALID", 422)

TOKEN_MAX_LEN: Final = 512
FULL_NAME_MAX: Final = 120
_NOBODY_ID: Final = "usr_00000000000000000000000000"
"""Id không bao giờ khớp thật — giữ đúng dạng truy vấn của nhánh "có người" cho C27."""

_BIDI_OVERRIDE: Final = frozenset(chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))
"""U+202A-202E (LRE/RLE/PDF/LRO/RLO) và U+2066-2069 (LRI/RLI/FSI/PDI) — cấm trong `fullName`."""


def _validate_full_name(value: str) -> str:
    """NFC + trim; 1-120 ký tự; cấm ký tự điều khiển (Cc) và ký tự đảo chiều song hướng."""
    normalized = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(normalized) <= FULL_NAME_MAX:
        raise ValueError("fullName sai độ dài")
    if any(unicodedata.category(ch) == "Cc" or ch in _BIDI_OVERRIDE for ch in normalized):
        raise ValueError("fullName chứa ký tự cấm")
    return normalized


class PasswordResetRequestBody(WireRequest):
    """Thân N8: `PasswordResetRequestSchema {email}` của FE."""

    email: str

    @field_validator("email")
    @classmethod
    def _wire_email(cls, value: str) -> str:
        """Sai dạng → 422 `field:"email"` (K37), như `SignInBody`."""
        return validate_wire_email(value)


class PasswordResetConfirmBody(WireRequest):
    """Thân N9: `PasswordResetConfirmSchema {token, newPassword}`."""

    token: Annotated[str, Field(min_length=1, max_length=TOKEN_MAX_LEN)]
    new_password: Annotated[str, Field(min_length=MIN_PASSWORD_LENGTH)]


class AcceptInvitationBody(WireRequest):
    """Thân N10: `AcceptInvitationSchema {token, fullName, password}`."""

    token: Annotated[str, Field(min_length=1, max_length=TOKEN_MAX_LEN)]
    full_name: str
    password: Annotated[str, Field(min_length=MIN_PASSWORD_LENGTH)]

    @field_validator("full_name")
    @classmethod
    def _wire_full_name(cls, value: str) -> str:
        """422 `field:"fullName"` khi rỗng, > 120 ký tự, hay chứa ký tự cấm."""
        return _validate_full_name(value)


@dataclass(frozen=True, slots=True)
class _RecoveryAccount:
    """Người dùng đọc cho N8 — chỉ đủ để quyết định phát token, không mang gì nhạy cảm."""

    id: str
    status: str


@dataclass(frozen=True, slots=True)
class _AcceptedUser:
    """Người vừa nhận lời mời — đủ cho `start_session` (giao thức `SessionOwner`)."""

    id: str
    token_version: int


_recovery_ip_limit: Final = rate_limit(
    "recovery_ip",
    limit=lambda: get_recovery_settings().recovery_ip_limit,
    window_s=lambda: get_recovery_settings().recovery_ip_window_s,
    key=key_ip,
    store="safe",
    on_error="closed",
)
"""Hạn mức theo IP dùng chung cho cả ba route (mẫu `auth/router.py:121-129`)."""


def _require(value: bool, code: ErrorCode) -> None:
    """Ném `code.error()` (422) khi `value` sai — hàm thuần, gọi ngay sau `await` (NO-130)."""
    if not value:
        raise code.error()


def _identity_or_422(token: OneTimeToken | None, code: ErrorCode) -> tuple[str, str]:
    """`(id, userId)` của token vừa tra, hay ném `code.error()` khi không thấy — một dòng sau `await` (NO-130)."""
    if token is None:
        raise code.error()
    return token.id, token.user_id


async def _find_account(db: AsyncSession, email: str) -> _RecoveryAccount | None:
    """Người chưa xoá mềm theo `email_normalized` (C16), hay `None`."""
    row = (
        await db.execute(
            select(User.id, User.status).where(
                User.email_normalized == normalize_email(email), User.deleted_at.is_(None)
            )
        )
    ).one_or_none()
    return _RecoveryAccount(*row) if row is not None else None


async def _active_reset_token(db: AsyncSession, user_id: str, now: datetime) -> OneTimeToken | None:
    """Token `password_reset` còn hiệu lực của một người; dùng nguyên dạng làm truy vấn giả (C27)."""
    stmt = select(OneTimeToken).where(
        OneTimeToken.user_id == user_id, OneTimeToken.purpose == "password_reset", active_clause(now)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _reset_eligible(
    account: _RecoveryAccount, existing: OneTimeToken | None, now: datetime, cooldown: timedelta, ttl: timedelta
) -> bool:
    """`active` và (chưa có token còn hiệu lực hoặc token đó đã qua cooldown) (C28).

    Lúc phát tính từ `expires_at - ttl` chứ không phải `created_at` (mặc định của
    `TimestampMixin` là `func.now()` phía DB, không đi theo `Clock` tiêm được — K20).
    """
    if account.status != "active":
        return False
    return existing is None or (existing.expires_at - ttl) <= now - cooldown


type _ResetPlan = Literal["issue", "ping", "noop"]


def _query_id_for(account: _RecoveryAccount | None) -> str:
    """Id để tra token còn hiệu lực: người thật hay `_NOBODY_ID` (giữ đúng dạng truy vấn, C27)."""
    return account.id if account is not None else _NOBODY_ID


def _plan_reset(
    account: _RecoveryAccount | None,
    existing: OneTimeToken | None,
    now: datetime,
    cooldown: timedelta,
    ttl: timedelta,
) -> _ResetPlan:
    """Quyết định N8 từ dữ liệu đã đọc — hàm thuần, gọi ngay sau `await` (NO-130)."""
    if account is None:
        return "ping"
    if _reset_eligible(account, existing, now, cooldown, ttl):
        return "issue"
    return "noop"


_broker_client: Final = ProcessLocal[SyncRedis](broker_redis_sync)
"""Một client Redis đồng bộ dùng lại cả tiến trình (NO-145): `broker_redis_sync()` dựng pool
mới mỗi lời gọi, và đường PING chạy cho **mọi** request N8 không cấp token — đúng phần lưu
lượng mà kẻ dò sinh ra. Dựng-mở-đóng mỗi lượt vừa tốn một vòng TCP connect/close, vừa làm
hỏng chính mục đích cân thời gian (connect mới không tương đương `LPUSH` qua kết nối pool mà
`send_task` dùng). `ProcessLocal` tự dựng lại khi PID đổi (an toàn qua `fork`, khuôn
`packages/messaging/tasks.py::_delivery_client`)."""


def _ping_broker() -> None:
    """PING `redis-broker` qua client dùng chung: cân thời gian nhánh "không người" với `send_task` thật (C27)."""
    _broker_client.get().ping()


async def _apply_reset_plan(db: AsyncSession, clock: Clock, user_id: str, plan: _ResetPlan) -> None:
    """Thực thi quyết định của `_plan_reset`: phát token, hay chỉ cân thời gian (C27).

    Mọi nhánh không `issue` (kể cả `"noop"` — người tồn tại nhưng `pending`/`disabled`/trong
    cooldown) đều PING để cân thời gian với `send_task` thật, không chỉ nhánh "không người".
    """
    if plan == "issue":
        await issue_token(db, user_id=user_id, purpose="password_reset", clock=clock)
    else:
        on_after_commit(db, _ping_broker)


@router.post(
    "/password-reset",
    status_code=204,
    response_class=Response,
    response_model=None,
    dependencies=[Depends(require_origin), Depends(_recovery_ip_limit)],
)
async def auth_request_password_reset(body: PasswordResetRequestBody, db: DbSession, clock: ClockDep) -> None:
    """N8: luôn 204 (C27); người `active` đủ điều kiện được cấp token mới, còn lại không tạo gì."""
    settings = get_recovery_settings()
    cooldown = timedelta(minutes=settings.password_reset_cooldown_min)
    ttl = timedelta(minutes=settings.password_reset_ttl_min)
    now = clock.now()
    await db.execute(text("SET LOCAL synchronous_commit = off"))
    account = await _find_account(db, body.email)
    existing = await _active_reset_token(db, _query_id_for(account), now)
    plan = _plan_reset(account, existing, now, cooldown, ttl)
    await _apply_reset_plan(db, clock, _query_id_for(account), plan)
    return None


async def _consume_if_row_matched(db: AsyncSession, row: object, *, token_id: str, now: datetime) -> bool:
    """0 dòng `RETURNING` → `False`; còn lại `consume_token` phân xử (hàm riêng, NO-130)."""
    if row is None:
        return False
    return await consume_token(db, token_id=token_id, now=now)


async def _finish_password_reset(db: AsyncSession, *, user_id: str, token_id: str, new_hash: str, clock: Clock) -> bool:
    """`UPDATE users` (còn `active`) rồi `consume_token`, thứ tự khoá `users` → `one_time_tokens`."""
    now = clock.now()
    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.status == "active", User.deleted_at.is_(None))
        .values(password_hash=new_hash)
        .returning(User.id)
        .execution_options(synchronize_session=False)
    )
    return await _consume_if_row_matched(db, result.scalar_one_or_none(), token_id=token_id, now=now)


async def _cleanup_password_reset(db: AsyncSession, clock: Clock, response: Response, user_id: str) -> None:
    """Thu hồi mọi phiên, mọi token `password_reset` khác, rồi xoá cookie (hàm riêng, NO-130)."""
    await revoke_sessions(db, user_id=user_id, reason="password_reset", clock=clock)
    await revoke_tokens(db, user_id=user_id, purpose="password_reset", clock=clock)
    clear_auth_cookies(response)


@router.post(
    "/password-reset/confirm",
    status_code=204,
    response_class=Response,
    response_model=None,
    dependencies=[Depends(require_origin), Depends(_recovery_ip_limit)],
)
async def auth_confirm_password_reset(
    body: PasswordResetConfirmBody, response: Response, db: DbSession, clock: ClockDep
) -> None:
    """N9: xác nhận đặt lại mật khẩu; mọi đường hỏng → 422 `PASSWORD_RESET_TOKEN_INVALID` (K30)."""
    token = await find_active_token(db, token=body.token, purpose="password_reset", now=clock.now())
    token_id, user_id = _identity_or_422(token, PASSWORD_RESET_TOKEN_INVALID)
    await db.rollback()  # K36: trả kết nối về pool trước khi băm
    fresh_hash = await hash_password(body.new_password)
    ok = await _finish_password_reset(db, user_id=user_id, token_id=token_id, new_hash=fresh_hash, clock=clock)
    _require(ok, PASSWORD_RESET_TOKEN_INVALID)
    return await _cleanup_password_reset(db, clock, response, user_id)


def _accepted_row(row: Row[tuple[str, int]] | None) -> tuple[str, int] | None:
    """`(id, tokenVersion)` của dòng `RETURNING`, hay `None` (0 dòng) — hàm thuần (NO-130)."""
    return None if row is None else (row[0], row[1])


async def _consume_if_accepted(
    db: AsyncSession, accepted: tuple[str, int] | None, *, token_id: str, now: datetime
) -> _AcceptedUser | None:
    """0 dòng `RETURNING` → `None`; còn lại `consume_token` phân xử (hàm riêng, NO-130)."""
    if accepted is None:
        return None
    consumed = await consume_token(db, token_id=token_id, now=now)
    return _AcceptedUser(id=accepted[0], token_version=accepted[1]) if consumed else None


async def _finish_invitation(
    db: AsyncSession, *, user_id: str, token_id: str, name: str, new_hash: str, clock: Clock
) -> _AcceptedUser | None:
    """`UPDATE users` (`pending` → `active`) rồi `consume_token`; `None` là mọi lỗi 422."""
    now = clock.now()
    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.status == "pending", User.deleted_at.is_(None))
        .values(name=name, password_hash=new_hash, status="active")
        .returning(User.id, User.token_version)
        .execution_options(synchronize_session=False)
    )
    return await _consume_if_accepted(db, _accepted_row(result.one_or_none()), token_id=token_id, now=now)


def _require_accepted(accepted: _AcceptedUser | None, code: ErrorCode) -> _AcceptedUser:
    """`accepted`, hay ném `code.error()` khi lời mời không dùng được (NO-130)."""
    if accepted is None:
        raise code.error()
    return accepted


def _client_host(request: Request) -> str | None:
    """IP người gọi, ghi vào `created_ip` của phiên N10 mở (không gom bucket như hạn mức)."""
    return request.client.host if request.client is not None else None


@router.post(
    "/invitations/accept",
    status_code=204,
    response_class=Response,
    response_model=None,
    dependencies=[Depends(require_origin), Depends(_recovery_ip_limit)],
)
async def auth_accept_invitation(
    body: AcceptInvitationBody, request: Request, response: Response, db: DbSession, clock: ClockDep
) -> None:
    """N10: nhận lời mời, mở phiên; K7=B — đường vào duy nhất cho người mới."""
    token = await find_active_token(db, token=body.token, purpose="invite", now=clock.now())
    token_id, user_id = _identity_or_422(token, INVITATION_TOKEN_INVALID)
    await db.rollback()  # K36
    fresh_hash = await hash_password(body.password)
    accepted = await _finish_invitation(
        db, user_id=user_id, token_id=token_id, name=body.full_name, new_hash=fresh_hash, clock=clock
    )
    account = _require_accepted(accepted, INVITATION_TOKEN_INVALID)
    await start_session(
        db,
        response,
        user=account,
        remember=False,
        ip=_client_host(request),
        clock=clock,
        replaced_cookie=refresh_cookie_of(request),
    )
    return None
