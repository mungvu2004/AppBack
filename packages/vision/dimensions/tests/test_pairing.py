"""Ghép kích thước dựng tay: cảnh 5 tường ở 10 mm/px, ca nhiễu, tường song song, nhịp và cả tường."""

import pytest

from packages.domain.scale import ScaleSample, infer_scale
from packages.ml_contracts.artifacts import BoxPx, PointPx, TextPx, WallPx
from packages.vision.dimensions import pair_dimension_lines, wall_spans

TEXT_HEIGHT = 14.0


def wall(x0: float, y0: float, x1: float, y1: float, thickness: float = 20.0) -> WallPx:
    """Đường tim tường từ `(x0, y0)` tới `(x1, y1)`."""
    return WallPx(start=PointPx(x=x0, y=y0), end=PointPx(x=x1, y=y1), thickness_px=thickness, confidence=1.0)


def text(value: str, cx: float, cy: float, *, vertical: bool = False) -> TextPx:
    """Chữ cao 14 px, mỗi ký tự rộng 12 px, tâm `(cx, cy)`; `vertical` xoay 90° (hộp cao hơn rộng)."""
    width, height = 12.0 * len(value) - 2, TEXT_HEIGHT
    if vertical:
        width, height = height, width
    box = BoxPx(x_min=cx - width / 2, y_min=cy - height / 2, x_max=cx + width / 2, y_max=cy + height / 2)
    return TextPx(text=value, box=box, confidence=0.9)


def ratio(samples: tuple[ScaleSample, ...]) -> float | None:
    """`mm_per_px` mà `infer_scale` rút ra từ mẫu."""
    return infer_scale(samples).mm_per_px


# Khung 6000 x 4000 mm ở 10 mm/px, một vách dọc giữa: tường 0-1 ngang, 2-3 dọc, 4 là vách.
BASE_WALLS = (
    wall(100, 100, 700, 100),
    wall(100, 500, 700, 500),
    wall(100, 100, 100, 500),
    wall(700, 100, 700, 500),
    wall(400, 100, 400, 500),
)
BASE_TEXTS = (
    text("3000", 250, 60),
    text("3000", 550, 60),
    text("3000", 250, 540),
    text("3000", 550, 540),
    text("4000", 60, 300, vertical=True),
    text("4000", 740, 300, vertical=True),
)
BASE_IDS = ("t0-w0-s0", "t1-w0-s1", "t2-w1-s0", "t3-w1-s1", "t4-w2-s0", "t5-w3-s0")


def test_hand_built_scene_gives_ten_mm_per_px() -> None:
    """Sáu chữ quanh khung sinh sáu mẫu đúng `id`, đúng thứ tự, `infer_scale` ra 10 mm/px."""
    samples = pair_dimension_lines(BASE_TEXTS, BASE_WALLS)
    assert tuple(s.id for s in samples) == BASE_IDS
    assert samples[0] == ScaleSample("t0-w0-s0", 300.0, 3000.0)
    assert samples[4] == ScaleSample("t4-w2-s0", 400.0, 4000.0)
    assert ratio(samples) == pytest.approx(10, abs=1e-9)


@pytest.mark.parametrize(
    ("extra_walls", "extra_text"),
    [
        pytest.param((), text("PHONG NGU", 250, 62), id="room-label"),
        pytest.param((), text("48OO", 250, 62), id="suspicious-length"),
        pytest.param((), text("3000", 250, 10), id="too-far"),
        pytest.param((wall(800, 100, 1100, 400),), text("4243", 1000, 220), id="diagonal-wall"),
        pytest.param((), text("3000", 130, 60), id="off-centre-of-span"),
        pytest.param((), text("150", 250, 62), id="half-mm-per-px"),
        pytest.param((), text("3000", 250, 62).model_copy(update={"text": "1e3"}), id="not-a-length"),
    ],
)
def test_noise_adds_no_sample(extra_walls: tuple[WallPx, ...], extra_text: TextPx) -> None:
    """Mỗi loại nhiễu (đặt sau các chữ thật nên không đổi `id`) không sinh thêm mẫu nào."""
    clean = pair_dimension_lines(BASE_TEXTS, BASE_WALLS)
    assert pair_dimension_lines((*BASE_TEXTS, extra_text), (*BASE_WALLS, *extra_walls)) == clean


def test_text_between_parallel_walls_pairs_only_the_closer() -> None:
    """Chữ giữa hai tường song song chỉ ghép tường gần hơn (d = 20 so với 40)."""
    walls = (wall(100, 100, 400, 100), wall(100, 160, 400, 160))
    samples = pair_dimension_lines((text("3000", 250, 120),), walls)
    assert [s.id for s in samples] == ["t0-w0-s0"]


def test_two_texts_beside_one_wall_both_sample() -> None:
    """Hai chữ cạnh một tường (hai bên) đều sinh mẫu; `id` theo chỉ số chữ."""
    texts = (text("3000", 160, 60), text("3000", 340, 140))
    samples = pair_dimension_lines(texts, (wall(100, 100, 400, 100),))
    assert [s.id for s in samples] == ["t0-w0-s0", "t1-w0-s0"]


def test_tie_prefers_longer_wall_then_lower_index() -> None:
    """Cùng khoảng cách: tường dài hơn thắng; cùng dài: chỉ số nhỏ hơn thắng."""
    label = (text("3000", 250, 60),)
    short_long = (wall(100, 100, 400, 100), wall(100, 100, 700, 100))
    assert [s.id for s in pair_dimension_lines(label, short_long)] == ["t0-w1-s0"]
    twins = (wall(100, 100, 400, 100), wall(100, 100, 400, 100))
    assert [s.id for s in pair_dimension_lines(label, twins)] == ["t0-w0-s0"]


def test_wrong_orientation_and_empty_inputs_pair_nothing() -> None:
    """Chữ dọc cạnh tường ngang không ghép; không tường hay không chữ → rỗng."""
    assert pair_dimension_lines((text("3000", 250, 60, vertical=True),), (wall(100, 100, 400, 100),)) == ()
    assert pair_dimension_lines(BASE_TEXTS, ()) == ()
    assert pair_dimension_lines((), BASE_WALLS) == ()


def test_slightly_tilted_wall_is_usable_and_steep_one_is_not() -> None:
    """Lệch trục 5° dùng được (chiếu theo hướng thật), 15° thì không."""
    tilted = wall(100, 100, 400, 126.0)  # ≈ 4,9°
    steep = wall(100, 100, 400, 180.4)  # ≈ 15°
    assert len(pair_dimension_lines((text("3000", 250, 70),), (tilted,))) == 1
    assert pair_dimension_lines((text("3000", 250, 70),), (steep,)) == ()


def test_text_at_wall_end_falls_outside_the_span_window() -> None:
    """Hình chiếu đúng đầu mút `L` thuộc nhịp cuối nhưng ngoài `[0,2; 0,8]` → không mẫu."""
    assert pair_dimension_lines((text("3000", 700, 60),), BASE_WALLS) == ()


def test_whole_wall_sample_needs_more_than_one_span() -> None:
    """Chữ tổng giữa tường hai nhịp cho mẫu cả tường `sall`; tường một nhịp chỉ có mẫu nhịp."""
    two_spans = pair_dimension_lines((text("6000", 400, 60),), BASE_WALLS)
    assert two_spans == (ScaleSample("t0-w0-sall", 600.0, 6000.0),)
    single = pair_dimension_lines((text("6000", 400, 60),), (wall(100, 100, 700, 100),))
    assert [s.id for s in single] == ["t0-w0-s0"]


# --- nhịp -----------------------------------------------------------------------------------------


def test_spans_split_at_touching_walls_only() -> None:
    """Chia tại vách chạm (kể cả đầu vách cách tim ≤ ½ bề dày lớn hơn) và tường cắt xuyên; xa hơn thì không."""
    long_wall = wall(100, 100, 700, 100)
    touching = wall(300, 108, 300, 400)  # đầu cách tim 8 px ≤ 10
    crossing = wall(500, 50, 500, 400)  # xuyên qua
    too_far = wall(600, 115, 600, 400)  # đầu cách 15 px > 10
    parallel = wall(200, 100, 350, 100)  # cùng phương, chồng lên: không chia
    spans = wall_spans((long_wall, touching, crossing, too_far, parallel))
    assert spans[0] == (0.0, 200.0, 400.0, 600.0)


def test_spans_merge_nearby_junctions_and_ignore_corners() -> None:
    """Hai nút cách nhau ≤ ½ bề dày là một; nút sát đầu mút (góc) không tạo nhịp cụt."""
    long_wall = wall(100, 100, 700, 100)
    walls = (
        long_wall,
        wall(300, 100, 300, 400),
        wall(305, 100, 305, 400),
        wall(100, 100, 100, 400),
        wall(700, 100, 700, 400),
    )
    assert wall_spans(walls)[0] == (0.0, 200.0, 600.0)


def test_spans_of_isolated_and_diagonal_walls() -> None:
    """Tường không ai chạm chỉ có `(0, L)`; tường chéo vẫn có nhịp; không tường → rỗng."""
    assert wall_spans((wall(100, 100, 400, 100),)) == ((0.0, 300.0),)
    assert wall_spans((wall(0, 0, 30, 40),)) == ((0.0, 50.0),)
    assert wall_spans(()) == ()


def _pt(side: str, a: float, c: float) -> tuple[float, float]:
    """Toạ độ trang của điểm cách đầu tường bao `a` dọc tường và `c` hướng ra ngoài, trên cạnh `side`."""
    return {
        "top": (100 + a, 400 - c),
        "bottom": (100 + a, 400 + c),
        "left": (400 - c, 100 + a),
        "right": (400 + c, 100 + a),
    }[side]


def _seg(side: str, a0: float, c0: float, a1: float, c1: float) -> WallPx:
    """Tường trên cạnh `side` từ `(a0, c0)` tới `(a1, c1)`."""
    return wall(*_pt(side, a0, c0), *_pt(side, a1, c1))


def _label(side: str, value: str, a: float, c: float) -> TextPx:
    """Chữ trên cạnh `side`; cạnh đứng thì chữ dọc."""
    return text(value, *_pt(side, a, c), vertical=side in ("left", "right"))


def _strip(side: str) -> tuple[WallPx, ...]:
    """Tường 12.000 mm (1.200 px) ở cạnh `side` với hai vách vào trong; cạnh dưới/phải vẽ ngược hướng."""
    reversed_side = side in ("bottom", "right")
    long_wall = _seg(side, 1200, 0, 0, 0) if reversed_side else _seg(side, 0, 0, 1200, 0)
    return (long_wall, _seg(side, 400, -8, 400, -300), _seg(side, 800, -8, 800, -300))


SIDES = ("top", "bottom", "left", "right")


@pytest.mark.parametrize("side", SIDES)
def test_wall_of_three_spans_gives_exact_span_points(side: str) -> None:
    """Tường 3 nhịp 4.000 mm ở cả bốn cạnh: `wall_spans` ra `(0, 400, 800, 1200)`."""
    assert wall_spans(_strip(side))[0] == (0.0, 400.0, 800.0, 1200.0)


@pytest.mark.parametrize("side", SIDES)
def test_span_row_alone_gives_ten(side: str) -> None:
    """Chỉ hàng chữ nhịp (3 chữ 4.000) → 3 mẫu nhịp 400 px cộng mẫu cả tường sai của chữ giữa → 10 ± 1 %.

    Chữ giữa nằm ở 0,5 L nên luật [6] cho nó thêm mẫu cả tường 3,3 mm/px; `infer_scale` loại mẫu này.
    Cạnh dưới/phải vẽ tường ngược hướng nên chỉ số nhịp đảo; đếm theo độ dài, không theo `id`.
    """
    texts = tuple(_label(side, "4000", a, 45) for a in (200, 600, 1000))
    samples = pair_dimension_lines(texts, _strip(side))
    by_span = [s for s in samples if not s.id.endswith("sall")]
    assert [(s.pixel_length, s.real_length_mm) for s in by_span] == [(400.0, 4000.0)] * 3
    assert [s.id for s in samples if s.id.endswith("sall")] == ["t1-w0-sall"]
    assert ratio(samples) == pytest.approx(10, rel=0.01)


@pytest.mark.parametrize("side", SIDES)
def test_span_row_and_total_row_give_ten(side: str) -> None:
    """Hàng nhịp cộng hàng tổng (12.000 giữa tường): chữ tổng cho mẫu cả tường và một mẫu nhịp giữa sai 30 mm/px.

    Mẫu sai đúng luật [6] (chữ giữa tường cũng nằm giữa nhịp 2) và do `infer_scale` loại ngoại lai: vẫn 10 ± 1 %.
    """
    texts = (*(_label(side, "4000", a, 45) for a in (200, 600, 1000)), _label(side, "12000", 600, 60))
    samples = pair_dimension_lines(texts, _strip(side))
    assert ScaleSample("t3-w0-sall", 1200.0, 12000.0) in samples
    assert len(samples) == 6
    assert ratio(samples) == pytest.approx(10, rel=0.01)


@pytest.mark.parametrize("side", SIDES)
def test_total_row_alone_leaves_scale_unresolved(side: str) -> None:
    """Chỉ hàng tổng → hai mẫu (cả tường và nhịp giữa sai) < 3 → `infer_scale` không đoán (K19)."""
    samples = pair_dimension_lines((_label(side, "12000", 600, 60),), _strip(side))
    assert [s.id for s in samples] == ["t0-w0-s1", "t0-w0-sall"]
    assert ratio(samples) is None


def test_two_by_two_grid_with_span_rows_only_gives_ten() -> None:
    """Lưới 2 x 2 phòng 4.000 mm, mỗi cạnh ngoài 2 nhịp, chỉ chữ nhịp (0,25 L và 0,75 L) → 8 mẫu, 10 ± 1 %."""
    walls = (
        wall(100, 100, 900, 100),
        wall(100, 900, 900, 900),
        wall(100, 100, 100, 900),
        wall(900, 100, 900, 900),
        wall(100, 500, 900, 500),
        wall(500, 100, 500, 900),
    )
    texts = (
        *(text("4000", x, y) for y in (55, 945) for x in (300, 700)),
        *(text("4000", x, y, vertical=True) for x in (55, 945) for y in (300, 700)),
    )
    samples = pair_dimension_lines(texts, walls)
    assert len(samples) == 8
    assert not any(s.id.endswith("sall") for s in samples)
    assert ratio(samples) == pytest.approx(10, rel=0.01)
