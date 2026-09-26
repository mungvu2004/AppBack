"""`read_view` — dựng `ImageQualityAssessment` của #30 (B2-05b [2], [6], [8] "Đọc")."""

from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.tests.sql_count import count_sql
from apps.api.quality.assessments import read_view
from apps.api.quality.schemas import QualityAssessmentOut
from apps.api.quality.tests._helpers import (
    PNG,
    DrawnFloor,
    finding,
    make_drawn_floor,
    measure_floor,
    sample_report,
)
from packages.core.errors import AppError
from packages.db.models.drawings import DrawingRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.db.models.quality import QualityAssessmentRow
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.drawings import make_complete_upload, make_drawing
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock


async def _project(db: AsyncSession) -> Project:
    """Dự án mới của một chủ mới."""
    return await make_project(db, owner=await make_user(db))


async def _wire(db: AsyncSession, storage: LocalDiskStorage, project: Project, level_id: str) -> dict[str, Any]:
    """`read_view` rồi tuần tự hoá đúng như route (`by_alias`, bỏ `None`)."""
    return (await read_view(db, storage, project_id=project.id, level_id=level_id)).model_dump(
        mode="json", by_alias=True
    )


async def test_read_view__two_drawn_floors_by_order_and_focus(
    db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Ba tầng, hai có bản vẽ → `floors` 2 phần tử theo `order`; tầng `order` 0 chưa tải → `floorId` = phần tử đầu."""
    project = await _project(db_session)
    empty = await make_floor(db_session, project=project, order=0)
    late = await make_drawn_floor(db_session, local_storage, project=project, order=2)
    early = await make_drawn_floor(db_session, local_storage, project=project, order=1)

    from_empty = await _wire(db_session, local_storage, project, empty.level_id)
    assert [f["floorId"] for f in from_empty["floors"]] == [early.floor.level_id, late.floor.level_id]
    assert from_empty["floorId"] == early.floor.level_id
    assert from_empty["projectId"] == project.id

    from_late = await _wire(db_session, local_storage, project, late.floor.level_id)
    assert from_late["floorId"] == late.floor.level_id


async def test_read_view__no_drawing_anywhere_is_404_upload(
    db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Dự án không tầng nào có bản vẽ → 404 `resource: upload`."""
    project = await _project(db_session)
    floor = await make_floor(db_session, project=project)
    with pytest.raises(AppError) as caught:
        await read_view(db_session, local_storage, project_id=project.id, level_id=floor.level_id)
    assert caught.value.code.code == "NOT_FOUND"
    assert caught.value.params == {"resource": "upload"}


async def test_read_view__deleted_floor_is_left_out(db_session: AsyncSession, local_storage: LocalDiskStorage) -> None:
    """Tầng đã xoá mềm không có trong `floors` dù còn bản vẽ."""
    project = await _project(db_session)
    kept = await make_drawn_floor(db_session, local_storage, project=project)
    gone = await make_drawn_floor(db_session, local_storage, project=project)
    await db_session.execute(
        update(FloorRow).where(FloorRow.pk == gone.floor.pk).values(deleted_at=kept.drawing.uploaded_at)
    )
    out = await _wire(db_session, local_storage, project, kept.floor.level_id)
    assert [f["floorId"] for f in out["floors"]] == [kept.floor.level_id]


async def test_read_view__unmeasured_has_no_measurement_frame_or_confidence(
    db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Tầng chưa đo: `findings: []`, vắng `measurement`, `frame`, `expectedConfidence`; có `sourceUrl`."""
    project = await _project(db_session)
    drawn = await make_drawn_floor(db_session, local_storage, project=project)
    floor = (await _wire(db_session, local_storage, project, drawn.floor.level_id))["floors"][0]
    assert set(floor) == {"floorId", "floorName", "sourceUrl", "isMeasured", "findings"}
    assert floor["isMeasured"] is False
    assert floor["findings"] == []
    assert floor["sourceUrl"]


async def test_read_view__measured_wire_shape_round_trips(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Đã đo: đúng khoá camelCase, không `expectedConfidence`; JSON giải lại bằng model được."""
    project = await _project(db_session)
    drawn = await make_drawn_floor(db_session, local_storage, project=project)
    await measure_floor(db_session, fake_clock, drawn, sample_report(finding("LOW_CONTRAST")))
    out = await _wire(db_session, local_storage, project, drawn.floor.level_id)
    floor = out["floors"][0]
    assert set(floor) == {"floorId", "floorName", "sourceUrl", "isMeasured", "findings", "measurement", "frame"}
    assert set(floor["measurement"]) == {"widthPx", "heightPx", "skewDeg", "contrastScore", "noiseScore"}
    assert set(floor["findings"][0]) == {"id", "code", "severity", "region"}
    assert set(floor["findings"][0]["region"]) == {"xRatio", "yRatio", "widthRatio", "heightRatio"}
    assert QualityAssessmentOut.model_validate(out).model_dump(mode="json", by_alias=True) == out


async def test_read_view__finding_ids_stable_and_distinct_across_floors(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Hai `save_assessment` cùng trang → id như nhau; hai tầng cùng mã → id khác."""
    project = await _project(db_session)
    a = await make_drawn_floor(db_session, local_storage, project=project)
    b = await make_drawn_floor(db_session, local_storage, project=project)
    report = sample_report(finding("LOW_CONTRAST"))
    await measure_floor(db_session, fake_clock, a, report)
    first = await _wire(db_session, local_storage, project, a.floor.level_id)
    await measure_floor(db_session, fake_clock, a, report)
    await measure_floor(db_session, fake_clock, b, report)
    second = await _wire(db_session, local_storage, project, a.floor.level_id)
    id_a, id_b = (f["findings"][0]["id"] for f in second["floors"])
    assert first["floors"][0]["findings"][0]["id"] == id_a
    assert id_a != id_b
    assert id_a.startswith(f"{a.floor.level_id}.LOW_CONTRAST.1.")


async def test_read_view__finding_number_follows_region_order(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`n` đếm từ 1 trong từng mã theo `(yRatio, xRatio)`, không theo thứ tự trong báo cáo."""
    project = await _project(db_session)
    drawn = await make_drawn_floor(db_session, local_storage, project=project)
    report = sample_report(
        finding("HIGH_NOISE", x=0.5, y=0.5),
        finding("HIGH_NOISE", x=0.6, y=0.1),
        finding("HIGH_NOISE", x=0.2, y=0.1),
        finding("LOW_CONTRAST", x=0.7, y=0.7),
    )
    await measure_floor(db_session, fake_clock, drawn, report)
    findings = (await _wire(db_session, local_storage, project, drawn.floor.level_id))["floors"][0]["findings"]
    noise = [(f["id"].split(".")[2], f["region"]["xRatio"]) for f in findings if f["code"] == "HIGH_NOISE"]
    assert noise == [("1", 0.2), ("2", 0.6), ("3", 0.5)]
    assert [f["id"].split(".")[2] for f in findings if f["code"] == "LOW_CONTRAST"] == ["1"]


async def test_read_view__frame_applied_found_and_missing(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Góc đã áp → `{isFound: true}`, bỏ `FRAME_NOT_FOUND`; chưa áp → có `corners`; không thấy → `false`."""
    project = await _project(db_session)
    applied = await make_drawn_floor(db_session, local_storage, project=project)
    found = await make_drawn_floor(db_session, local_storage, project=project)
    missing = await make_drawn_floor(db_session, local_storage, project=project)
    not_found = finding("FRAME_NOT_FOUND")
    corners = ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9))
    await measure_floor(db_session, fake_clock, applied, sample_report(not_found, frame=None), corners=corners)
    await measure_floor(db_session, fake_clock, found, sample_report())
    await measure_floor(db_session, fake_clock, missing, sample_report(not_found, frame=None))
    floors = (await _wire(db_session, local_storage, project, applied.floor.level_id))["floors"]
    by_id = {f["floorId"]: f for f in floors}
    assert by_id[applied.floor.level_id]["frame"] == {"isFound": True}
    assert by_id[applied.floor.level_id]["findings"] == []
    assert len(by_id[found.floor.level_id]["frame"]["corners"]) == 4
    assert by_id[missing.floor.level_id]["frame"] == {"isFound": False}
    assert [f["code"] for f in by_id[missing.floor.level_id]["findings"]] == ["FRAME_NOT_FOUND"]


async def test_read_view__replaced_drawing_is_unmeasured(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Bản vẽ thay bằng upload khác, hoặc `page_key` đổi → `isMeasured: false`, `findings: []`."""
    project = await _project(db_session)
    drawn = await make_drawn_floor(db_session, local_storage, project=project)
    await measure_floor(db_session, fake_clock, drawn, sample_report(finding("LOW_CONTRAST")))
    drawn.drawing.page_key = drawn.drawing.page_key.replace(".png", "-2.png")
    await db_session.flush()
    floor = (await _wire(db_session, local_storage, project, drawn.floor.level_id))["floors"][0]
    assert (floor["isMeasured"], floor["findings"]) == (False, [])

    newer = await make_complete_upload(db_session, local_storage, project=project, floor=drawn.floor, data=PNG)
    await db_session.delete(drawn.drawing)
    await db_session.flush()
    await make_drawing(db_session, local_storage, upload=newer, png=PNG)
    floor = (await _wire(db_session, local_storage, project, drawn.floor.level_id))["floors"][0]
    assert (floor["isMeasured"], floor["findings"]) == (False, [])


async def test_read_view__rounds_and_clamps(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Toạ độ và vùng làm tròn 4 chữ số và kẹp [0, 1]."""
    project = await _project(db_session)
    drawn = await make_drawn_floor(db_session, local_storage, project=project)
    _, saved = await measure_floor(db_session, fake_clock, drawn, sample_report(finding("LOW_CONTRAST")))
    report: dict[str, Any] = {**saved.report}
    report["findings"] = [
        {
            "code": "LOW_CONTRAST",
            "severity": "poor",
            "region": {"xRatio": 0.123456, "yRatio": -0.2, "widthRatio": 1.7, "heightRatio": 0.5},
        }
    ]
    report["frame"] = {"isFound": True, "corners": [[0.33333, 1.2], [1, 0], [1, 1], [-0.1, 1]]}
    await db_session.execute(
        update(QualityAssessmentRow).where(QualityAssessmentRow.floor_pk == drawn.floor.pk).values(report=report)
    )
    floor = (await _wire(db_session, local_storage, project, drawn.floor.level_id))["floors"][0]
    assert floor["findings"][0]["region"] == {"xRatio": 0.1235, "yRatio": 0.0, "widthRatio": 1.0, "heightRatio": 0.5}
    assert floor["frame"]["corners"][0] == {"xRatio": 0.3333, "yRatio": 1.0}
    assert floor["frame"]["corners"][3]["xRatio"] == 0.0


async def test_read_view__single_query(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Đúng **một** câu SQL cho mọi tầng (không N+1)."""
    project = await _project(db_session)
    drawn: list[DrawnFloor] = [await make_drawn_floor(db_session, local_storage, project=project) for _ in range(3)]
    await measure_floor(db_session, fake_clock, drawn[0], sample_report(finding("LOW_CONTRAST")))
    with count_sql() as counter:
        await read_view(db_session, local_storage, project_id=project.id, level_id=drawn[0].floor.level_id)
    assert counter.count == 1, counter.statements


async def test_read_view__page_key_without_ulid_uses_the_whole_key(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """NO-226: `pageKey` không có ULID không làm `IndexError`; `finding.id` kết thúc bằng cả khoá trang."""
    project = await _project(db_session)
    drawn = await make_drawn_floor(db_session, local_storage, project=project)
    await measure_floor(db_session, fake_clock, drawn, sample_report(finding("LOW_CONTRAST")))
    plain = "pages/no-ulid.png"
    await db_session.execute(update(DrawingRow).where(DrawingRow.id == drawn.drawing.id).values(page_key=plain))
    row = (
        await db_session.execute(select(QualityAssessmentRow).where(QualityAssessmentRow.floor_pk == drawn.floor.pk))
    ).scalar_one()
    row.report = {**row.report, "pageKey": plain}
    await db_session.flush()

    out = await _wire(db_session, local_storage, project, drawn.floor.level_id)

    assert [f["id"] for f in out["floors"][0]["findings"]] == [f"{drawn.floor.level_id}.LOW_CONTRAST.1.{plain}"]
