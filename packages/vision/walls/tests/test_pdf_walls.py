"""Tường đọc từ nét vector PDF (`pdf_page_vectors` → `pixel_vectors` → `vector_walls`).

PDF dựng tay trong test (`synthetic.make_pdf`) ở tỉ lệ 1:50 nên đáp án biết trước theo mm thật:
phòng 6000 x 4000, tường bao 200, vách 100, một ô cửa đi 900 có cánh và cung mở, hai đường kích
thước song song cách 350 mm (lọt khoảng bề dày tường) cùng chữ — những thứ không được thành tường.
Mặt nạ trọng tài giả SegFormer: ảnh dựng của chính các dải tường tô đặc.
"""

import json
import math

import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.preprocess import pdf_vector
from packages.vision.preprocess.errors import VisionError
from packages.vision.preprocess.pdf import render_pdf_page
from packages.vision.preprocess.pdf_vector import pdf_page_vectors
from packages.vision.preprocess.tests.synthetic import make_pdf
from packages.vision.preprocess.types import Homography
from packages.vision.walls import pdf_walls
from packages.vision.walls.pdf_walls import PageVectors, VectorWalls, pixel_vectors, vector_walls

PAGE = (1190.0, 842.0)
MM = 72 / 25.4 / 50
"""Point giấy cho 1 mm thật ở 1:50."""
PT_PER_PAPER_MM = 72 / 25.4
OX, OY = 150.0, 200.0
BLACK = (0.0, 0.0, 0.0)
DPI = 100.0
# Dải tường (x, y, rộng, cao) theo mm thật: tường bao 200 có ô cửa 1000..1900 ở cạnh dưới, vách 100 ở x=3000.
BANDS_MM = (
    (0, 0, 1000, 200),
    (1900, 0, 4100, 200),
    (0, 3800, 6000, 200),
    (0, 0, 200, 4000),
    (5800, 0, 200, 4000),
    (3000, 200, 100, 3600),
)


def _pt(x: float, y: float) -> bytes:
    """Toạ độ mm thật → hai số point trên trang."""
    return f"{OX + x * MM:.3f} {OY + y * MM:.3f}".encode()


def _line(x0: float, y0: float, x1: float, y1: float) -> bytes:
    """Một nét thẳng `m l S` theo mm thật."""
    return _pt(x0, y0) + b" m " + _pt(x1, y1) + b" l S\n"


def _double_line_plan() -> bytes:
    """Mặt bằng vẽ hai nét: mặt ngoài/trong tường, vách, ô cửa, cánh + cung cửa, kích thước, chữ."""
    ops = b"0.5 w\n"
    ops += _line(0, 0, 1000, 0) + _line(1900, 0, 6000, 0) + _line(200, 200, 1000, 200)
    ops += _line(1900, 200, 3000, 200) + _line(3100, 200, 5800, 200)
    ops += _line(1000, 0, 1000, 200) + _line(1900, 0, 1900, 200)  # má cửa
    ops += _line(0, 4000, 6000, 4000) + _line(200, 3800, 3000, 3800) + _line(3100, 3800, 5800, 3800)
    ops += _line(0, 0, 0, 4000) + _line(200, 200, 200, 3800) + _line(6000, 0, 6000, 4000)
    ops += _line(5800, 200, 5800, 3800) + _line(3000, 200, 3000, 3800) + _line(3100, 200, 3100, 3800)
    ops += _pt(1000, 200) + f" {40 * MM:.3f} {900 * MM:.3f} re S\n".encode()  # cánh cửa 40 x 900
    ops += _pt(1000, 1100) + b" m " + _pt(1500, 1100) + b" " + _pt(1900, 700) + b" " + _pt(1900, 200) + b" c S\n"
    ops += b"0.2 w\n" + _line(0, -500, 6000, -500) + _line(0, -850, 6000, -850)  # hai đường kích thước
    ops += _line(0, -900, 0, -100) + _line(6000, -900, 6000, -100)  # đường gióng
    ops += b"BT /F1 12 Tf " + _pt(2800, -450) + b" Td (6000) Tj ET\n"
    ops += b"BT /F1 14 Tf " + _pt(0, 4600) + b" Td (MAT BANG - TL 1:50) Tj ET\n"
    return make_pdf(1, size=PAGE, ops=ops)


def _bands_pdf(rotate: int = 0) -> bytes:
    """Cùng mặt bằng, mỗi dải tường là một hình chữ nhật tô đặc (kiểu `vector-apt.pdf`)."""
    rects = [(OX + x * MM, OY + y * MM, w * MM, h * MM, BLACK) for x, y, w, h in BANDS_MM]
    return make_pdf(1, size=PAGE, rotate=rotate, rects=rects)


def _ink(data: bytes) -> NDArray[np.bool_]:
    """Mực của ảnh dựng ở `DPI` — mặt nạ trọng tài giả SegFormer."""
    pixels = render_pdf_page(data, 0, dpi=DPI).pixels
    return np.asarray(pixels.mean(axis=2) < 128)


def _page_vectors(data: bytes, shape: tuple[int, ...], scale_n: int | None = None) -> PageVectors | None:
    """`pixel_vectors` của trang 0 khi trang cuối là chính ảnh dựng khổ `shape` (không nắn)."""
    vectors = pdf_page_vectors(data, 0)
    height, width = shape
    px_per_paper_mm = width / vectors.width_pt * PT_PER_PAPER_MM
    return pixel_vectors(vectors, Homography.identity(width, height), px_per_paper_mm=px_per_paper_mm, scale_n=scale_n)


def _walls(data: bytes, evidence: NDArray[np.bool_], scale_n: int | None = None) -> VectorWalls | None:
    """`vector_walls` của trang 0 theo khổ của `evidence`; trang không vector → `None`."""
    page_vectors = _page_vectors(data, evidence.shape, scale_n)
    return None if page_vectors is None else vector_walls(page_vectors, evidence=evidence)


def _mm(px: float) -> float:
    """Pixel ảnh dựng → mm thật ở 1:50."""
    return px / (DPI / 72) / MM


def _summary(result: VectorWalls | None, shape: tuple[int, ...]) -> list[tuple[float, float, float, float, float]]:
    """Tường theo mm thật quanh gốc mặt bằng: `(x0, y0, x1, y1, bề dày)` làm tròn 1 mm, đã xếp.

    Pixel → point theo đúng tỉ lệ ảnh dựng `shape` (PDFium làm tròn khổ ảnh lên, khác `DPI / 72` vài phần vạn).
    """
    assert result is not None
    sx, sy = shape[1] / PAGE[0], shape[0] / PAGE[1]
    rows = []
    for wall in result.walls:
        x0, y0 = wall.start[0] / sx, wall.start[1] / sy
        x1, y1 = wall.end[0] / sx, wall.end[1] / sy
        ends = sorted([((x0 - OX) / MM, (PAGE[1] - y0 - OY) / MM), ((x1 - OX) / MM, (PAGE[1] - y1 - OY) / MM)])
        rows.append((*(round(v) for v in (*ends[0], *ends[1])), round(_mm(wall.thickness_px))))
    return sorted(rows)


EXPECTED = [
    (100, 100, 100, 3900, 200),
    (100, 100, 1000, 100, 200),
    (100, 3900, 5900, 3900, 200),
    (1900, 100, 5900, 100, 200),
    (3050, 100, 3050, 3900, 100),
    (5900, 100, 5900, 3900, 200),
]
"""Sáu tường: tim chạy tới tim tường vuông góc, ô cửa 1000..1900 còn nguyên, mặt trong bị vách cắt đã nối."""
THICKNESS_MM = [100, 200, 200, 200, 200, 200]


def test_double_line_plan_gives_exact_centrelines_and_thickness() -> None:
    """Tường hai nét → đúng sáu tường, bề dày 200/100; kích thước, chữ, cánh cửa, cung cửa không thành tường."""
    data = _double_line_plan()
    evidence = _ink(_bands_pdf())
    result = _walls(data, evidence)
    assert _summary(result, evidence.shape) == EXPECTED
    assert result is not None
    assert result.scale_n == 50  # đọc từ lớp chữ "TL 1:50"
    assert result.candidates > len(result.walls)  # cặp đường kích thước có mặt nhưng trọng tài loại
    assert all(wall.confidence >= 0.6 for wall in result.walls)


@pytest.mark.parametrize("rotate", [0, 90, 180, 270])
def test_filled_bands_follow_page_rotation(rotate: int) -> None:
    """Dải tô đặc trên trang xoay: tường vẫn khớp ảnh dựng (trọng tài là mực của chính ảnh đó)."""
    data = _bands_pdf(rotate)
    evidence = _ink(data)
    result = _walls(data, evidence, scale_n=50)
    assert result is not None
    assert len(result.walls) == 6
    assert sorted(round(_mm(w.thickness_px)) for w in result.walls) == THICKNESS_MM
    if rotate == 0:
        assert _summary(result, evidence.shape) == EXPECTED


def test_filled_bands_without_scale_note_use_paper_range() -> None:
    """Không có `TL 1:N`: khoảng bề dày theo mm giấy vẫn nhận tường 2-4 mm giấy."""
    data = _bands_pdf()
    result = _walls(data, _ink(data))
    assert result is not None
    assert result.scale_n is None
    assert len(result.walls) == 6


def test_dimension_lines_alone_are_not_walls() -> None:
    """Trọng tài không thấy tường (mặt nạ rỗng) → `None`, người gọi lùi về vector hoá mặt nạ."""
    data = _double_line_plan()
    evidence = np.zeros_like(_ink(data))
    assert _walls(data, evidence) is None


def test_rectified_page_maps_strokes_into_page_pixels() -> None:
    """Phép nắn (thu nửa) áp lên nét: tường nằm trong khổ trang cuối, bề dày đổi theo cùng tỉ lệ."""
    data = _bands_pdf()
    full = _ink(data)
    height, width = full.shape
    target = (width // 2, height // 2)
    homography = Homography.from_array(np.diag([0.5, 0.5, 1.0]), (width, height), target)
    vectors = pdf_page_vectors(data, 0)
    px_per_paper_mm = width / vectors.width_pt * PT_PER_PAPER_MM / 2
    page_vectors = pixel_vectors(vectors, homography, px_per_paper_mm=px_per_paper_mm, scale_n=50)
    assert page_vectors is not None
    result = vector_walls(page_vectors, evidence=full[: target[1] * 2 : 2, : target[0] * 2 : 2])
    assert result is not None
    assert sorted(round(_mm(2 * w.thickness_px)) for w in result.walls) == THICKNESS_MM
    points = [p for wall in result.walls for p in (wall.start, wall.end)]
    assert all(0 <= x <= target[0] and 0 <= y <= target[1] for x, y in points)


def test_raster_in_pdf_has_no_vectors() -> None:
    """PDF quét (một ảnh phủ cả trang, không nét) → `image_ratio` ≈ 1 và `pixel_vectors` là `None`."""
    image = b"q %g 0 0 %g 0 0 cm BI /W 2 /H 2 /CS /G /BPC 8 ID \x00\xff\xff\x00 EI Q\n" % PAGE
    data = make_pdf(1, size=PAGE, ops=image)
    vectors = pdf_page_vectors(data, 0)
    assert math.isclose(vectors.image_ratio, 1.0)
    assert len(vectors.segments) == 0
    assert _page_vectors(data, _ink(data).shape) is None


def test_blank_page_has_no_vectors() -> None:
    """Trang PDF không nét, không ảnh → không còn đoạn nào → `None` (không ghi `vectors.json` rỗng)."""
    data = make_pdf(1, size=PAGE)
    assert _page_vectors(data, _ink(data).shape) is None


def test_page_vectors_json_round_trip_keeps_walls() -> None:
    """`to_json` → `from_json` giữ nguyên đoạn, tỉ lệ và cho cùng tường (bước tường đọc lại đúng thứ đã ghi)."""
    data = _double_line_plan()
    evidence = _ink(_bands_pdf())
    page_vectors = _page_vectors(data, evidence.shape)
    assert page_vectors is not None
    loaded = PageVectors.from_json(page_vectors.to_json())
    assert np.array_equal(loaded.segments, page_vectors.segments)
    assert loaded.thickness_px == pytest.approx(page_vectors.thickness_px, abs=1e-4)
    assert loaded.scale_n == page_vectors.scale_n == 50
    assert vector_walls(loaded, evidence=evidence) == vector_walls(page_vectors, evidence=evidence)


def _body(**changes: object) -> bytes:
    """Một `vectors.json` hợp lệ đã đổi vài khoá (giá trị `...` = bỏ khoá)."""
    body: dict[str, object] = {"segments": [[0, 0, 10, 0], [0, 5, 10, 5]], "thicknessPx": [1.0, 9.0], "scaleN": 50}
    body |= changes
    return json.dumps({k: v for k, v in body.items() if v is not ...}).encode()


@pytest.mark.parametrize(
    "data",
    [
        b"{",
        b"\xff",
        b"[]",
        _body(extra=1),
        _body(scaleN=...),
        _body(scaleN=0),
        _body(scaleN="50"),
        _body(scaleN=True),
        _body(segments=[[0, 0, 10, 0], [0, 5]]),
        _body(segments=[[0, 0, 10]]),
        _body(segments=[[0, 0, 10, None]]),
        _body(segments=[["a", 0, 10, 0]]),
        _body(segments=[[0, 0, 10, float("nan")]]),
        _body(segments=[0, 0, 10, 0]),
        _body(thicknessPx=[9.0, 1.0]),
        _body(thicknessPx=[0.0, 1.0]),
        _body(thicknessPx=[1.0]),
    ],
    ids=[
        "bad_json",
        "not_utf8",
        "not_object",
        "extra_key",
        "missing_key",
        "scale_zero",
        "scale_string",
        "scale_bool",
        "ragged",
        "three_columns",
        "null_number",
        "string_number",
        "nan",
        "flat",
        "thickness_reversed",
        "thickness_zero",
        "thickness_one",
    ],
)
def test_page_vectors_from_json_rejects_bad_objects(data: bytes) -> None:
    """Object kho không tin: mọi dạng lệch → `ValueError` (bước tường lùi về mặt nạ), không lỗi khác."""
    with pytest.raises(ValueError):  # noqa: PT011  # mỗi dạng lệch một thông điệp; chỉ kiểu là hợp đồng
        PageVectors.from_json(data)


def test_page_vectors_from_json_caps_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quá `MAX_SEGMENTS` đoạn → `ValueError` (K13), đúng trần thì qua."""
    monkeypatch.setattr(pdf_walls, "MAX_SEGMENTS", 2)
    assert len(PageVectors.from_json(_body()).segments) == 2
    with pytest.raises(ValueError, match="n ≤ 2"):
        PageVectors.from_json(_body(segments=[[0, 0, 10, 0]] * 3))


def test_empty_page_vectors_give_no_walls() -> None:
    """`segments` rỗng đọc được thành `(0, 4)` và không ra tường nào → `None`."""
    loaded = PageVectors.from_json(_body(segments=[], scaleN=None))
    assert loaded.segments.shape == (0, 4)
    assert loaded.scale_n is None
    assert vector_walls(loaded, evidence=np.ones((50, 50), dtype=np.bool_)) is None


def test_nested_forms_stop_at_depth_limit() -> None:
    """Form XObject lồng: nét trong form được đọc, nhưng sâu hơn `_MAX_FORM_DEPTH` tầng thì bỏ."""
    line = b"100 100 m 300 100 l S\n"
    forms = [line + b"/Fn Do\n"] * (pdf_vector._MAX_FORM_DEPTH + 2)
    vectors = pdf_page_vectors(make_pdf(1, size=PAGE, ops=b"/Fn Do\n", forms=forms), 0)
    assert len(vectors.segments) == pdf_vector._MAX_FORM_DEPTH


def test_segment_cap_stops_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chạm trần `_MAX_SEGMENTS` → dừng đọc object kế tiếp (K13): còn ít đoạn hơn trang đầy đủ."""
    data = _bands_pdf()
    full = len(pdf_page_vectors(data, 0).segments)
    monkeypatch.setattr(pdf_vector, "_MAX_SEGMENTS", 1)
    capped = len(pdf_page_vectors(data, 0).segments)
    assert 0 < capped < full


def test_bad_page_index_is_validation() -> None:
    """`page_index` ngoài khoảng → `VALIDATION` như đường dựng ảnh."""
    with pytest.raises(VisionError) as caught:
        pdf_page_vectors(_bands_pdf(), 3)
    assert caught.value.code == "VALIDATION"
