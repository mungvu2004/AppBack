"""Bản vẽ tổng hợp: đáp án khớp từng điểm ảnh, luật hình học, suy tỉ lệ, tất định giữa tiến trình (M01, M06)."""

import hashlib
import itertools
import logging
import math
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from packages.domain.scale.infer import ScaleSample, infer_scale
from packages.ml_contracts._font import CHARSET, TEXT_HEIGHT_PX, glyph, render_text
from packages.ml_contracts.artifacts import BoxPx, WallPx
from packages.ml_contracts.synthetic import (
    EVAL_SET_SEEDS,
    EVAL_SET_SHA256,
    MAX_SEED,
    MM_PER_PX_CHOICES,
    SyntheticPlan,
    can_render,
    eval_set_digest,
    format_mm,
    read_marker,
    render_plan,
)

_log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]
DIMENSION_RE = re.compile(r"[0-9]{1,3}(\.[0-9]{3})*")
SEEDS = (0, 1, 7, 100, 123, 139, 4_000_000_000)


def ink(plan: SyntheticPlan) -> NDArray[np.bool_]:
    return np.asarray(plan.pixels[:, :, 0] == 0, dtype=np.bool_)


def horizontal(wall: WallPx) -> bool:
    return wall.start.y == wall.end.y


def refill(plan: SyntheticPlan) -> NDArray[np.bool_]:
    """Tô lại mặt nạ từ đáp án theo luật tô tường của module, rồi khoét khe cửa đi."""
    mask = np.zeros_like(plan.walls_mask)
    for wall in plan.walls:
        half = wall.thickness_px / 2
        if horizontal(wall):
            along = sorted((wall.start.x, wall.end.x))
            rows = slice(int(wall.start.y - half), int(wall.start.y + half))
            cols = slice(math.floor(along[0] - half), math.ceil(along[1] + half))
        else:
            along = sorted((wall.start.y, wall.end.y))
            rows = slice(math.floor(along[0] - half), math.ceil(along[1] + half))
            cols = slice(int(wall.start.x - half), int(wall.start.x + half))
        mask[rows, cols] = True
    for door in (item for item in plan.detections if item.label == "door"):
        mask[region(door.box)] = False
    return mask


def region(box: BoxPx) -> tuple[slice, slice]:
    return slice(int(box.y_min), int(box.y_max)), slice(int(box.x_min), int(box.x_max))


def trimmed(block: NDArray[np.bool_]) -> NDArray[np.bool_]:
    rows = np.flatnonzero(block.any(axis=1))
    cols = np.flatnonzero(block.any(axis=0))
    return block[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]


def building_faces(plan: SyntheticPlan) -> tuple[int, int, int, int]:
    """(trên, dưới, trái, phải) của mặt ngoài tường bao, từ mặt nạ."""
    rows = np.flatnonzero(plan.walls_mask.any(axis=1))
    cols = np.flatnonzero(plan.walls_mask.any(axis=0))
    return int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1


@pytest.mark.parametrize("seed", SEEDS)
def test_render_plan_answers(seed: int) -> None:
    """Mặt nạ = tô lại `walls` trừ khe cửa đi; cửa sổ thuộc tường; mọi hộp chữ khớp mực (lệch 0 px)."""
    plan = render_plan(seed)
    image = ink(plan)
    assert np.array_equal(refill(plan), plan.walls_mask)
    assert plan.pixels.dtype == np.uint8
    assert set(np.unique(plan.pixels)) <= {0, 255}
    assert np.array_equal(plan.pixels[:, :, 0], plan.pixels[:, :, 2])
    for item in plan.detections:
        crop, mask_crop = image[region(item.box)], plan.walls_mask[region(item.box)]
        assert item.confidence == 1.0
        if item.label == "door":
            assert not crop.any()
            assert not mask_crop.any()
        elif item.label == "window":
            assert mask_crop.all()
            lines = crop.all(axis=1) if crop.shape[1] > crop.shape[0] else crop.all(axis=0)
            assert int(lines.sum()) == 3
            assert int(crop.sum()) == 3 * max(crop.shape)
        else:
            assert crop[0].all()
            assert crop[-1].all()
            assert crop[:, 0].all()
            assert crop[:, -1].all()
            assert not crop[1:-1, 1:-1].any()
    for text in plan.texts:
        crop = image[region(text.box)]
        block = trimmed(render_text(text.text))
        expected = block if crop.shape == block.shape else trimmed(np.rot90(render_text(text.text), k=-1))
        assert np.array_equal(crop, expected), text.text
        around = image[
            int(text.box.y_min) - 1 : int(text.box.y_max) + 1, int(text.box.x_min) - 1 : int(text.box.x_max) + 1
        ]
        assert int(around.sum()) == int(crop.sum())


@pytest.mark.parametrize("seed", SEEDS)
def test_render_plan_geometry_rules(seed: int) -> None:
    """Tỉ lệ, bề dày, 2-6 phòng, 1-3 đồ, mép cửa cách tim tường vuông góc ≥ 300 mm."""
    plan = render_plan(seed)
    scale = plan.mm_per_px
    assert scale in MM_PER_PX_CHOICES
    outer = math.floor(220 / scale + 0.5)
    partitions = {math.floor(mm / scale + 0.5) for mm in (110, 150)}
    thickness = sorted(wall.thickness_px for wall in plan.walls)
    assert thickness[-4:] == [outer] * 4
    assert set(thickness[:-4]) <= partitions
    rooms = len([t for t in plan.texts if not DIMENSION_RE.fullmatch(t.text)]) - 5
    assert 2 <= rooms <= 6
    furniture = [item for item in plan.detections if item.label not in ("door", "window")]
    assert rooms <= len(furniture) <= 3 * rooms
    verticals = sorted(wall.start.x for wall in plan.walls if not horizontal(wall))
    horizontals = sorted(wall.start.y for wall in plan.walls if horizontal(wall))
    clearance = 300 / scale
    for item in plan.detections:
        if item.label not in ("door", "window"):
            continue
        box = item.box
        along, crossing = (
            ((box.x_min, box.x_max), verticals)
            if box.x_max - box.x_min > box.y_max - box.y_min
            else (
                (box.y_min, box.y_max),
                horizontals,
            )
        )
        width_mm = (along[1] - along[0]) * scale
        assert abs(width_mm - (900 if item.label == "door" else 1200)) <= scale / 2
        assert min(abs(edge - centre) for edge in along for centre in crossing) >= clearance


@pytest.mark.parametrize("seed", SEEDS)
def test_render_plan_dimension_rows(seed: int) -> None:
    """Mỗi cạnh: chữ từng nhịp cách mặt ngoài 3 x cao chữ, chữ tổng 6 x cao chữ, tâm giữa nhịp."""
    plan = render_plan(seed)
    top, bottom, left, right = building_faces(plan)
    dims = [t for t in plan.texts if DIMENSION_RE.fullmatch(t.text)]
    assert len(dims) >= 4
    gaps = []
    for text in dims:
        box = text.box
        gaps.append(
            min(
                abs(top - box.y_max),
                abs(box.y_min - bottom),
                abs(left - box.x_max),
                abs(box.x_min - right),
            )
        )
    assert set(gaps) <= {3 * TEXT_HEIGHT_PX, 6 * TEXT_HEIGHT_PX}
    assert gaps.count(6 * TEXT_HEIGHT_PX) == 4


def pixel_length(plan: SyntheticPlan, box: BoxPx) -> float:
    """Nhịp tim-tim mà chữ kích thước ghi: nhịp chứa tâm chữ, hay cả cạnh với hàng chữ tổng."""
    top, bottom, left, right = building_faces(plan)
    is_row = box.y_max <= top or box.y_min >= bottom
    walls = [wall for wall in plan.walls if horizontal(wall) != is_row]
    centres = sorted(wall.start.x if is_row else wall.start.y for wall in walls)
    gap = (
        min(abs(top - box.y_max), abs(box.y_min - bottom))
        if is_row
        else min(abs(left - box.x_max), abs(box.x_min - right))
    )
    if gap == 6 * TEXT_HEIGHT_PX:
        return centres[-1] - centres[0]
    middle = (box.x_min + box.x_max) / 2 if is_row else (box.y_min + box.y_max) / 2
    return next(b - a for a, b in itertools.pairwise(centres) if a < middle < b)


@pytest.mark.parametrize("seed", SEEDS)
def test_render_plan_scale_infers(seed: int) -> None:
    """Chữ kích thước + nhịp pixel đủ để `infer_scale` (B3-01) ra đúng tỉ lệ, lệch ≤ 1 %."""
    plan = render_plan(seed)
    samples = [
        ScaleSample(
            id=str(index), pixel_length=pixel_length(plan, text.box), real_length_mm=float(text.text.replace(".", ""))
        )
        for index, text in enumerate(plan.texts)
        if DIMENSION_RE.fullmatch(text.text)
    ]
    result = infer_scale(samples)
    assert result.mm_per_px is not None
    assert abs(result.mm_per_px - plan.mm_per_px) <= 0.01 * plan.mm_per_px


def test_render_plan_ink_outside() -> None:
    """≥ 5 % điểm mực nằm ngoài hộp bao tường ngoài nở 2 % mỗi phía (40 seed của tập kiểm)."""
    for seed in EVAL_SET_SEEDS:
        plan = render_plan(seed)
        top, bottom, left, right = building_faces(plan)
        grow_y, grow_x = 0.02 * (bottom - top), 0.02 * (right - left)
        inside = np.zeros_like(plan.walls_mask)
        inside[
            math.floor(top - grow_y) : math.ceil(bottom + grow_y), math.floor(left - grow_x) : math.ceil(right + grow_x)
        ] = True
        page = ink(plan)
        assert (page & ~inside).sum() >= 0.05 * page.sum(), seed


@pytest.mark.perf
def test_render_plan_performance() -> None:
    started = time.perf_counter()
    for seed in EVAL_SET_SEEDS:
        render_plan(seed)
    elapsed = time.perf_counter() - started
    _log.info("render_plan_40_seeds_s=%.3f", elapsed)
    assert elapsed < 8.0


def _fingerprint(plan: SyntheticPlan) -> str:
    return hashlib.sha256(plan.pixels.tobytes() + plan.walls_mask.tobytes() + plan.image_png).hexdigest()


def test_render_plan_m01_cross_process() -> None:
    """Cùng seed → cùng từng byte (ảnh, mặt nạ, PNG) ở một tiến trình Python khác."""
    script = textwrap.dedent(
        """
        import hashlib
        from packages.ml_contracts.synthetic import render_plan
        plan = render_plan(123)
        print(hashlib.sha256(plan.pixels.tobytes() + plan.walls_mask.tobytes() + plan.image_png).hexdigest())
        """
    )
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=120
    )
    assert result.stdout.strip() == _fingerprint(render_plan(123))


def test_eval_set_m06_fixed() -> None:
    """Tập kiểm cố định tính lại đúng hằng đã ghim; đổi hằng chỉ qua FIX kèm đánh giá lại."""
    assert eval_set_digest() == EVAL_SET_SHA256


def test_read_marker() -> None:
    plan = render_plan(MAX_SEED, width_px=900, height_px=800)
    assert read_marker(plan.pixels) == MAX_SEED
    assert read_marker(render_plan(0).pixels) == 0
    assert read_marker(plan.pixels[:, :-10]) is None
    assert read_marker(plan.pixels[10:]) is None
    assert read_marker(np.full((800, 900, 3), 255, dtype=np.uint8)) is None
    assert read_marker(np.zeros((40, 900, 3), dtype=np.uint8)) is None
    assert read_marker(plan.pixels[:, :, 0]) is None


@pytest.mark.parametrize(
    ("seed", "width", "height", "match"),
    [
        (-1, 1600, 1200, "seed"),
        (MAX_SEED + 1, 1600, 1200, "seed"),
        (1, 255, 1200, "cạnh"),
        (1, 8001, 5000, "cạnh"),
        (1, 640, 480, "quá nhỏ"),
    ],
)
def test_render_plan_rejects(seed: int, width: int, height: int, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        render_plan(seed, width_px=width, height_px=height)


def test_can_render_matches_render_plan() -> None:
    """`can_render` nói đúng khổ nào `render_plan` vẽ được (bộ giả dựa vào nó để trả rỗng)."""
    assert can_render(1600, 1200)
    assert can_render(800, 600)
    for width, height in ((640, 480), (255, 2000), (8001, 5000)):
        assert not can_render(width, height)
        with pytest.raises(ValueError, match=r"quá nhỏ|cạnh"):
            render_plan(1, width_px=width, height_px=height)


def test_render_plan_large_page() -> None:
    plan = render_plan(5, width_px=4000, height_px=3000)
    assert plan.pixels.shape == (3000, 4000, 3)
    assert not plan.pixels.flags.writeable
    assert not plan.walls_mask.flags.writeable


def test_format_and_font() -> None:
    assert [format_mm(value) for value in (900, 3600, 12500)] == ["900", "3.600", "12.500"]
    assert {"0", "9", ".", "A", "Z", " "} <= CHARSET
    assert glyph("8").shape == (TEXT_HEIGHT_PX, 10)
    assert render_text("AB").shape == (TEXT_HEIGHT_PX, 22)
    with pytest.raises(ValueError, match="không có ký tự"):
        glyph("Ư")
    with pytest.raises(ValueError, match="rỗng"):
        render_text("")
