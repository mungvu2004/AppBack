"""Luật phân loại `classify_region` và đo tín hiệu `measure_signals` trên ảnh tổng hợp."""

import cv2
import numpy as np

from packages.vision.drawing_kind import Classification, RegionSignals, TitleText, classify_region, measure_signals
from packages.vision.layout import Box
from packages.vision.preprocess.types import RgbImage


def _signals(
    titles: tuple[str, ...] | None = None,
    *,
    saturated: float = 0.0,
    ground_line: bool = False,
    vertical: float = 0.5,
    area: float = 0.3,
    density: float = 0.0,
) -> RegionSignals:
    """Tín hiệu mặc định "bản vẽ nét đen, không đường đất, không OCR"; ghi đè từng trường theo test."""
    return RegionSignals(saturated, titles, ground_line, vertical, area, density)


def test_classify_region__keyword_section() -> None:
    """Từ khoá mặt cắt + hình học đường đất (không mâu thuẫn) ⇒ `section`."""
    result = classify_region(_signals(("MẶT CẮT 1-1",), ground_line=True, vertical=0.1))
    assert result.drawing_type == "section"
    assert result.reasons == ("Chữ 'MẶT CẮT 1-1' ven vùng gợi ý mặt cắt",)


def test_classify_region__keyword_conflict_unknown() -> None:
    """Từ khoá mặt bằng trái hình học mặt cắt, hoặc hai loại từ khoá ⇒ `unknown` kèm lý do."""
    geo = classify_region(_signals(("MẶT BẰNG TẦNG 1",), ground_line=True, vertical=0.1))
    assert geo.drawing_type == "unknown"
    assert "đường đất" in geo.reasons[-1]
    two = classify_region(_signals(("MẶT BẰNG", "MẶT CẮT A-A")))
    assert two.drawing_type == "unknown"
    assert two.reasons[-1] == "Chữ tiêu đề gợi ý nhiều loại khác nhau"


def test_classify_region__saturated_other() -> None:
    """Nhiều điểm ảnh màu ⇒ `other` dù có từ khoá."""
    result = classify_region(_signals(("MẶT BẰNG",), saturated=0.4))
    assert result == Classification("other", ("40 % điểm ảnh có màu đậm, giống ảnh render hoặc ảnh chụp",))


def test_classify_region__no_signal_unknown() -> None:
    """Không OCR, không chữ, hay chữ chỉ chứa từ khoá ngắn dính trong từ khác ⇒ `unknown`."""
    for titles in (None, (), ("MBA 3 PHA", "ACT 2")):
        assert classify_region(_signals(titles)).drawing_type == "unknown"


def test_classify_region__unaccented_match() -> None:
    """Chữ không dấu "MAT CAT A-A" vẫn khớp mặt cắt; từ khoá ngắn nguyên từ cũng khớp."""
    assert classify_region(_signals(("MAT CAT A-A",))).drawing_type == "section"
    assert classify_region(_signals(("MB-01",))).drawing_type == "floorPlan"


def test_classify_region__accented_match() -> None:
    """Chữ có dấu (kể cả "Đ", chữ thường) khớp sau chuẩn hoá; lý do giữ nguyên văn."""
    result = classify_region(_signals(("MẶT BẰNG TẦNG 1",)))
    assert result == Classification("floorPlan", ("Chữ 'MẶT BẰNG TẦNG 1' ven vùng gợi ý mặt bằng",))
    assert classify_region(_signals(("mặt đứng chính",))).drawing_type == "elevation"
    assert classify_region(_signals(("Chi tiết cầu thang",))).drawing_type == "detail"


def test_classify_region__small_dense_text_other() -> None:
    """Vùng nhỏ chữ dày đặc (khung tên) ⇒ `other`; vùng lớn cùng mật độ thì không."""
    assert classify_region(_signals(area=0.05, density=0.4)).drawing_type == "other"
    assert classify_region(_signals(area=0.3, density=0.4)).drawing_type == "unknown"


def _blank(h: int = 800, w: int = 1000) -> np.ndarray:
    """Trang trắng RGB."""
    return np.full((h, w, 3), 255, np.uint8)


def test_measure_signals__ground_line() -> None:
    """Đường đất + nét dọc ngắn ⇒ ground_line, ít nét dọc; mặt bằng kín ⇒ nhiều nét dọc; lọc chữ theo dải."""
    region = Box(0.1, 0.1, 0.9, 0.7)  # pixel x 100..900, y 80..560
    section = _blank()
    cv2.line(section, (110, 500), (890, 500), (0, 0, 0), 3)
    for x in range(200, 800, 150):
        cv2.line(section, (x, 420), (x, 500), (0, 0, 0), 3)
    titles = (
        TitleText("MẶT CẮT A-A", Box(0.4, 0.72, 0.6, 0.76)),  # ngay dưới vùng
        TitleText("GHI CHÚ", Box(0.4, 0.9, 0.6, 0.95)),  # quá xa dưới
        TitleText("TRÁI", Box(0.0, 0.72, 0.05, 0.76)),  # ngoài khoảng ngang
        TitleText("TRONG", Box(0.4, 0.3, 0.6, 0.36)),  # trong vùng: chỉ tính mật độ
    )
    s = measure_signals(RgbImage(section), region, titles)
    assert s.ground_line
    assert s.long_vertical_ratio < 0.35
    assert s.titles == ("MẶT CẮT A-A",)
    assert s.saturated_ratio == 0.0
    assert abs(s.area_ratio - 0.48) < 1e-9
    assert abs(s.text_density - 0.012 / 0.48) < 1e-9
    assert classify_region(s).drawing_type == "section"

    plan = _blank()
    cv2.rectangle(plan, (150, 120), (850, 540), (0, 0, 0), 4)
    cv2.line(plan, (500, 120), (500, 540), (0, 0, 0), 3)
    p = measure_signals(RgbImage(plan), region, None)
    assert p.long_vertical_ratio >= 0.35
    assert (p.titles, p.text_density) == (None, 0.0)

    top_only = _blank()
    cv2.line(top_only, (110, 150), (890, 150), (0, 0, 0), 3)
    top_only[600:, :] = (255, 0, 0)  # màu ngoài vùng không tính
    t = measure_signals(RgbImage(top_only), region, ())
    assert not t.ground_line
    assert t.saturated_ratio == 0.0

    color = _blank()
    color[80:560, 100:900] = (200, 60, 40)
    assert measure_signals(RgbImage(color), region, None).saturated_ratio > 0.9
