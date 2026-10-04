"""Nghiệp vụ #16-#18 (B2-07 [6]).

Thứ tự của mọi route ghi (BE-00 §7): khoá tư vấn `measurements:<project_id>` → dòng cần ghi
→ `touch_project` cuối cùng. Kiểm trùng id và trần chỉ chạy **sau** khoá, trong giao dịch ghi.
Phép đo xoá cứng, không nhật ký, không upsert: khác thân luôn 409.
"""

import hashlib
import json
from typing import Any, Final

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal
from apps.api.measurements.errors import MEASUREMENT_ID_TAKEN, MEASUREMENT_LIMIT_REACHED
from apps.api.measurements.schemas import MeasurementPoint, MeasurementRecord, MeasurementRecordIn
from apps.api.measurements.settings import get_measurements_settings
from apps.api.projects.summaries import touch_project
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND
from packages.core.ids import is_measurement_id
from packages.db.locks import lock_project_scope
from packages.db.models.measurements import MeasurementRow

LOCK_SCOPE: Final = "measurements"
RESOURCE: Final = "measurement"


def _real(value: float) -> float:
    """`float`, `-0.0` → `0.0` (cộng `0.0` xoá dấu của số không âm)."""
    return float(value) + 0.0


def _point(point: MeasurementPoint) -> dict[str, float]:
    """Điểm chuẩn hoá; `z` vắng giữ vắng."""
    data = {"x": _real(point.x), "y": _real(point.y)}
    if point.z is not None:
        data["z"] = _real(point.z)
    return data


def normalize(body: MeasurementRecordIn) -> dict[str, Any]:
    """Bản chuẩn hoá duy nhất của thân — dùng cho cả lưu lẫn so (B2-07 [6]).

    Tên đã `nfc(strip)` từ validator; thứ tự `points` giữ nguyên.
    """
    return {
        "id": body.id,
        "name": body.name,
        "mode": body.mode,
        "points": [_point(point) for point in body.points],
        "rawValueMm": _real(body.raw_value_mm),
    }


def body_sha256(normalized: dict[str, Any]) -> str:
    """SHA-256 của JSON chuẩn tắc (khoá sắp xếp, không khoảng trắng, không NaN)."""
    text = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def to_record(row: MeasurementRow) -> MeasurementRecord:
    """Dòng đã lưu → response; không có `body_sha256`, `created_by`, mốc thời gian (K01)."""
    return MeasurementRecord.model_validate(
        {
            "id": row.measurement_id,
            "name": row.name,
            "mode": row.mode,
            "points": row.points,
            "rawValueMm": row.raw_value,
        }
    )


async def list_records(db: AsyncSession, project_id: str) -> list[MeasurementRecord]:
    """#16: theo **thứ tự số** của id (`MS-10000` sau `MS-9999`), tối đa `MEASUREMENTS_MAX`."""
    stmt = (
        select(MeasurementRow)
        .where(MeasurementRow.project_id == project_id)
        .order_by(func.char_length(MeasurementRow.measurement_id), MeasurementRow.measurement_id.collate("C"))
        .limit(get_measurements_settings().measurements_max)
    )
    return [to_record(row) for row in (await db.execute(stmt)).scalars()]


async def _check_room(db: AsyncSession, project_id: str, new_points: int) -> None:
    """Trần số phép đo và tổng điểm (một truy vấn); vượt → 422 `MEASUREMENT_LIMIT_REACHED`."""
    settings = get_measurements_settings()
    count, total = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(func.jsonb_array_length(MeasurementRow.points)), 0)).where(
                MeasurementRow.project_id == project_id
            )
        )
    ).one()
    if count >= settings.measurements_max or total + new_points > settings.measurement_points_total_max:
        raise MEASUREMENT_LIMIT_REACHED.error()


def _resolve_existing(row: MeasurementRow, digest: str) -> MeasurementRecord:
    """Id đã có: cùng thân → bản đã lưu (200); khác thân → 409 `MEASUREMENT_ID_TAKEN`."""
    if row.body_sha256 != digest:
        raise MEASUREMENT_ID_TAKEN.error(field="id")
    return to_record(row)


async def create_record(
    db: AsyncSession, project_id: str, body: MeasurementRecordIn, principal: Principal, clock: Clock
) -> tuple[MeasurementRecord, bool]:
    """#17: `(bản ghi, đã_tạo_mới)`; 200 không ghi gì và không `touch_project`."""
    normalized = normalize(body)
    digest = body_sha256(normalized)
    await lock_project_scope(db, LOCK_SCOPE, project_id)
    existing = (
        await db.execute(
            select(MeasurementRow)
            .where(MeasurementRow.project_id == project_id, MeasurementRow.measurement_id == body.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _resolve_existing(existing, digest), False
    await _check_room(db, project_id, len(body.points))
    row = MeasurementRow(
        project_id=project_id,
        measurement_id=body.id,
        name=normalized["name"],
        mode=body.mode,
        points=normalized["points"],
        raw_value=normalized["rawValueMm"],
        body_sha256=digest,
        created_by=principal.user_id,
    )
    db.add(row)
    await db.flush()
    await touch_project(db, project_id=project_id, clock=clock)
    return to_record(row), True


async def delete_record(db: AsyncSession, project_id: str, measurement_id: str, clock: Clock) -> None:
    """#18: xoá cứng; id sai mẫu hay không có trong **dự án này** → 404 `measurement`."""
    if not is_measurement_id(measurement_id):
        raise NOT_FOUND.error(resource=RESOURCE)
    await lock_project_scope(db, LOCK_SCOPE, project_id)
    deleted = (
        await db.execute(
            delete(MeasurementRow)
            .where(MeasurementRow.project_id == project_id, MeasurementRow.measurement_id == measurement_id)
            .returning(MeasurementRow.measurement_id)
        )
    ).scalar_one_or_none()
    if deleted is None:
        raise NOT_FOUND.error(resource=RESOURCE)
    await touch_project(db, project_id=project_id, clock=clock)
