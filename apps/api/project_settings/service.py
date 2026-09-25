"""Nghiệp vụ N5/N6 (B2-02 [6]): đọc cài đặt và ghi thay thế có version.

Ghi không bao giờ đọc-so-ghi revision trong Python (K07): một câu `INSERT … ON CONFLICT DO
NOTHING` (base 0) hoặc `UPDATE … WHERE revision = :base` (base > 0) quyết định thắng thua, kể cả
khi hai người ghi song song. Chỉ khi câu đó trả 0 dòng mới đọc hiện trạng để phân biệt lượt ghi
lặp (C09b) với xung đột thật (409).
"""

import hashlib
import json
from decimal import Decimal
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import ReturningInsert, ReturningUpdate

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.project_settings.read import find_row, read_settings, value_of
from apps.api.project_settings.schemas import ProjectSettingsBodyIn, ProjectSettingsOut
from apps.api.projects.access import ProjectAccess
from apps.api.projects.summaries import touch_project
from packages.core.clock import Clock
from packages.core.errors import VersionConflictError
from packages.db.models.project_settings import ProjectSettingsRow


async def get_settings(db: AsyncSession, project_id: str) -> ProjectSettingsOut:
    """N5: cài đặt của dự án, hoặc mặc định `revision 0` khi chưa ghi lần nào."""
    return ProjectSettingsOut.of(await read_settings(db, project_id))


def _columns(body: ProjectSettingsBodyIn) -> dict[str, Any]:
    """Các cột dữ liệu của body đã chuẩn hoá (NFC, trim, làm tròn đã làm ở schema)."""
    return {
        "building_type": body.building_type,
        "notes": body.notes,
        "length_unit": body.length_unit,
        "snap_tolerance_mm": body.snap_tolerance_mm,
        "confidence_threshold": body.confidence_threshold,
        "default_scale_mm_per_px": body.default_scale_mm_per_px,
    }


def body_digest(columns: dict[str, Any]) -> str:
    """SHA-256 của JSON chuẩn tắc (khoá sắp, không khoảng trắng); số thập phân ghi bằng chuỗi đã làm tròn.

    Cùng thân sau chuẩn hoá luôn cho cùng băm, nên bản NFD và NFC của `notes` là một (C16).
    """
    canonical = {key: str(value) if isinstance(value, Decimal) else value for key, value in columns.items()}
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _try_write(
    db: AsyncSession, project_id: str, base_version: int, values: dict[str, Any]
) -> ProjectSettingsRow | None:
    """Một câu SQL nguyên tử; `None` khi base không còn khớp (dòng đã có với base 0, hay revision đã đổi)."""
    statement: ReturningInsert[tuple[ProjectSettingsRow]] | ReturningUpdate[tuple[ProjectSettingsRow]]
    if base_version == 0:
        statement = (
            pg_insert(ProjectSettingsRow)
            .values(project_id=project_id, revision=1, **values)
            .on_conflict_do_nothing(index_elements=["project_id"])
            .returning(ProjectSettingsRow)
        )
    else:
        statement = (
            update(ProjectSettingsRow)
            .where(ProjectSettingsRow.project_id == project_id, ProjectSettingsRow.revision == base_version)
            .values(revision=ProjectSettingsRow.revision + 1, **values)
            .returning(ProjectSettingsRow)
        )
    return (await db.execute(statement.execution_options(populate_existing=True))).scalar_one_or_none()


def _is_repeat(row: ProjectSettingsRow, base_version: int, values: dict[str, Any]) -> bool:
    """C09b: dòng hiện tại chính là kết quả lượt ghi này của cùng người (revision = base + 1, cùng người, cùng băm)."""
    return (
        row.revision == base_version + 1
        and row.last_writer_id == values["last_writer_id"]
        and row.last_body_sha256 == values["last_body_sha256"]
    )


async def replace_settings(
    db: AsyncSession,
    access: ProjectAccess,
    *,
    base_version: int,
    body: ProjectSettingsBodyIn,
    clock: Clock,
) -> ProjectSettingsOut:
    """N6: thay toàn bộ cài đặt nếu `base_version` còn khớp; lượt lặp của chính người ghi → 200 không đổi gì.

    Ném `VersionConflictError` (409, `remoteChanges: []`) khi ai đó đã ghi trước. Thắng thì ghi
    nhật ký rồi `touch_project` (lời khoá cuối, BE-00 §7). `last_writer_id` chỉ lấy từ `Principal` (K05).
    """
    columns = _columns(body)
    values = {**columns, "last_writer_id": access.principal.user_id, "last_body_sha256": body_digest(columns)}
    written = await _try_write(db, access.project_id, base_version, values)
    if written is not None:
        await record_activity(
            db,
            actor_id=access.principal.user_id,
            kind=ActivityKind.PROJECT_SETTINGS_UPDATE,
            object_code=access.project_id,
            object_label=access.project_name,
            clock=clock,
            project_id=access.project_id,
        )
        await touch_project(db, project_id=access.project_id, clock=clock)
        return ProjectSettingsOut.of(value_of(written))
    current = await find_row(db, access.project_id)
    if current is not None and _is_repeat(current, base_version, values):
        return ProjectSettingsOut.of(value_of(current))
    raise VersionConflictError(current_version=0 if current is None else current.revision, remote_changes=[])
