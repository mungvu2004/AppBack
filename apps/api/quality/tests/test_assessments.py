"""`report_to_json`, `save_assessment`, `load_assessment` (B2-05b [2], [6], [8] "Lượt cũ")."""

import logging
from typing import Any

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.runs import start_run
from apps.api.quality.assessments import AssessmentRow, load_assessment, report_to_json, save_assessment
from apps.api.quality.tests._helpers import (
    HEIGHT,
    PNG,
    WIDTH,
    DrawnFloor,
    finding,
    identity_json,
    make_drawn_floor,
    measure_floor,
    sample_report,
)
from packages.db.models.drawings import PipelineRunRow
from packages.db.models.floors import FloorRow
from packages.db.models.quality import QualityAssessmentRow
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.drawings import make_complete_upload, make_drawing
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock
from packages.vision.quality import QualityReport

PAGE_KEY = "p/pages/0-X.png"


def _json(report: QualityReport | None = None, undo: dict[str, object] | None = None) -> dict[str, Any]:
    """`report_to_json` với báo cáo mẫu (hoặc `report`) trên trang `PAGE_KEY`."""
    return report_to_json(report or sample_report(), page_key=PAGE_KEY, width_px=WIDTH, height_px=HEIGHT, undo=undo)


async def _drawn(db: AsyncSession, storage: LocalDiskStorage) -> DrawnFloor:
    """Dự án mới + một tầng có bản vẽ."""
    project = await make_project(db, owner=await make_user(db))
    return await make_drawn_floor(db, storage, project=project)


async def _save(
    db: AsyncSession, clock: FakeClock, run_id: str, drawn: DrawnFloor, *, drawing_id: str | None = None
) -> AssessmentRow | None:
    """`save_assessment` với báo cáo mẫu; mặc định ghi cho bản vẽ hiện tại của `drawn`."""
    return await save_assessment(
        db,
        run_id=run_id,
        floor_pk=drawn.floor.pk,
        drawing_id=drawing_id or drawn.drawing.id,
        page_key=drawn.drawing.page_key,
        width_px=WIDTH,
        height_px=HEIGHT,
        report=sample_report(),
        homography=identity_json(),
        clock=clock,
    )


def test_report_to_json__shape_and_frame_ratios() -> None:
    """Số đo, vùng, mức nguyên từ báo cáo; khung pixel → tỉ lệ; `undo` đi nguyên."""
    report = sample_report(finding("SKEW_DETECTED", x=0.5, y=0.25, severity="poor"))
    out = _json(report, undo={"pageWidthPx": 5})
    assert out["pageKey"] == PAGE_KEY
    assert out["measurement"] == {
        "widthPx": WIDTH,
        "heightPx": HEIGHT,
        "skewDeg": 0.4,
        "contrastScore": 0.8,
        "noiseScore": 0.9,
    }
    assert out["findings"] == [
        {
            "code": "SKEW_DETECTED",
            "severity": "poor",
            "region": {"xRatio": 0.5, "yRatio": 0.25, "widthRatio": 0.2, "heightRatio": 0.2},
        }
    ]
    assert out["frame"] == {"isFound": True, "corners": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]}
    assert out["undo"] == {"pageWidthPx": 5}


def test_report_to_json__no_frame_is_not_found() -> None:
    """Không có khung → `isFound: false`, `corners: null`; `undo` vắng → `null`."""
    out = _json(sample_report(frame=None))
    assert out["frame"] == {"isFound": False, "corners": None}
    assert out["undo"] is None


def test_report_to_json__unknown_code_dropped_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Mã ngoài 5 mã bị bỏ và ghi `quality_unknown_code` (K01)."""
    with caplog.at_level(logging.WARNING):
        out = _json(sample_report(finding("MADE_UP"), finding("LOW_CONTRAST")))
    assert [f["code"] for f in out["findings"]] == ["LOW_CONTRAST"]
    assert any(r.message == "quality_unknown_code" for r in caplog.records)


async def test_save_assessment__writes_exact_values_then_upserts(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt hợp lệ ghi đúng giá trị truyền vào; lần hai cập nhật cùng dòng, không thêm dòng."""
    drawn = await _drawn(db_session, local_storage)
    corners = ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9))
    run, saved = await measure_floor(
        db_session, fake_clock, drawn, sample_report(finding("LOW_CONTRAST")), corners=corners, undo={"k": 1}
    )
    assert saved.corners == corners
    assert saved.homography == identity_json()
    assert saved.report["undo"] == {"k": 1}
    assert await load_assessment(db_session, drawn.floor.pk) == saved

    again = await _save(db_session, fake_clock, run.id, drawn)
    assert again is not None
    assert again.corners is None
    count = (await db_session.execute(select(func.count()).select_from(QualityAssessmentRow))).scalar_one()
    assert count == 1
    assert await load_assessment(db_session, drawn.floor.pk, for_update=True) == again


async def test_load_assessment__missing_is_none(db_session: AsyncSession) -> None:
    """Tầng chưa đo (hay không có) → `None`."""
    assert await load_assessment(db_session, 987654) is None


@pytest.mark.parametrize("status", ["completed", "failed"])
async def test_save_assessment__finished_run_is_none(
    status: str, db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt đã `completed`/`failed` không nhận kết quả muộn."""
    drawn = await _drawn(db_session, local_storage)
    run = await start_run(db_session, upload_id=drawn.upload.id, clock=fake_clock)
    await db_session.execute(update(PipelineRunRow).where(PipelineRunRow.id == run.id).values(status=status))
    assert await _save(db_session, fake_clock, run.id, drawn) is None
    assert await load_assessment(db_session, drawn.floor.pk) is None


async def test_save_assessment__superseded_run_is_none(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt bị `start_run` sau thay (`superseded_by`) → `None`, không ghi."""
    drawn = await _drawn(db_session, local_storage)
    old = await start_run(db_session, upload_id=drawn.upload.id, clock=fake_clock)
    await start_run(db_session, upload_id=drawn.upload.id, clock=fake_clock)
    assert await _save(db_session, fake_clock, old.id, drawn) is None
    assert await load_assessment(db_session, drawn.floor.pk) is None


async def test_save_assessment__other_upload_or_unknown_drawing_is_none(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Upload của lượt ≠ upload của bản vẽ `drawing_id` → `None`; bản vẽ lạ → `None`."""
    drawn = await _drawn(db_session, local_storage)
    run = await start_run(db_session, upload_id=drawn.upload.id, clock=fake_clock)
    newer = await make_complete_upload(db_session, local_storage, project=drawn.project, floor=drawn.floor, data=PNG)
    await db_session.delete(drawn.drawing)
    await db_session.flush()
    replaced = await make_drawing(db_session, local_storage, upload=newer, png=PNG)
    assert await _save(db_session, fake_clock, run.id, drawn, drawing_id=replaced.id) is None
    assert await _save(db_session, fake_clock, run.id, drawn, drawing_id="drw_missing") is None
    assert await load_assessment(db_session, drawn.floor.pk) is None


async def test_save_assessment__unknown_run_or_other_floor_is_none(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`run_id` không có, hay của tầng khác `floor_pk` → `None`."""
    project = await make_project(db_session, owner=await make_user(db_session))
    first = await make_drawn_floor(db_session, local_storage, project=project)
    second = await make_drawn_floor(db_session, local_storage, project=project)
    run = await start_run(db_session, upload_id=first.upload.id, clock=fake_clock)
    assert await _save(db_session, fake_clock, "run_missing", first) is None
    assert await _save(db_session, fake_clock, run.id, second) is None


async def test_floor_delete_cascades_assessment(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Xoá cứng tầng → dòng đo mất theo (FK `ON DELETE CASCADE`)."""
    drawn = await _drawn(db_session, local_storage)
    await measure_floor(db_session, fake_clock, drawn, sample_report())
    await db_session.execute(delete(FloorRow).where(FloorRow.pk == drawn.floor.pk))
    assert await load_assessment(db_session, drawn.floor.pk) is None
