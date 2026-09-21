"""Thuật toán idempotency của `AppRoute` (BE-00 §7, C10, C22).

Ba giai đoạn, cố ý nằm ở **ba giao dịch khác nhau**:

1. `begin` — giao dịch riêng, commit ngay. Một `INSERT … ON CONFLICT DO UPDATE`
   vừa nhận việc, vừa chiếm lại dòng đã hết hạn thuê, vừa dọn dòng quá TTL trong
   **một** lệnh: tách ra thành đọc-rồi-ghi là mở cửa cho hai lượt cùng thắng.
2. `complete` — nằm trong **chính giao dịch nghiệp vụ** của request, nên "đã ghi
   dữ liệu" và "đã ghi bằng chứng" hoặc cùng có, hoặc cùng không. `UPDATE … WHERE
   claim_token = :mine` trả 0 dòng nghĩa là hạn thuê đã hết và người khác đang
   chạy: lượt này phải rollback (BE-00 §7).
3. `discard` — giao dịch riêng, xoá dòng khi lượt chạy hỏng, để lượt sau thử lại
   được.

Lượt lặp không bao giờ chạy lại handler: hoặc trả lại đúng response đã lưu, hoặc
422 `IDEMPOTENCY_KEY_REUSED` (thân khác), hoặc 503 `IDEMPOTENCY_IN_PROGRESS`.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, and_, delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.dml import ReturningInsert
from starlette.responses import Response

from packages.core.error_codes import (
    IDEMPOTENCY_IN_PROGRESS,
    IDEMPOTENCY_KEY_REUSED,
    INTERNAL,
    VALIDATION,
)
from packages.core.errors import AppError
from packages.db.models.idempotency import (
    KEY_PATTERN,
    MAX_RESPONSE_BODY_BYTES,
    STATE_COMPLETED,
    STATE_IN_PROGRESS,
    IdempotencyRecord,
)

HEADER: Final = "Idempotency-Key"
KEY_FIELD: Final = "idempotencyKey"
LEASE: Final = timedelta(seconds=30)
TTL: Final = timedelta(hours=24)
IN_PROGRESS_RETRY_AFTER: Final = 1

NO_STORE_STATUSES: Final = frozenset({401, 408, 429})
"""Status không lưu (BE-00 §7): lượt sau phải được chạy lại thật."""

DEFAULT_CONTENT_TYPE: Final = "application/octet-stream"

_KEY_RE: Final = re.compile(KEY_PATTERN)
_LENGTH_BYTES: Final = 8


@dataclass(frozen=True, slots=True)
class Claim:
    """Quyền chạy của **lượt này** trên một dòng idempotency."""

    record_id: int
    token: UUID


class Replay(Exception):  # noqa: N818 — không phải lỗi: đây là lối thoát mang response đã lưu
    """Thoát khỏi route mà không chạy handler, trả lại response của lượt trước (C10)."""

    def __init__(self, response: Response) -> None:
        """Mang theo response đã dựng sẵn; `AppRoute` trả nó thay cho handler."""
        super().__init__("idempotency replay")
        self.response: Final = response


def check_key(raw: str) -> str:
    """Header sai mẫu → 422 `VALIDATION` (fail-closed: không im lặng bỏ qua idempotency)."""
    if not _KEY_RE.fullmatch(raw):
        raise VALIDATION.error(field=KEY_FIELD, count=1)
    return raw


def request_digest(method: str, path: str, query: str, body: bytes) -> str:
    """SHA-256 của `method | đường thật | query đã sắp | thân thô` (BE-00 §7).

    Dùng **đường thật** chứ không phải khuôn đường: cùng một khoá gửi sang dự án
    khác là một request khác, và phải nhận 422 `IDEMPOTENCY_KEY_REUSED`.

    Mỗi phần mang **tiền tố độ dài** chứ không nối bằng `|`: đường thật đã giải mã có thể
    chứa `|`, nên phép nối trần cho hai request khác nhau cùng một hash.
    """
    parts = sorted(query.split("&")) if query else []
    digest = hashlib.sha256()
    for field in (method.upper().encode("utf-8"), path.encode("utf-8"), "&".join(parts).encode("utf-8"), body):
        digest.update(len(field).to_bytes(_LENGTH_BYTES, "big"))
        digest.update(field)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class _Existing:
    """Dòng đang chặn lượt này, đã đọc sẵn ra giá trị thường.

    Không giữ thực thể ORM: `rollback()` làm mọi thuộc tính của nó hết hạn, và lần
    đọc sau khi session đóng sẽ ném `DetachedInstanceError` thay vì trả dữ liệu.
    """

    request_hash: str
    state: str
    status_code: int | None
    content_type: str | None
    response_body: bytes | None


def _replay_response(record: _Existing) -> Response:
    """Response của lượt trước. Thân không lưu được (> 1 MiB) → 500, **không** chạy lại."""
    if record.response_body is None or record.status_code is None:
        raise AppError(INTERNAL)
    return Response(
        content=record.response_body,
        status_code=record.status_code,
        media_type=record.content_type or DEFAULT_CONTENT_TYPE,
    )


def _claim_statement(
    *,
    user_id: str,
    method: str,
    route_template: str,
    key: str,
    digest: str,
    now: datetime,
) -> ReturningInsert[tuple[int, UUID]]:
    """`INSERT … ON CONFLICT DO UPDATE … WHERE <dòng cũ>` trả `(id, claim_token)` khi nhận được việc.

    Một lệnh duy nhất vừa tạo dòng mới, vừa chiếm lại dòng quá TTL hay hết hạn thuê;
    không trả dòng nào nghĩa là dòng đang chặn còn hiệu lực (BE-00 §7).
    """
    stale = or_(
        IdempotencyRecord.expires_at <= now,
        and_(IdempotencyRecord.state == STATE_IN_PROGRESS, IdempotencyRecord.lease_until <= now),
    )
    fresh: dict[str, object] = {
        "user_id": user_id,
        "method": method,
        "route_template": route_template,
        "key": key,
        "request_hash": digest,
        "state": STATE_IN_PROGRESS,
        "claim_token": uuid4(),
        "lease_until": now + LEASE,
        "expires_at": now + TTL,
        "created_at": now,
        "updated_at": now,
    }
    taken_over = {name: value for name, value in fresh.items() if name != "created_at"}
    taken_over.update(status_code=None, content_type=None, response_body=None)
    return (
        pg_insert(IdempotencyRecord)
        .values(**fresh)
        .on_conflict_do_update(
            index_elements=["user_id", "method", "route_template", "key"],
            set_=taken_over,
            where=stale,
        )
        .returning(IdempotencyRecord.id, IdempotencyRecord.claim_token)
    )


async def _read_blocker(
    session: AsyncSession, *, user_id: str, method: str, route_template: str, key: str
) -> _Existing | None:
    """Dòng đang chặn lượt này, đọc ra giá trị thường trước khi session rollback."""
    row = (
        await session.execute(
            select(
                IdempotencyRecord.request_hash,
                IdempotencyRecord.state,
                IdempotencyRecord.status_code,
                IdempotencyRecord.content_type,
                IdempotencyRecord.response_body,
            ).where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.method == method,
                IdempotencyRecord.route_template == route_template,
                IdempotencyRecord.key == key,
            )
        )
    ).first()
    return None if row is None else _Existing(*row)


async def begin(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    user_id: str,
    method: str,
    route_template: str,
    key: str,
    digest: str,
    now: datetime,
) -> Claim:
    """Nhận việc trong giao dịch riêng (commit ngay), hoặc thoát bằng `Replay` / `AppError` (422, 503)."""
    scope = {"user_id": user_id, "method": method, "route_template": route_template, "key": key}
    async with sessionmaker() as session:
        claimed = (await session.execute(_claim_statement(**scope, digest=digest, now=now))).first()
        if claimed is not None:
            await session.commit()
            return Claim(record_id=int(claimed.id), token=claimed.claim_token)
        blocker = await _read_blocker(session, **scope)
        await session.rollback()
    return _blocked(blocker, digest)


def _blocked(record: _Existing | None, digest: str) -> Claim:
    """Không nhận được việc thì trả gì. Hàm này không bao giờ trả về bình thường."""
    if record is None:
        # Dòng vừa biến mất giữa hai lệnh (lịch dọn rác xoá đúng lúc): bảo client thử lại.
        raise IDEMPOTENCY_IN_PROGRESS.error(retry_after=IN_PROGRESS_RETRY_AFTER)
    if record.request_hash != digest:
        raise IDEMPOTENCY_KEY_REUSED.error()
    if record.state == STATE_COMPLETED:
        raise Replay(_replay_response(record))
    raise IDEMPOTENCY_IN_PROGRESS.error(retry_after=IN_PROGRESS_RETRY_AFTER)


def storable(response: Response) -> bool:
    """Status của response này có được ghi vào dòng `completed` không (BE-00 §7)."""
    return response.status_code < 500 and response.status_code not in NO_STORE_STATUSES


async def complete(session: AsyncSession, claim: Claim, response: Response, now: datetime) -> None:
    """Đánh dấu `completed` trong **cùng** giao dịch nghiệp vụ; 0 dòng → 503."""
    body = getattr(response, "body", None)
    keep = body if isinstance(body, bytes) and len(body) <= MAX_RESPONSE_BODY_BYTES else None
    # `Result` chung không khai `rowcount`; lệnh DML luôn trả `CursorResult`.
    result = cast(
        "CursorResult[Any]",
        await session.execute(
            update(IdempotencyRecord)
            .where(IdempotencyRecord.id == claim.record_id, IdempotencyRecord.claim_token == claim.token)
            .values(
                state=STATE_COMPLETED,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                response_body=keep,
                updated_at=now,
            )
        ),
    )
    if result.rowcount != 1:
        raise IDEMPOTENCY_IN_PROGRESS.error(retry_after=IN_PROGRESS_RETRY_AFTER)


async def discard(sessionmaker: async_sessionmaker[AsyncSession], claim: Claim) -> None:
    """Xoá dòng của lượt hỏng bằng giao dịch riêng (giao dịch nghiệp vụ đã rollback).

    Chỉ xoá dòng còn `in_progress`: lượt bị huỷ **sau** khi đã commit (tắt tiến trình lúc
    deploy, client ngắt giữa `after_commit_idle`) cũng đi qua đây, và xoá mất dòng
    `completed` là để lượt lặp chạy lại handler — nhân đôi tác dụng ngoài (CON-02).
    """
    async with sessionmaker() as session:
        await session.execute(
            delete(IdempotencyRecord).where(
                IdempotencyRecord.id == claim.record_id,
                IdempotencyRecord.claim_token == claim.token,
                IdempotencyRecord.state == STATE_IN_PROGRESS,
            )
        )
        await session.commit()
