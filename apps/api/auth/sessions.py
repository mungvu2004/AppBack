"""Phiên refresh: mở, xoay, thu hồi, và kiểm phiên ở mỗi request (BE-00 §5, K10, K35).

**Xoay tất định.** Cookie `<sid>.<token>`; token kế tiếp là `HMAC(K_refresh, token)`. DB
giữ SHA-256 của token hiện hành (`current`) và ngay trước (`previous`) cùng `rotated_at`:

- token = `current`: đã xoay trong `REFRESH_GRACE_S` → trả lại chính nó (không xoay lần
  hai); không thì xoay bằng `UPDATE … WHERE current_token_hash = :h` (so-và-đặt);
- token = `previous` trong ân hạn → trả token kế tiếp **tính lại**, không ghi DB: mọi thẻ
  cùng lượt nhận cùng một cookie (C19); ngoài ân hạn → **dùng lại**, thu hồi (C20);
- token lạ: tiến chuỗi HMAC ≤ `REFRESH_CHAIN_LOOKBACK` bước; chạm `current` là dùng lại,
  không chạm thì 401 **không ghi DB** — kẻ chỉ biết `sid` không thu hồi được phiên người khác.

Thu hồi và hết hạn kiểm **trước** mọi nhánh. Từ chối trả `RefreshDenied` chứ không ném:
`AppRoute` rollback khi có ngoại lệ, và lệnh thu hồi vì dùng lại phải được commit.

**Kiểm mỗi request.** `check_session` đọc ảnh chụp `auth:principal:{sid}` ở `redis-cache`
(≤ 5 s), trượt thì đọc Postgres bằng session ngắn riêng. Mọi lệnh thu hồi xoá ảnh chụp
**sau commit** bằng client Redis đồng bộ; xoá hỏng thì nó tự hết sau TTL (BE-00 §5).
"""

import hmac
import ipaddress
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import Final, Literal, Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import Response

from apps.api.auth.cookies import set_refresh_cookie, set_stream_cookie
from apps.api.auth.services import AuthServices, soft_redis
from apps.api.auth.settings import AuthSettings, get_auth_settings
from apps.api.auth.stream_tokens import issue_stream_token
from apps.api.auth.tokens import (
    is_session_id,
    new_refresh_token,
    next_refresh_token,
    parse_refresh_cookie,
    refresh_cookie_value,
    token_hash,
)
from apps.api.core.auth import ROLES, Principal, Role
from packages.core.clock import Clock
from packages.core.error_codes import SESSION_REVOKED, UNAUTHENTICATED
from packages.core.errors import ErrorCode
from packages.core.instants import parse_wire, to_wire
from packages.core.keys import current_key, verification_keys
from packages.db.errors import translate_db_error
from packages.db.hooks import on_after_commit
from packages.db.models.auth import RefreshSession, RevokeReason, User
from packages.messaging.redis import AsyncRedis, cache_redis_sync

_log: Final = logging.getLogger(__name__)

REMEMBER_IDLE: Final = timedelta(days=7)
REMEMBER_ABSOLUTE: Final = timedelta(days=30)
SHORT_IDLE: Final = timedelta(hours=12)
SHORT_ABSOLUTE: Final = timedelta(hours=24)
LAST_ACTIVE_EVERY: Final = timedelta(minutes=5)
MAX_CACHE_DROP: Final = 500
"""Trần số ảnh chụp xoá sau `bump_token_version`: một người hiếm khi có quá vài chục phiên
sống; phần vượt trần tự hết sau TTL cache (≤ 5 s). Nâng khi có người dùng máy dùng chung."""

DELETED: Final = "deleted"
"""Trạng thái trong ảnh chụp của người đã xoá mềm (cột `status` giữ nguyên khi xoá)."""


class SessionOwner(Protocol):
    """Người mở phiên: dòng `User` của ORM hay bản ghi đọc riêng đều dùng được."""

    @property
    def id(self) -> str:
        """`usr_…` của người dùng."""
        ...

    @property
    def token_version(self) -> int:
        """`ver` ghi vào token luồng cấp cùng phiên."""
        ...


@dataclass(frozen=True, slots=True)
class SessionState:
    """Một phiên và người sở hữu nó, đọc trong một câu `SELECT … JOIN`."""

    sid: UUID
    current_hash: str
    previous_hash: str | None
    rotated_at: datetime | None
    remember: bool
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked: bool
    user_id: str
    name: str
    email: str
    role: str
    status: str
    token_version: int
    deleted: bool

    def alive(self, now: datetime) -> bool:
        """Chưa thu hồi, chưa hết idle, chưa hết hạn tuyệt đối."""
        return not self.revoked and self.idle_expires_at > now and self.absolute_expires_at > now

    def owner_usable(self) -> bool:
        """Người sở hữu còn `active` và chưa bị xoá mềm."""
        return self.status == "active" and not self.deleted


@dataclass(frozen=True, slots=True)
class Refreshed:
    """Refresh thành công: token của cookie trả về và hạn idle ghi trong DB."""

    state: SessionState
    token: str
    idle_expires_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshDenied:
    """Refresh bị từ chối với một mã 401; mọi ghi DB (thu hồi) đã nằm trong giao dịch."""

    code: ErrorCode


@dataclass(frozen=True, slots=True)
class _Rotate:
    """Quyết định "xoay": token trình lên đúng là `current` và đã ra khỏi ân hạn."""

    state: SessionState


def lifetimes(remember: bool) -> tuple[timedelta, timedelta]:
    """(idle, tuyệt đối): ghi nhớ 7 ngày/30 ngày, không ghi nhớ 12 giờ/24 giờ (BE-00 §5)."""
    return (REMEMBER_IDLE, REMEMBER_ABSOLUTE) if remember else (SHORT_IDLE, SHORT_ABSOLUTE)


def principal_key(sid: str) -> str:
    """Khoá ảnh chụp phiên ở `redis-cache`."""
    return f"auth:principal:{sid}"


def _drop_cached(keys: tuple[str, ...]) -> None:
    """Chạy sau commit trên executor của B0-03: xoá ảnh chụp bằng client đồng bộ (trần 0,5 s)."""
    client = cache_redis_sync()
    try:
        client.delete(*keys)
    finally:
        client.close()


def _drop_cached_after_commit(db: AsyncSession, sids: Iterable[str]) -> None:
    """Hẹn xoá ảnh chụp của các phiên **sau** khi giao dịch commit; rollback thì bỏ hẹn."""
    keys = tuple(principal_key(sid) for sid in sids)
    if keys:
        on_after_commit(db, partial(_drop_cached, keys))


def _inet(ip: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """IP hợp lệ cho cột `inet`; chuỗi không phải IP (client ASGI lạ) → không ghi."""
    if ip is None:
        return None
    try:
        return ipaddress.ip_address(ip)
    except ValueError:
        return None


def issue_session_cookies(
    response: Response,
    *,
    sid: UUID,
    token: str,
    remember: bool,
    idle_expires_at: datetime,
    user_id: str,
    ver: int,
    clock: Clock,
) -> None:
    """Đặt cookie refresh (có `Max-Age` tới hạn idle chỉ khi ghi nhớ) và cookie luồng mới."""
    now = clock.now()
    max_age = max(0, int((idle_expires_at - now).total_seconds())) if remember else None
    set_refresh_cookie(response, refresh_cookie_value(sid, token), max_age=max_age)
    stream = issue_stream_token(user_id=user_id, sid=str(sid), ver=ver, clock=clock)
    set_stream_cookie(response, stream, max_age=get_auth_settings().stream_token_ttl_s)


async def start_session(
    db: AsyncSession,
    response: Response,
    *,
    user: SessionOwner,
    remember: bool,
    ip: str | None,
    clock: Clock,
    replaced_cookie: str | None = None,
) -> str:
    """Mở phiên mới, đặt hai cookie, trả `sid`; cookie refresh cũ còn hợp lệ bị thu hồi (`replaced`).

    Trình duyệt dùng chung: người sau đăng nhập đè người trước, phiên của người trước phải
    chết theo chứ không chỉ mất cookie (BE-00 §5 "Mở phiên mới").
    """
    if replaced_cookie is not None:
        await revoke_by_cookie(db, replaced_cookie, reason="replaced", clock=clock)
    now = clock.now()
    sid, token = uuid4(), new_refresh_token()
    idle, absolute = lifetimes(remember)
    await db.execute(
        insert(RefreshSession).values(
            id=sid,
            user_id=user.id,
            current_token_hash=token_hash(token),
            remember=remember,
            idle_expires_at=now + idle,
            absolute_expires_at=now + absolute,
            created_ip=_inet(ip),
        )
    )
    issue_session_cookies(
        response,
        sid=sid,
        token=token,
        remember=remember,
        idle_expires_at=now + idle,
        user_id=user.id,
        ver=user.token_version,
        clock=clock,
    )
    return str(sid)


async def revoke_by_cookie(db: AsyncSession, cookie: str | None, *, reason: RevokeReason, clock: Clock) -> str | None:
    """Thu hồi phiên còn sống mà cookie khớp `current` hoặc `previous`; trả `sid` đã thu hồi hay `None`."""
    parsed = parse_refresh_cookie(cookie)
    if parsed is None:
        return None
    sid, token = parsed
    presented, now = token_hash(token), clock.now()
    result = await db.execute(
        update(RefreshSession)
        .where(
            RefreshSession.id == sid,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.idle_expires_at > now,
            RefreshSession.absolute_expires_at > now,
            or_(RefreshSession.current_token_hash == presented, RefreshSession.previous_token_hash == presented),
        )
        .values(revoked_at=now, revoked_reason=reason)
        .returning(RefreshSession.id)
        .execution_options(synchronize_session=False)
    )
    revoked = result.scalar_one_or_none()
    if revoked is None:
        return None
    _drop_cached_after_commit(db, [str(revoked)])
    return str(revoked)


async def revoke_sessions(
    db: AsyncSession, *, user_id: str, reason: RevokeReason, clock: Clock, except_sid: str | None = None
) -> list[str]:
    """Thu hồi mọi phiên sống của một người (trừ `except_sid`) trong giao dịch của người gọi."""
    conditions = [RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None)]
    if except_sid is not None:
        conditions.append(RefreshSession.id != UUID(except_sid))
    result = await db.execute(
        update(RefreshSession)
        .where(*conditions)
        .values(revoked_at=clock.now(), revoked_reason=reason)
        .returning(RefreshSession.id)
        .execution_options(synchronize_session=False)
    )
    sids = [str(sid) for sid in result.scalars()]
    _drop_cached_after_commit(db, sids)
    return sids


async def bump_token_version(db: AsyncSession, user_id: str) -> None:
    """`token_version + 1`: mọi access token đang lưu hành của người này hết giá trị sau commit."""
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(token_version=User.token_version + 1)
        .execution_options(synchronize_session=False)
    )
    live = await db.execute(
        select(RefreshSession.id)
        .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
        .limit(MAX_CACHE_DROP)
    )
    _drop_cached_after_commit(db, [str(sid) for sid in live.scalars()])


async def read_state(db: AsyncSession, sid: UUID) -> SessionState | None:
    """Phiên `sid` cùng người sở hữu, hay `None` khi không có phiên đó."""
    row = (
        await db.execute(
            select(
                RefreshSession.current_token_hash,
                RefreshSession.previous_token_hash,
                RefreshSession.rotated_at,
                RefreshSession.remember,
                RefreshSession.idle_expires_at,
                RefreshSession.absolute_expires_at,
                RefreshSession.revoked_at,
                User.id,
                User.name,
                User.email,
                User.role,
                User.status,
                User.token_version,
                User.deleted_at,
            )
            .join(User, User.id == RefreshSession.user_id)
            .where(RefreshSession.id == sid)
        )
    ).one_or_none()
    if row is None:
        return None
    current, previous, rotated_at, remember, idle, absolute, revoked_at, *owner = row
    user_id, name, email, role, status, version, deleted_at = owner
    return SessionState(
        sid=sid,
        current_hash=current,
        previous_hash=previous,
        rotated_at=rotated_at,
        remember=remember,
        idle_expires_at=idle,
        absolute_expires_at=absolute,
        revoked=revoked_at is not None,
        user_id=user_id,
        name=name,
        email=email,
        role=role,
        status=status,
        token_version=version,
        deleted=deleted_at is not None,
    )


async def touch_last_active(db: AsyncSession, user_id: str, now: datetime) -> None:
    """`last_active_at` khi cũ hơn 5 phút; dòng đang bị khoá thì bỏ qua, không bao giờ chờ khoá."""
    stale = (
        select(User.id)
        .where(User.id == user_id, or_(User.last_active_at.is_(None), User.last_active_at < now - LAST_ACTIVE_EVERY))
        # `NO KEY UPDATE`: chỉ ghi `last_active_at`, không chặn `FOR KEY SHARE` mà `INSERT refresh_sessions` (FK) cần.
        .with_for_update(skip_locked=True, key_share=True)
    )
    await db.execute(
        update(User).where(User.id.in_(stale)).values(last_active_at=now).execution_options(synchronize_session=False)
    )


async def _revoke_one(db: AsyncSession, sid: UUID, reason: RevokeReason, now: datetime) -> None:
    """Thu hồi một phiên (dùng lại, người dùng bị vô hiệu) và hẹn xoá ảnh chụp của nó."""
    await db.execute(
        update(RefreshSession)
        .where(RefreshSession.id == sid, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now, revoked_reason=reason)
        .execution_options(synchronize_session=False)
    )
    _drop_cached_after_commit(db, [str(sid)])


def _successor(token: str, current_hash: str) -> str | None:
    """Token kế tiếp của `token` khớp `current` với một khoá kiểm nào đó (xoay `SECRET_KEY` giữa chừng)."""
    for key in verification_keys("refresh"):
        candidate = next_refresh_token(token, key)
        if hmac.compare_digest(token_hash(candidate), current_hash):
            return candidate
    return None


def _walk(token: str, key: bytes, current_hash: str, steps: int) -> bool:
    """Tiến chuỗi HMAC của `token` tối đa `steps` bước bằng một khoá; chạm `current` → `True`."""
    step = token
    for _ in range(steps):
        step = next_refresh_token(step, key)
        if hmac.compare_digest(token_hash(step), current_hash):
            return True
    return False


def _chain_reaches(token: str, current_hash: str, lookback: int) -> bool:
    """`token` là tổ tiên ≤ `lookback` bước của `current` → token cũ của phiên (dùng lại).

    Xoay luôn ký bằng khoá hiện hành, nên chuỗi của một phiên chỉ đổi khoá ở mốc xoay
    `SECRET_KEY`: vài bước đầu bằng một khoá cũ, phần còn lại bằng khoá mới. Dò cả chuỗi một
    khoá lẫn chuỗi đổi khoá **một** lần (≈ `lookback²/2` HMAC mỗi khoá cũ; đo 1,4 ms với một
    khoá cũ, 4,4 ms với ba — chỉ trên đường token lạ, sau hạn mức tầng thất bại). Hai lần xoay
    khoá trong `lookback` bước không dò (R-05: xoay khoá là việc tay, cách nhau hàng tháng;
    nâng cấp = dò mọi thứ tự khoá cũ nếu có lịch xoay tự động).
    """
    newest, *older = verification_keys("refresh")
    if _walk(token, newest, current_hash, lookback):
        return True
    for key in older:
        step = token
        for used in range(1, lookback + 1):
            step = next_refresh_token(step, key)
            if hmac.compare_digest(token_hash(step), current_hash) or _walk(
                step, newest, current_hash, lookback - used
            ):
                return True
    return False


@dataclass(frozen=True, slots=True)
class _Verdict:
    """Token trình lên là gì với phiên: `hand` kèm token phải trả, hay một trong ba nhánh còn lại."""

    kind: Literal["hand", "rotate", "reuse", "unknown"]
    token: str | None = None


def _judge(state: SessionState, token: str, now: datetime, settings: AuthSettings) -> _Verdict:
    """Bước 4-7 của BE-00 §5, thuần tính toán (không đọc, không ghi DB)."""
    presented = token_hash(token)
    grace = state.rotated_at is not None and now - state.rotated_at <= timedelta(seconds=settings.refresh_grace_s)
    if hmac.compare_digest(presented, state.current_hash):
        # Vừa xoay trong ân hạn: không xoay lần hai, trả lại chính cookie hiện hành (K35).
        return _Verdict("hand", token) if grace else _Verdict("rotate")
    if state.previous_hash is not None and hmac.compare_digest(presented, state.previous_hash):
        if not grace:
            return _Verdict("reuse")
        successor = _successor(token, state.current_hash)
        return _Verdict("hand", successor) if successor is not None else _Verdict("unknown")
    reached = _chain_reaches(token, state.current_hash, settings.refresh_chain_lookback)
    return _Verdict("reuse") if reached else _Verdict("unknown")


async def _decide(
    db: AsyncSession, sid: UUID, token: str, clock: Clock, settings: AuthSettings, *, may_rotate: bool
) -> Refreshed | RefreshDenied | _Rotate:
    """Bước 3-8 của BE-00 §5 trên trạng thái vừa đọc; chỉ ghi DB khi phải thu hồi.

    `may_rotate=False` là lượt đọc lại sau một lần xoay hỏng: lúc đó token trình lên không thể
    còn là `current` (xem `refresh_session`); gặp lại là bất biến đã vỡ → `RuntimeError`, không
    lặng lẽ trả thành công.
    """
    state = await read_state(db, sid)
    if state is None:
        return RefreshDenied(UNAUTHENTICATED)
    now = clock.now()
    if not state.alive(now):
        return RefreshDenied(SESSION_REVOKED)
    verdict = _judge(state, token, now, settings)
    if verdict.kind == "unknown":
        return RefreshDenied(UNAUTHENTICATED)
    if verdict.kind == "reuse":
        # Token cũ quay lại: dấu hiệu cookie bị đánh cắp. Chỉ `sid` và người, không bao giờ token (K11).
        _log.warning("refresh_reuse_revoked", extra={"sid": str(sid), "userId": state.user_id})
        await _revoke_one(db, sid, "reuse", now)
        return RefreshDenied(SESSION_REVOKED)
    if not state.owner_usable():
        await _revoke_one(db, sid, DELETED if state.deleted else "disabled", now)
        return RefreshDenied(SESSION_REVOKED)
    if verdict.token is not None:
        return Refreshed(state, verdict.token, state.idle_expires_at)
    if not may_rotate:
        raise RuntimeError("refresh: token vẫn là `current` sau một lần xoay hỏng (bất biến so-và-đặt vỡ)")
    return _Rotate(state)


async def _rotate(db: AsyncSession, state: SessionState, token: str, clock: Clock) -> Refreshed | None:
    """Xoay so-và-đặt; 0 dòng (bên khác vừa xoay hay thu hồi) → `None`, người gọi đọc lại."""
    now = clock.now()
    successor = next_refresh_token(token, current_key("refresh"))
    idle, _ = lifetimes(state.remember)
    idle_at = min(now + idle, state.absolute_expires_at)
    result = await db.execute(
        update(RefreshSession)
        .where(
            RefreshSession.id == state.sid,
            RefreshSession.current_token_hash == state.current_hash,
            RefreshSession.revoked_at.is_(None),
        )
        .values(
            previous_token_hash=RefreshSession.current_token_hash,
            current_token_hash=token_hash(successor),
            rotated_at=now,
            idle_expires_at=idle_at,
        )
        .returning(RefreshSession.id)
        .execution_options(synchronize_session=False)
    )
    if result.scalar_one_or_none() is None:
        return None
    # Ảnh chụp đang cache mang hạn idle cũ; để nó sống thêm 5 s là có thể 401 oan đúng lúc sát hạn.
    _drop_cached_after_commit(db, [str(state.sid)])
    return Refreshed(state, successor, idle_at)


async def refresh_session(
    db: AsyncSession, *, sid: UUID, token: str, clock: Clock, settings: AuthSettings
) -> Refreshed | RefreshDenied:
    """Thuật toán refresh của BE-00 §5 trong giao dịch của request (cookie đã qua kiểm mẫu).

    Xoay hỏng vì 0 dòng nghĩa là một lượt song song vừa xoay **đúng token này** và đã commit
    (lệnh `UPDATE` chờ khoá dòng của nó). Đọc lại thì token này là `previous` trong ân hạn,
    hoặc phiên đã bị thu hồi: lượt hai không bao giờ đòi xoay nữa, nên không có vòng lặp.
    """
    decision = await _decide(db, sid, token, clock, settings, may_rotate=True)
    if not isinstance(decision, _Rotate):
        return decision
    rotated = await _rotate(db, decision.state, token, clock)
    if rotated is not None:
        return rotated
    # `may_rotate=False` ném thay vì trả `_Rotate`, nên kết quả chỉ còn hai kiểu này.
    return cast("Refreshed | RefreshDenied", await _decide(db, sid, token, clock, settings, may_rotate=False))


@dataclass(frozen=True, slots=True)
class _Snapshot:
    """Ảnh chụp phiên ở `redis-cache` — đủ để trả lời `check_session` không cần Postgres."""

    user_id: str
    role: Role
    ver: int
    status: str
    revoked: bool
    idle_exp: datetime
    abs_exp: datetime

    @classmethod
    def of(cls, state: SessionState) -> "_Snapshot":
        """Ảnh chụp của một trạng thái vừa đọc từ Postgres."""
        return cls(
            user_id=state.user_id,
            role=_role(state.role),
            ver=state.token_version,
            status=DELETED if state.deleted else state.status,
            revoked=state.revoked,
            idle_exp=state.idle_expires_at,
            abs_exp=state.absolute_expires_at,
        )

    @classmethod
    def parse(cls, raw: str) -> "_Snapshot":
        """Giải JSON đã cache; thiếu khoá, sai kiểu hay vai lạ → `ValueError`/`KeyError`/`TypeError`."""
        data = json.loads(raw)
        if not isinstance(data["ver"], int) or not isinstance(data["revoked"], bool):
            raise TypeError("ảnh chụp phiên sai kiểu")
        return cls(
            user_id=str(data["userId"]),
            role=_role(data["role"]),
            ver=data["ver"],
            status=str(data["status"]),
            revoked=data["revoked"],
            idle_exp=parse_wire(data["idleExp"]),
            abs_exp=parse_wire(data["absExp"]),
        )

    def dump(self) -> str:
        """JSON `{userId, role, ver, status, revoked, idleExp, absExp}` (B1-01 [5])."""
        return json.dumps(
            {
                "userId": self.user_id,
                "role": self.role,
                "ver": self.ver,
                "status": self.status,
                "revoked": self.revoked,
                "idleExp": to_wire(self.idle_exp),
                "absExp": to_wire(self.abs_exp),
            }
        )

    def admits(self, *, user_id: str, ver: int, now: datetime) -> bool:
        """Phiên sống, người `active`, `ver` khớp `token_version`, phiên đúng của `sub`."""
        alive = not self.revoked and self.idle_exp > now and self.abs_exp > now
        return alive and self.status == "active" and self.ver == ver and self.user_id == user_id


def _role(value: object) -> Role:
    """Vai hợp lệ, hay `ValueError` (dữ liệu cache hỏng không được thành `Principal`)."""
    if value not in ROLES:
        raise ValueError(f"vai lạ: {value!r}")
    return cast("Role", value)


async def _load_snapshot(maker: async_sessionmaker[AsyncSession], sid: str) -> _Snapshot | None:
    """Đọc Postgres bằng session ngắn riêng (không giữ kết nối của request); hỏng → 503 (C13)."""
    try:
        async with maker() as db:
            state = await read_state(db, UUID(sid))
    except Exception as exc:  # phân loại ngay dưới: lỗi không phải hạ tầng được ném lại
        translated = translate_db_error(exc)
        if translated is None:
            raise
        raise translated from exc
    return None if state is None else _Snapshot.of(state)


async def _cached_snapshot(cache: AsyncRedis, sid: str) -> _Snapshot | None:
    """Ảnh chụp trong cache; cache hỏng, trượt hay dữ liệu hỏng đều là "không có" (đọc DB)."""
    raw = await soft_redis(cache.get(principal_key(sid)), "principal_cache_unavailable")
    if not isinstance(raw, str):
        return None
    try:
        return _Snapshot.parse(raw)
    except (ValueError, KeyError, TypeError):
        return None


async def check_session(services: AuthServices, *, user_id: str, sid: str, ver: int) -> Principal:
    """`Principal` của một access token đã giải; phiên chết, người không `active`, `ver` lệch → 401.

    Vai luôn lấy từ ảnh chụp Postgres (≤ `AUTH_PRINCIPAL_CACHE_TTL_S`), không từ token (K34).
    """
    if not is_session_id(sid):
        raise SESSION_REVOKED.error()
    snapshot = await _cached_snapshot(services.cache, sid)
    if snapshot is None:
        snapshot = await _load_snapshot(services.sessionmaker, sid)
        if snapshot is None:
            raise SESSION_REVOKED.error()
        ttl = get_auth_settings().auth_principal_cache_ttl_s
        await soft_redis(services.cache.set(principal_key(sid), snapshot.dump(), ex=ttl), "principal_cache_unavailable")
    if not snapshot.admits(user_id=user_id, ver=ver, now=services.clock.now()):
        raise SESSION_REVOKED.error()
    return Principal(user_id=snapshot.user_id, session_id=sid, role=snapshot.role)
