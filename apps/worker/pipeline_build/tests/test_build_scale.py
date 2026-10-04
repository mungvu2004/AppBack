"""Bước 1 và 2 của `build_layer` (B5-05 [6]): lọc đầu vào, chốt tỉ lệ, `s_dựng`, dựng lại."""

import logging
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import pytest

from apps.worker.pipeline_build import build as build_module
from apps.worker.pipeline_build.build import BuiltLayer, build_layer
from apps.worker.pipeline_build.tests.helpers import build_wrapped
from packages.domain.scale import RescaleError, ScaleSample
from packages.ml_contracts.artifacts import (
    BoxPx,
    DetectionPx,
    ObjectsResult,
    PointPx,
    TextPx,
    TextResult,
    WallPx,
    WallsResult,
)
from packages.ml_contracts.synthetic import render_plan
from packages.testing.fixtures.clock import FakeClock

LEVEL_ID = "L-0000000000000000000000001"
SIZE = {"width_px": 1600, "height_px": 1200}


def _wall(x0: float, y0: float, x1: float, y1: float, thickness_px: float = 20.0) -> WallPx:
    """Tường px ngang hay dọc, tin cậy cố định 0,9 để `confidence` của đầu ra dễ đoán."""
    return WallPx(start=PointPx(x=x0, y=y0), end=PointPx(x=x1, y=y1), thickness_px=thickness_px, confidence=0.9)


def _run(
    walls: Sequence[WallPx],
    texts: Sequence[TextPx],
    clock: FakeClock,
    *,
    detections: Sequence[DetectionPx] = (),
    fallback: str = "5",
) -> BuiltLayer:
    """Gọi `build_layer` trên khổ 1600x1200 mặc định; tham số còn lại giữ nguyên giữa các ca."""
    return build_wrapped(
        walls=walls,
        detections=detections,
        texts=texts,
        fallback_mm_per_px=Decimal(fallback),
        clock=clock,
        level_id=LEVEL_ID,
        **SIZE,
    )


def test_build_layer__scale_from_pipeline_matches_answer(fake_clock: FakeClock) -> None:
    """Seed 100 tổng hợp → `pipeline`, lệch `mm_per_px` đáp án ≤ 2 % (K19: không đoán tỉ lệ)."""
    plan = render_plan(100)
    built = _run(plan.walls, plan.texts, fake_clock, detections=plan.detections)
    assert built.scale_source == "pipeline"
    assert abs(float(built.scale_mm_per_px) - plan.mm_per_px) / plan.mm_per_px <= 0.02


def test_build_layer__no_text_falls_back_to_project_default(
    fake_clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    """Không chữ nào → không suy được tỉ lệ: `s` là `fallback`, log mang `SCALE_UNRESOLVED`."""
    caplog.set_level(logging.INFO, logger=build_module.__name__)
    built = _run([_wall(100, 100, 1100, 100)], (), fake_clock)
    assert (built.scale_source, built.scale_mm_per_px) == ("project_default", Decimal("5"))
    assert any(getattr(record, "code", None) == "SCALE_UNRESOLVED" for record in caplog.records)


@pytest.mark.parametrize("fallback", ["0", "-1", "NaN"])
def test_build_layer__rejects_bad_fallback(fallback: str, fake_clock: FakeClock) -> None:
    """`fallback_mm_per_px` không dương hay không hữu hạn là sai hợp đồng → `ValueError`."""
    with pytest.raises(ValueError, match="fallback_mm_per_px"):
        _run([_wall(100, 100, 1100, 100)], (), fake_clock, fallback=fallback)


@pytest.mark.parametrize(("width", "height"), [(0, 1200), (1600, 0)])
def test_build_layer__rejects_empty_image(width: int, height: int, fake_clock: FakeClock) -> None:
    """Ảnh nhỏ hơn 1 px không có hệ toạ độ để kẹp đầu vào → `ValueError`."""
    with pytest.raises(ValueError, match="không hợp lệ"):
        build_wrapped(
            width_px=width, height_px=height, fallback_mm_per_px=Decimal("5"), clock=fake_clock, level_id=LEVEL_ID
        )


def test_build_layer__scale_out_of_range_falls_back(fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mẫu 500 mm/px (ngoài khoảng) → đếm `scaleOutOfRange` rồi dùng `fallback`, không áp 500."""
    samples = tuple(ScaleSample(id=f"t{i}-w0-s0", pixel_length=10.0, real_length_mm=5000.0) for i in range(4))
    monkeypatch.setattr(build_module, "pair_dimension_lines", lambda texts, walls: samples)
    built = _run([_wall(100, 100, 1100, 100)], (), fake_clock)
    assert built.scale_source == "project_default"
    assert built.dropped["scaleOutOfRange"] == 1


def test_build_layer__rescale_error_rebuilds_at_final_scale(
    fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """`RescaleError` khi đổi `s_dựng → s` → dựng lại thẳng ở `s`, không ném, có log riêng."""

    def _explode(layer: object, old: float, new: float) -> object:
        """Bản vá của `rescale_unreviewed`: luôn báo một thực thể hỏng (K23, phụ thuộc ngoài module)."""
        raise RescaleError("W-0000000000000000000000001")

    caplog.set_level(logging.WARNING, logger=build_module.__name__)
    monkeypatch.setattr(build_module, "rescale_unreviewed", _explode)
    built = _run([_wall(100, 100, 1100, 100)], (), fake_clock)
    assert built.scale_source == "project_default"
    assert any(record.getMessage() == "pipeline_build_rescale_fallback" for record in caplog.records)


def test_build_layer__rejects_non_finite_coordinate(fake_clock: FakeClock) -> None:
    """Toạ độ NaN dựng lén bằng `model_construct` vẫn bị bước 1 chặn → `ValueError`."""
    wall = WallPx.model_construct(
        start=PointPx.model_construct(x=float("nan"), y=100.0),
        end=PointPx(x=1100.0, y=100.0),
        thickness_px=20.0,
        confidence=0.9,
    )
    with pytest.raises(ValueError, match="NaN"):
        _run([wall], (), fake_clock)


def test_build_layer__rejects_confidence_out_of_unit_range(fake_clock: FakeClock) -> None:
    """`confidence` 1,5 là đầu ra sai hợp đồng B5-01, không phải đầu ra xấu → `ValueError`."""
    detection = DetectionPx.model_construct(
        label="door", box=BoxPx(x_min=400, y_min=90, x_max=500, y_max=110), confidence=1.5
    )
    with pytest.raises(ValueError, match="confidence"):
        _run([_wall(100, 100, 1100, 100)], (), fake_clock, detections=[detection])


def test_build_layer__drops_entities_outside_image(fake_clock: FakeClock) -> None:
    """Tường nằm ngoài `[-1, w+1] x [-1, h+1]` bị bỏ và đếm `outOfImage`, không làm hỏng lượt."""
    built = _run([_wall(100, 100, 1100, 100), _wall(5000, 5000, 6000, 5000)], (), fake_clock)
    assert built.dropped["outOfImage"] == 1
    assert len(built.layer.walls) == 1


def test_build_layer__post_rules_snap_fixture_to_wall(fake_clock: FakeClock) -> None:
    """Luật hậu xử lý B3-06 chạy: lavabo cách mặt tường 120 mm bị dời sát (`apply_post_rules`)."""
    fixture = DetectionPx(
        label="sanitary_fixture",
        box=BoxPx(x_min=300.0, y_min=134.0, x_max=400.0, y_max=174.0),
        confidence=0.8,
    )
    built = _run([_wall(100, 100, 1100, 100)], (), fake_clock, detections=[fixture])
    assert len(built.layer.furniture) == 1
    assert built.layer.furniture[0].centre.y < 770


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"thickness_px": 0.0}, "thickness_px"),
        ({"thickness_px": -5.0}, "thickness_px"),
        ({"end": PointPx(x=100.0, y=100.0)}, "hai đầu trùng"),
    ],
)
def test_build_layer__rejects_degenerate_wall(overrides: dict[str, Any], match: str, fake_clock: FakeClock) -> None:
    """Tường suy biến dựng lén bằng `model_construct` → `ValueError`, không `ZeroDivisionError`.

    `_build_scale` chia cho bề dày trung vị; bề dày 0 lọt qua bước 1 sẽ ném `ZeroDivisionError`
    mà `tasks._build_and_write` (`except ValueError`) không bắt được, nên thông điệp rơi vào
    đường thử lại thay vì `step_done failed` (review lượt 1, F1). `WallsResult` cũng dựng bằng
    `model_construct`: qua hàm dựng thường thì pydantic chặn trước, không tới được bước 1.
    """
    fields: dict[str, Any] = {
        "start": PointPx(x=100.0, y=100.0),
        "end": PointPx(x=1100.0, y=100.0),
        "thickness_px": 20.0,
        "confidence": 0.9,
        **overrides,
    }
    wall = WallPx.model_construct(None, **fields)
    with pytest.raises(ValueError, match=match):
        build_layer(
            level_id=LEVEL_ID,
            walls=WallsResult.model_construct(walls=(wall,)),
            objects=ObjectsResult(detections=()),
            text=TextResult(items=()),
            fallback_mm_per_px=Decimal("5"),
            clock=fake_clock,
            **SIZE,
        )
