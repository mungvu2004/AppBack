"""`/api/me`: hồ sơ, đổi mật khẩu, ảnh đại diện (B1-04 [2],[6],[7], HOP-DONG-MOI §3).

N11-N14 đều đọc người dùng **chưa xoá** của `Principal` trước khi làm gì khác; không thấy
(verifier qua nhờ ảnh chụp cũ) → 401 `SESSION_REVOKED`, không 500 (K30, BE-00 §5). N13 đọc
`password_hash` xong `await db.rollback()` **trước** khi băm (K36) — executor riêng của
`apps.api.auth.passwords` không giữ kết nối DB nào. N14 giải mã ảnh dưới semaphore riêng của
`apps/api/me/avatar.py`, `storage.put` **trước** khi ghi `avatar_key` (K22): giao dịch hỏng
sau đó để lại object mồ côi, lịch `purge_avatars` dọn (BE-00 §8).

Mọi quyết định (if/raise) đọc dữ liệu vừa `await` được tách vào hàm **đồng bộ** riêng, gọi
qua đúng một dòng ngay sau `await` — coverage không đo được nhánh nằm ngay sau `await` của
SQLAlchemy async/greenlet (NO-130, mẫu `apps/api/auth_recovery/router.py`).
"""

from dataclasses import dataclass
from typing import Final, Literal, cast
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from apps.api.auth.passwords import hash_password, verify_password
from apps.api.auth.sessions import revoke_sessions
from apps.api.auth_recovery.tokens import revoke_tokens
from apps.api.core.deps import ClockDep, CurrentPrincipal, DbSession, Storage
from apps.api.core.ratelimit import key_user, rate_limit
from apps.api.core.routing import protected_router
from apps.api.me.avatar import MAX_STORED_BYTES, ProcessedAvatar, avatar_url, process_avatar
from apps.api.me.schemas import ChangePasswordBody, MeSchema, ReplaceAvatarBody, UpdateMeBody
from packages.core.clock import Clock
from packages.core.error_codes import SESSION_REVOKED
from packages.core.errors import ERRORS, ErrorCode
from packages.core.ids import new_id
from packages.db.models.auth import RefreshSession, User
from packages.storage.keys import avatar as avatar_key_of
from packages.storage.port import ObjectStorage

router = protected_router(tags=["me"])
ROUTERS: Final = (router,)

CURRENT_PASSWORD_INCORRECT = ERRORS.define("CURRENT_PASSWORD_INCORRECT", 422)

PASSWORD_RATE_LIMIT: Final = 5
PASSWORD_RATE_WINDOW_S: Final = 900
AVATAR_RATE_LIMIT: Final = 10
AVATAR_RATE_WINDOW_S: Final = 900

_COLUMN_OF: Final = {"full_name": "name", "job_title": "job_title", "phone": "phone", "language": "language"}
_NULLABLE_ON_EMPTY: Final = frozenset({"job_title", "phone"})


def _require(value: bool, code: ErrorCode, *, field: str | None = None) -> None:
    """Ném `code.error(field=field)` khi `value` sai — hàm thuần, gọi ngay sau `await` (NO-130)."""
    if not value:
        raise code.error() if field is None else code.error(field=field)


@dataclass(frozen=True, slots=True)
class _ProfileRow:
    """Cột hồ sơ đọc lại để dựng `MeSchema` (N11, sau ghi của N12/N14 — K22)."""

    email: str
    name: str
    job_title: str | None
    phone: str | None
    language: str
    avatar_key: str | None


def _profile_row_of(row: object) -> _ProfileRow | None:
    """`_ProfileRow` từ dòng `SELECT` (hay `None`) — hàm thuần, gọi ngay sau `await` (NO-130)."""
    return None if row is None else _ProfileRow(*row)  # type: ignore[misc]  # Row đúng cột SELECT


async def _load_profile(db: AsyncSession, user_id: str) -> _ProfileRow | None:
    """Hồ sơ của người chưa xoá mềm, hay `None` (phiên còn nhưng người đã bị xoá — K30)."""
    row = (
        await db.execute(
            select(User.email, User.name, User.job_title, User.phone, User.language, User.avatar_key).where(
                User.id == user_id, User.deleted_at.is_(None)
            )
        )
    ).one_or_none()
    return _profile_row_of(row)


def _require_profile(row: _ProfileRow | None) -> _ProfileRow:
    """`row`, hay ném `SESSION_REVOKED` khi không thấy — hàm thuần, gọi ngay sau `await` (NO-130)."""
    if row is None:
        raise SESSION_REVOKED.error()
    return row


async def _me_schema(db: AsyncSession, storage: ObjectStorage, user_id: str) -> MeSchema:
    """`MeSchema` đọc lại từ DB; không thấy người → 401 `SESSION_REVOKED` (K30)."""
    row = _require_profile(await _load_profile(db, user_id))
    return MeSchema(
        email=row.email,
        full_name=row.name,
        job_title=row.job_title,
        phone=row.phone,
        language=cast("Literal['vi', 'en']", row.language),
        avatar_url=await avatar_url(storage, row.avatar_key),
    )


@router.get("/me")
async def me_read_profile(principal: CurrentPrincipal, db: DbSession, storage: Storage) -> MeSchema:
    """N11: đọc hồ sơ của chính người gọi."""
    return await _me_schema(db, storage, principal.user_id)


def _profile_values(body: UpdateMeBody) -> dict[str, object]:
    """Chỉ cột có khoá mặt trong thân; `jobTitle`/`phone` rỗng → `NULL` (xoá, HOP-DONG-MOI §3)."""
    values: dict[str, object] = {}
    for field, column in _COLUMN_OF.items():
        if field in body.model_fields_set:
            value = getattr(body, field)
            values[column] = None if field in _NULLABLE_ON_EMPTY and value == "" else value
    return values


async def _apply_profile_update(db: AsyncSession, *, user_id: str, body: UpdateMeBody) -> None:
    """`UPDATE users` chỉ các cột có mặt; không thấy người chưa xoá → 401 `SESSION_REVOKED`."""
    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .values(_profile_values(body))
        .returning(User.id)
        .execution_options(synchronize_session=False)
    )
    _require(result.scalar_one_or_none() is not None, SESSION_REVOKED)


@router.patch("/me")
async def me_update_profile(
    body: UpdateMeBody, principal: CurrentPrincipal, db: DbSession, storage: Storage
) -> MeSchema:
    """N12: ghi các cột có mặt trong thân, trả `MeSchema` đọc lại sau khi ghi (K22)."""
    await _apply_profile_update(db, user_id=principal.user_id, body=body)
    return await _me_schema(db, storage, principal.user_id)


_password_limit: Final = rate_limit(
    "me_password",
    limit=PASSWORD_RATE_LIMIT,
    window_s=PASSWORD_RATE_WINDOW_S,
    key=key_user,
    store="safe",
    on_error="closed",
)


@dataclass(frozen=True, slots=True)
class _PasswordRow:
    """Băm hiện hành của một người chưa xoá mềm."""

    password_hash: str | None


def _password_row_of(row: object) -> _PasswordRow | None:
    """`_PasswordRow` từ dòng `SELECT` (hay `None`) — hàm thuần, gọi ngay sau `await` (NO-130)."""
    return None if row is None else _PasswordRow(row[0])  # type: ignore[index]  # Row đúng cột SELECT


async def _load_password_hash(db: AsyncSession, user_id: str) -> _PasswordRow | None:
    """`password_hash` của người chưa xoá, hay `None`."""
    row = (
        await db.execute(select(User.password_hash).where(User.id == user_id, User.deleted_at.is_(None)))
    ).one_or_none()
    return _password_row_of(row)


def _require_password_row(row: _PasswordRow | None) -> _PasswordRow:
    """`row`, hay ném `SESSION_REVOKED` khi không thấy — hàm thuần, gọi ngay sau `await` (NO-130)."""
    if row is None:
        raise SESSION_REVOKED.error()
    return row


async def _swap_password_hash(db: AsyncSession, *, user_id: str, old_hash: str | None, new_hash: str) -> bool:
    """Bước 1: so-và-đặt `password_hash`; 0 dòng (N9 vừa đổi giữa chừng) → `False` (BE-00 §5 N13)."""
    same_hash = User.password_hash.is_(None) if old_hash is None else User.password_hash == old_hash
    result = await db.execute(
        update(User)
        .where(User.id == user_id, same_hash, User.deleted_at.is_(None))
        .values(password_hash=new_hash)
        .returning(User.id)
        .execution_options(synchronize_session=False)
    )
    return result.scalar_one_or_none() is not None


async def _session_alive(db: AsyncSession, session_id: str) -> bool:
    """Bước 3: phiên hiện tại vẫn sống trong DB, khoá `FOR SHARE` (thứ tự khoá users → …)."""
    row = (
        await db.execute(
            select(RefreshSession.id)
            .where(RefreshSession.id == UUID(session_id), RefreshSession.revoked_at.is_(None))
            .with_for_update(read=True)
        )
    ).one_or_none()
    return row is not None


async def _finish_change_password(
    db: AsyncSession, *, user_id: str, session_id: str, old_hash: str | None, new_hash: str, clock: Clock
) -> None:
    """Bước 1-4 của N13 trong giao dịch của request, đúng thứ tự khoá `users → one_time_tokens → refresh_sessions`."""
    swapped = await _swap_password_hash(db, user_id=user_id, old_hash=old_hash, new_hash=new_hash)
    _require(swapped, CURRENT_PASSWORD_INCORRECT, field="currentPassword")
    await revoke_tokens(db, user_id=user_id, purpose="password_reset", clock=clock)
    alive = await _session_alive(db, session_id)
    _require(alive, SESSION_REVOKED)
    await revoke_sessions(db, user_id=user_id, reason="password_change", clock=clock, except_sid=session_id)


@router.post(
    "/me/password",
    status_code=204,
    response_class=Response,
    response_model=None,
    dependencies=[Depends(_password_limit)],
)
async def me_change_password(
    body: ChangePasswordBody, principal: CurrentPrincipal, db: DbSession, clock: ClockDep
) -> None:
    """N13: đổi mật khẩu; sai mật khẩu hiện tại → 422, không bao giờ 401 (K30). Thu hồi phiên khác."""
    row = _require_password_row(await _load_password_hash(db, principal.user_id))
    await db.rollback()  # K36: trả kết nối về pool trước khi kiểm/băm mật khẩu
    matched = await verify_password(row.password_hash, body.current_password)
    _require(matched, CURRENT_PASSWORD_INCORRECT, field="currentPassword")
    new_hash = await hash_password(body.new_password)
    await _finish_change_password(
        db,
        user_id=principal.user_id,
        session_id=principal.session_id,
        old_hash=row.password_hash,
        new_hash=new_hash,
        clock=clock,
    )
    return None


_avatar_limit: Final = rate_limit(
    "me_avatar", limit=AVATAR_RATE_LIMIT, window_s=AVATAR_RATE_WINDOW_S, key=key_user, store="safe", on_error="closed"
)


def _new_ulid(clock: Clock) -> str:
    """ULID trần cho tên object ảnh đại diện — mượn bộ sinh Crockford của `new_id` (BE-00 §8).

    `packages.core.ids` không phơi hàm sinh ULID trần riêng; tiền tố `tpl` bị bỏ ngay, chỉ
    thân 26 ký tự được dùng làm tên object (không phải id `tpl_…` thật nào tồn tại).
    """
    return new_id("tpl", clock).split("_", 1)[1]


async def _apply_avatar_key(db: AsyncSession, *, user_id: str, key: str) -> None:
    """`UPDATE users SET avatar_key` sau khi object đã ghi bền vững (bước 7); không thấy người → 401."""
    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .values(avatar_key=key)
        .returning(User.id)
        .execution_options(synchronize_session=False)
    )
    _require(result.scalar_one_or_none() is not None, SESSION_REVOKED)


@router.put("/me/avatar", dependencies=[Depends(_avatar_limit)])
async def me_replace_avatar(
    body: ReplaceAvatarBody, principal: CurrentPrincipal, db: DbSession, storage: Storage, clock: ClockDep
) -> MeSchema:
    """N14: giải mã, kiểm, mã hoá lại ảnh; `storage.put` trước giao dịch ghi `avatar_key` (K22)."""
    processed: ProcessedAvatar = await process_avatar(body.content_base64, body.mime_type)
    key = avatar_key_of(principal.user_id, _new_ulid(clock), processed.ext)
    await storage.put(key, processed.data, content_type=processed.content_type, max_bytes=MAX_STORED_BYTES)
    await _apply_avatar_key(db, user_id=principal.user_id, key=key)
    return await _me_schema(db, storage, principal.user_id)
