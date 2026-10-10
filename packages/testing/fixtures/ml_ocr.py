"""Model OCR thật dùng chung cho `test_ocr.py` (runtime) và `test_reader_real.py` (text), PERF-01 BE-3.

`RapidOCR()` của wheel dựng lại tốn vài giây (hai phiên ONNX: dò + nhận dạng, cộng dồn qua các
hàm test từng gọi `RapidOCR()` riêng); dựng **một lần mỗi tiến trình pytest** (`lru_cache`) thay
vì mỗi hàm test, không đổi kết quả đọc vì cùng một engine mặc định của wheel.

Thu nhỏ khổ `render_plan` (1600x1200 → ~960x720) từng thử nhưng đo lại tỉ lệ đọc đúng tụt dưới
ngưỡng hiện có (0,726 < 0,8 và 0,906 < 0,95 trên seed 100-109): khổ nhỏ hơn đổi hẳn bố cục phòng
(`_layout` chọn lại `mm_per_px`/lưới theo khổ trang), không chỉ scale ảnh, nên không dùng được mà
không nới ngưỡng ([9] cấm) — xem `do-truoc-sau.md` BE-3.
"""

from functools import lru_cache

from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]  # wheel không có py.typed


@lru_cache(maxsize=1)
def wheel_engine() -> RapidOCR:
    """`RapidOCR()` mặc định của wheel (bộ phân loại góc vẫn bật; mỗi lượt gọi tự tắt bằng `use_cls=False`)."""
    return RapidOCR()
