"""Ghim model và sổ theo dõi của một lượt chạy: bảng `pipeline_run_models` (B5-06a [2], [5]).

Hàm worker nhập (BE-00 §7): gọi **sau** `lock_run` của B2-04, trong cùng giao dịch; không
commit. Mỗi hàm ghi "một lần" trả `False` khi đã ghi rồi (giao lặp J06), không ném — dùng
`INSERT … ON CONFLICT DO NOTHING` hay `UPDATE … WHERE <cột> IS NULL` cùng `rowcount`, không
đọc-rồi-ghi (tránh đua giữa hai giao lại song song, #26).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, Text, bindparam, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.pipeline_orchestrate import PipelineRunModelsRow
from packages.ml_contracts.families import MODEL_FAMILIES, ModelFamily
from packages.ml_contracts.payloads import ModelRef


@dataclass(frozen=True, slots=True)
class RunPins:
    """Ảnh chụp một dòng `pipeline_run_models`; đông cứng để không ai ghi qua nó.

    `used`: họ → `version_id` | `pinned_name` | `"classic"` (chỉ tường) | `"none"`; họ đã có
    ở đây thì `queue_infer` không gửi lại bước đó.
    """

    run_id: str
    pinned: Mapping[ModelFamily, ModelRef]
    used: Mapping[ModelFamily, str]
    persisted_revision: int | None
    step_requeue_count: int


async def pin_models(db: AsyncSession, *, run_id: str, models: Mapping[ModelFamily, ModelRef]) -> bool:
    """Ghim đủ ba họ cho lượt; dòng đã có → `False` (giữ bản đầu); thiếu họ → `ValueError`."""
    missing = [family for family in MODEL_FAMILIES if family not in models]
    if missing:
        raise ValueError(f"thiếu họ model để ghim: {missing}")
    pinned = {family: models[family].model_dump(mode="json") for family in MODEL_FAMILIES}
    stmt = (
        pg_insert(PipelineRunModelsRow)
        .values(run_id=run_id, pinned=pinned)
        .on_conflict_do_nothing(index_elements=[PipelineRunModelsRow.run_id])
        .returning(PipelineRunModelsRow.run_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def record_used(db: AsyncSession, *, run_id: str, family: ModelFamily, used: str) -> bool:
    """Ghi bản model một bước ML đã dùng; họ đã có → `False`; đặt `last_used_at = now`."""
    stmt = text(
        "UPDATE pipeline_run_models"
        " SET used = used || jsonb_build_object(:family, :used), last_used_at = now()"
        " WHERE run_id = :run_id AND NOT (used ? :family)"
    ).bindparams(bindparam("family", type_=Text), bindparam("used", type_=Text), bindparam("run_id", type_=Text))
    result = cast("CursorResult[Any]", await db.execute(stmt, {"run_id": run_id, "family": family, "used": used}))
    return result.rowcount > 0


async def mark_persisted(db: AsyncSession, *, run_id: str, revision: int) -> bool:
    """Ghi revision tài liệu tầng chỉ khi còn NULL; `< 0` → `ValueError`; `step_requeue_count = 0`."""
    if revision < 0:
        raise ValueError(f"revision không được âm: {revision}")
    stmt = (
        update(PipelineRunModelsRow)
        .where(PipelineRunModelsRow.run_id == run_id, PipelineRunModelsRow.persisted_revision.is_(None))
        .values(persisted_revision=revision, step_requeue_count=0)
    )
    result = cast("CursorResult[Any]", await db.execute(stmt))
    return result.rowcount > 0


async def set_step_requeue(db: AsyncSession, *, run_id: str, count: int) -> None:
    """Đặt số lần quét bù gửi lại bước hiện tại; `< 0` → `ValueError`."""
    if count < 0:
        raise ValueError(f"count không được âm: {count}")
    stmt = update(PipelineRunModelsRow).where(PipelineRunModelsRow.run_id == run_id).values(step_requeue_count=count)
    await db.execute(stmt)


async def mark_artifacts_purged(db: AsyncSession, *, run_id: str, at: datetime) -> bool:
    """Đánh dấu artifact của lượt đã dọn; đã có → `False`."""
    stmt = (
        update(PipelineRunModelsRow)
        .where(PipelineRunModelsRow.run_id == run_id, PipelineRunModelsRow.artifacts_purged_at.is_(None))
        .values(artifacts_purged_at=at)
    )
    result = cast("CursorResult[Any]", await db.execute(stmt))
    return result.rowcount > 0


async def load_pins(db: AsyncSession, run_id: str, *, for_update: bool = False) -> RunPins | None:
    """Đọc dòng ghim của lượt; chưa có → `None`; `for_update` khoá dòng."""
    stmt = select(PipelineRunModelsRow).where(PipelineRunModelsRow.run_id == run_id)
    if for_update:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    pinned = {cast("ModelFamily", family): ModelRef.model_validate(value) for family, value in row.pinned.items()}
    used = {cast("ModelFamily", family): value for family, value in row.used.items()}
    return RunPins(
        run_id=row.run_id,
        pinned=pinned,
        used=used,
        persisted_revision=row.persisted_revision,
        step_requeue_count=row.step_requeue_count,
    )
