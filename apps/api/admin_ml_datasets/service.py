"""Việc của N28-N31 (B6-02 [6]); `router.py` chỉ chuyển tham số vào đây.

Thứ tự khoá của cả module: `datasets` → `dataset_versions` (BE-00 §9) — `versions.py`
đã khoá `datasets FOR UPDATE` trước khi đọc/ghi `dataset_versions` (`start_version`).

N31 gửi task **sau commit** (K17, `on_after_commit`): `send_task` không bao giờ chạy
trong cùng giao dịch với việc ghi bản `building`, để một `rollback` muộn (lỗi ở chỗ
khác trong cùng request) không để lại một thông điệp mồ côi.
"""

from datetime import datetime
from typing import Final

from sqlalchemy import desc, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.admin_ml_datasets import versions
from apps.api.admin_ml_datasets.errors import DATASET_BUILD_IN_PROGRESS, DATASET_NAME_TAKEN
from apps.api.admin_ml_datasets.schemas import (
    DatasetOut,
    DatasetPage,
    DatasetVersionOut,
    DatasetVersionPage,
    dataset_out,
    dataset_version_out,
)
from apps.api.admin_ml_datasets.settings import MlDatasetsSettings
from apps.api.core.auth import Principal
from apps.api.core.pagination import PageParams, decode_cursor, encode_cursor
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND, VALIDATION
from packages.core.errors import AppError
from packages.core.ids import is_id, new_id
from packages.db.hooks import on_after_commit
from packages.db.models.admin_ml_datasets import DatasetRow, DatasetVersionRow
from packages.db.models.projects import Project
from packages.messaging.celery_app import send_task
from packages.messaging.payloads.datasets import BUILD_VERSION_TASK, BuildDatasetVersionPayload
from packages.ml_contracts.families import MODEL_FAMILIES as FAMILY_ORDER

LIST_DATASETS_OP: Final = "ml_list_datasets"
LIST_VERSIONS_OP: Final = "ml_list_dataset_versions"
DATASET_RESOURCE: Final = "dataset"


def _dataset_not_found() -> AppError:
    """404 `NOT_FOUND` `resource:"dataset"` — id sai mẫu cũng trả 404, không 422."""
    return NOT_FOUND.error(resource=DATASET_RESOURCE)


async def list_datasets(db: AsyncSession, *, family: str | None, page: PageParams) -> DatasetPage:
    """N28 — mới nhất trước, cursor theo `(created_at, id)`, bộ lọc `family` gắn vào cursor.

    `family` ngoài ba họ → 422 `VALIDATION` `field:"family"` (đây là query, không 404).
    """
    if family is not None and family not in FAMILY_ORDER:
        raise VALIDATION.error(field="family")
    filters = {"family": family}
    stmt = select(DatasetRow)
    if family is not None:
        stmt = stmt.where(DatasetRow.family == family)
    if page.cursor is not None:
        position = decode_cursor(page.cursor, LIST_DATASETS_OP, filters)
        after = (datetime.fromisoformat(str(position["createdAt"])), str(position["id"]))
        stmt = stmt.where(tuple_(DatasetRow.created_at, DatasetRow.id) < after)
    stmt = stmt.order_by(desc(DatasetRow.created_at), desc(DatasetRow.id)).limit(page.limit + 1)
    rows = list((await db.execute(stmt)).scalars().all())
    items = rows[: page.limit]
    more = len(rows) > page.limit
    last = {"createdAt": items[-1].created_at.isoformat(), "id": items[-1].id} if more else None
    return DatasetPage(
        items=[dataset_out(row) for row in items],
        next_cursor=encode_cursor(LIST_DATASETS_OP, filters, last) if last is not None else None,
    )


async def create_dataset(db: AsyncSession, *, name: str, family: str, principal: Principal, clock: Clock) -> DatasetOut:
    """N29 — `INSERT … ON CONFLICT (name_key) DO NOTHING RETURNING`; 0 dòng → 409.

    `name` đã `nfc(strip)`, cấm `Cc`/bidi, 1-80 ký tự ở `schemas.CleanName`; chỉ còn
    tính `name_key` (`casefold`) ở đây.
    """
    now = clock.now()
    dataset_id = new_id("dst", clock)
    stmt = (
        pg_insert(DatasetRow)
        .values(
            id=dataset_id,
            name=name,
            name_key=name.casefold(),
            family=family,
            created_by=principal.user_id,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["name_key"])
        .returning(DatasetRow)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise DATASET_NAME_TAKEN.error()
    await record_activity(
        db,
        actor_id=principal.user_id,
        kind=ActivityKind.DATASET_CREATE,
        object_code=row.id,
        object_label=row.name,
        clock=clock,
    )
    return dataset_out(row)


async def _get_dataset(db: AsyncSession, dataset_id: str) -> DatasetRow:
    """Dataset chưa khoá; không có → 404 `resource:"dataset"` (N30, N31 bước 1)."""
    row = (await db.execute(select(DatasetRow).where(DatasetRow.id == dataset_id))).scalar_one_or_none()
    if row is None:
        raise _dataset_not_found()
    return row


async def list_dataset_versions(db: AsyncSession, *, dataset_id: str, page: PageParams) -> DatasetVersionPage:
    """N30 — dataset không có → 404; cursor theo `sequence` giảm dần."""
    await _get_dataset(db, dataset_id)
    filters = {"datasetId": dataset_id}
    stmt = select(DatasetVersionRow).where(DatasetVersionRow.dataset_id == dataset_id)
    if page.cursor is not None:
        position = decode_cursor(page.cursor, LIST_VERSIONS_OP, filters)
        stmt = stmt.where(DatasetVersionRow.sequence < int(position["sequence"]))
    stmt = stmt.order_by(desc(DatasetVersionRow.sequence)).limit(page.limit + 1)
    rows = list((await db.execute(stmt)).scalars().all())
    items = rows[: page.limit]
    more = len(rows) > page.limit
    last = {"sequence": items[-1].sequence} if more else None
    return DatasetVersionPage(
        items=[dataset_version_out(row) for row in items],
        next_cursor=encode_cursor(LIST_VERSIONS_OP, filters, last) if last is not None else None,
    )


async def _checked_project_ids(
    db: AsyncSession, project_ids: list[str] | None, settings: MlDatasetsSettings
) -> list[str] | None:
    """1…`DATASET_PROJECT_IDS_MAX` id `prj_…`, bỏ trùng, sắp tăng; sai mẫu hay xoá mềm → 422.

    Vắng (`None`) nghĩa là mọi dự án ([6] bước 1) — trả `None` nguyên vẹn, không rỗng.
    """
    if project_ids is None:
        return None
    unique = sorted(set(project_ids))
    over_limit = len(unique) > settings.dataset_project_ids_max
    if not unique or over_limit or any(not is_id("prj", pid) for pid in unique):
        raise VALIDATION.error(field="projectIds")
    stmt = select(Project.id).where(Project.id.in_(unique), Project.deleted_at.is_(None))
    found = (await db.execute(stmt)).scalars().all()
    if set(found) != set(unique):
        raise VALIDATION.error(field="projectIds")
    return unique


async def build_dataset_version(
    db: AsyncSession,
    *,
    dataset_id: str,
    project_ids: list[str] | None,
    principal: Principal,
    clock: Clock,
    settings: MlDatasetsSettings,
) -> DatasetVersionOut:
    """N31 — dataset không có → 404; bản `building` đang có → 409; task gửi sau commit (K17)."""
    dataset = await _get_dataset(db, dataset_id)
    checked_project_ids = await _checked_project_ids(db, project_ids, settings)
    version = await versions.start_version(
        db,
        dataset_id=dataset_id,
        source="approvedFloors",
        project_ids=checked_project_ids,
        created_by=principal.user_id,
        clock=clock,
    )
    if version is None:
        raise DATASET_BUILD_IN_PROGRESS.error()
    await record_activity(
        db,
        actor_id=principal.user_id,
        kind=ActivityKind.DATASET_BUILD,
        object_code=version.id,
        object_label=dataset.name,
        clock=clock,
    )
    payload = BuildDatasetVersionPayload(dataset_version_id=version.id)
    on_after_commit(db, lambda: send_task(BUILD_VERSION_TASK, payload))
    return dataset_version_out(version)
