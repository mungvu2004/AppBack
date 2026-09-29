"""Việc của N23, N24, N25, N27 (B6-01 [6]); `router.py` chỉ chuyển tham số vào đây.

N24 là ghi có version (W20, K07): so `revision` **trong câu `UPDATE`** (`WHERE family = :f AND
revision = :base`), không đọc rồi so trong Python. Thứ tự khoá của cả module: `model_families`
→ `model_versions` (BE-00 §9), nên N24 khoá dòng họ `FOR UPDATE` trước khi `FOR SHARE` bản.

N26 nằm ở `upload.py` vì nó không mở giao dịch trong lúc nhận tệp (K36).
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Final

from sqlalchemy import desc, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.admin_ml_registry.errors import (
    MODEL_FORMAT_UNSUPPORTED,
    MODEL_VERSION_FAMILY_MISMATCH,
    MODEL_VERSION_NOT_EVALUATED,
    family_not_found,
    version_not_found,
)
from apps.api.admin_ml_registry.schemas import (
    COMPLETED,
    ModelFamilyOut,
    ModelFamilyPage,
    ModelVersionOut,
    ModelVersionPage,
    family_out,
    version_out,
)
from apps.api.core.auth import Principal
from apps.api.core.pagination import PageParams, decode_cursor, encode_cursor
from packages.core.clock import Clock
from packages.core.error_codes import VALIDATION
from packages.core.errors import VersionConflictError
from packages.db.models.admin_ml_registry import ModelFamilyRow, ModelVersionRow
from packages.ml_contracts.families import MODEL_FAMILIES as FAMILY_ORDER

LIST_VERSIONS_OP: Final = "ml_list_versions"
"""`op` ký vào cursor của N25 — cursor của danh sách khác không dùng lại được."""

WALL: Final = "wallSegmentation"
"""Họ duy nhất chạy được đường cổ điển, nên là họ duy nhất nhận `versionId: null`."""

ONNX: Final = "onnx"
CLASSIC_LABEL: Final = "đường cổ điển"
"""Nhãn nhật ký của lượt bỏ kích hoạt: không có bản nào để lấy nhãn thật."""


async def list_families(db: AsyncSession) -> ModelFamilyPage:
    """N23 — đủ ba họ trong một truy vấn, thứ tự như `src/lib/realtime/pipeline.ts:50-52`.

    Không bao giờ có `nextCursor`: số họ là hằng ba, không phân trang thật. Thứ tự lấy từ
    `FAMILY_ORDER` (cùng bảng FE đọc) chứ không từ `ORDER BY`: ba dòng đã ở trong RAM, sắp
    trong SQL bằng `CASE` chỉ để có cùng kết quả là công vô ích. `KeyError` ở đây nghĩa là
    revision dữ liệu gốc thiếu một họ — lỗi migration, không phải lỗi người gọi.
    """
    rows = (await db.execute(select(ModelFamilyRow))).scalars().all()
    by_family = {row.family: row for row in rows}
    return ModelFamilyPage(items=[family_out(by_family[family]) for family in FAMILY_ORDER])


def _body_digest(version_id: str | None) -> str:
    """SHA-256 của thân N24 chuẩn hoá — dấu vết nhận ra lượt ghi lặp của chính người ghi (C09b)."""
    raw = json.dumps({"versionId": version_id}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_repeat(row: ModelFamilyRow, base_version: int, actor_id: str, digest: str) -> bool:
    """C09b: dòng họ hiện tại **chính là** kết quả lượt ghi này của cùng người, cùng thân."""
    return row.revision == base_version + 1 and row.last_writer_id == actor_id and row.last_body_sha256 == digest


async def _lock_family(db: AsyncSession, family: str) -> ModelFamilyRow:
    """Dòng họ dưới `FOR UPDATE`; không có dòng → 404 `modelFamily` như họ ngoài ba họ."""
    stmt = select(ModelFamilyRow).where(ModelFamilyRow.family == family).with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise family_not_found()
    return row


async def _activatable_version(db: AsyncSession, *, family: str, version_id: str) -> ModelVersionRow:
    """Bản dưới `FOR SHARE` (khoá **sau** dòng họ), đã qua bốn luật kích hoạt của N24 [6].

    `FOR SHARE` chứ không `FOR UPDATE`: lượt này không sửa bản, chỉ cần nó không bị xoá giữa
    chừng. Thứ tự kiểm là thứ tự khối [6] bước 3, nên một bản `safetensors` chưa đánh giá trả
    `MODEL_FORMAT_UNSUPPORTED` (định dạng là lý do gần hơn).
    """
    stmt = select(ModelVersionRow).where(ModelVersionRow.id == version_id).with_for_update(read=True)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise version_not_found()
    if row.family != family:
        raise MODEL_VERSION_FAMILY_MISMATCH.error()
    if row.weights_format != ONNX:
        raise MODEL_FORMAT_UNSUPPORTED.error()
    if row.evaluation_status != COMPLETED:
        raise MODEL_VERSION_NOT_EVALUATED.error()
    return row


async def _write_active(db: AsyncSession, *, family: str, base_version: int, values: dict[str, Any]) -> ModelFamilyRow:
    """`UPDATE … WHERE family AND revision = :base RETURNING` — một câu quyết định thắng thua (K07).

    Dòng họ đang bị lượt này giữ `FOR UPDATE` và `revision` vừa được đọc bằng `base_version`,
    nên `scalar_one` không bao giờ rỗng; rỗng thì bất biến khoá đã hỏng và ném là đúng.
    """
    stmt = (
        update(ModelFamilyRow)
        .where(ModelFamilyRow.family == family, ModelFamilyRow.revision == base_version)
        .values(revision=ModelFamilyRow.revision + 1, **values)
        .returning(ModelFamilyRow)
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one()


async def set_active_version(
    db: AsyncSession,
    *,
    family: str,
    base_version: int,
    version_id: str | None,
    principal: Principal,
    clock: Clock,
) -> ModelFamilyOut:
    """N24 — kích hoạt `version_id` cho `family`, hay `null` để quay về đường cổ điển.

    `family` ngoài ba họ → 404 `modelFamily`; `revision ≠ base_version` → 409
    `VersionConflictError(remote_changes=[])`, trừ lượt lặp của chính người ghi (C09b) và lượt
    đặt lại đúng bản đang kích hoạt — hai trường hợp ấy trả hiện trạng, không tăng `revision`.
    `null` cho họ khác `wallSegmentation`, bản họ khác, bản không `onnx`, bản chưa `completed`
    → 422 mã riêng của `errors.py`.
    """
    if family not in FAMILY_ORDER:
        raise family_not_found()
    digest = _body_digest(version_id)
    current = await _lock_family(db, family)
    if _is_repeat(current, base_version, principal.user_id, digest):
        return family_out(current)
    if current.revision != base_version:
        raise VersionConflictError(current_version=current.revision, remote_changes=[])
    label = CLASSIC_LABEL
    if version_id is None:
        if family != WALL:
            raise MODEL_VERSION_FAMILY_MISMATCH.error()
    else:
        label = (await _activatable_version(db, family=family, version_id=version_id)).label
    if version_id == current.active_version_id:
        return family_out(current)
    values = {
        "active_version_id": version_id,
        "last_writer_id": principal.user_id,
        "last_body_sha256": digest,
    }
    written = await _write_active(db, family=family, base_version=base_version, values=values)
    await record_activity(
        db,
        actor_id=principal.user_id,
        kind=ActivityKind.MODEL_ACTIVATE,
        object_code=version_id if version_id is not None else family,
        object_label=label,
        clock=clock,
    )
    return family_out(written)


async def list_versions(db: AsyncSession, *, family: str | None, page: PageParams) -> ModelVersionPage:
    """N25 — mới nhất trước, cursor theo `(created_at, id)`, bộ lọc `family` gắn vào cursor.

    `family` ngoài ba họ → 422 `VALIDATION` `field:"family"` (không 404: đây là query).
    Đọc `limit + 1` dòng: dòng thừa chỉ để biết còn trang sau, không trả ra. So vị trí bằng
    **bộ đôi** `(created_at, id) < (…)` chứ không hai điều kiện rời: hai bản cùng `created_at`
    (factory đặt mốc tay) vẫn ra đúng một thứ tự toàn phần, không lặp và không nhảy dòng.
    """
    if family is not None and family not in FAMILY_ORDER:
        raise VALIDATION.error(field="family")
    filters = {"family": family}
    stmt = select(ModelVersionRow)
    if family is not None:
        stmt = stmt.where(ModelVersionRow.family == family)
    if page.cursor is not None:
        position = decode_cursor(page.cursor, LIST_VERSIONS_OP, filters)
        after = (datetime.fromisoformat(str(position["createdAt"])), str(position["id"]))
        stmt = stmt.where(tuple_(ModelVersionRow.created_at, ModelVersionRow.id) < after)
    stmt = stmt.order_by(desc(ModelVersionRow.created_at), desc(ModelVersionRow.id)).limit(page.limit + 1)
    rows = list((await db.execute(stmt)).scalars().all())
    items = rows[: page.limit]
    more = len(rows) > page.limit
    last = {"createdAt": items[-1].created_at.isoformat(), "id": items[-1].id} if more else None
    return ModelVersionPage(
        items=[version_out(row) for row in items],
        next_cursor=encode_cursor(LIST_VERSIONS_OP, filters, last) if last is not None else None,
    )


async def read_version(db: AsyncSession, *, version_id: str) -> ModelVersionOut:
    """N27 — một bản; id sai mẫu hay không có → 404 `modelVersion` (không 422).

    Không kiểm mẫu `mdl_…` riêng: một id sai mẫu không khớp dòng nào, và trả cùng một câu trả
    lời cho "sai mẫu" và "không có" thì API không thành máy dò id (cùng lý lẽ với `CURSOR_INVALID`).
    """
    row = (await db.execute(select(ModelVersionRow).where(ModelVersionRow.id == version_id))).scalar_one_or_none()
    if row is None:
        raise version_not_found()
    return version_out(row)
