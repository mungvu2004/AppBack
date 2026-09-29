"""Bước đọc chữ của worker `ml` (`dimensionReading`): bộ đọc OCR và task `ml.infer.text.read`.

Nhập gói này kéo theo `onnxruntime` và wheel `rapidocr-onnxruntime` — **không** `torch`
(M03). Hàm thuần đọc số và nhãn phòng nằm ở `packages.vision.dimensions`, gói ấy không
được nhập `apps.*` nên hai bên chỉ gặp nhau ở B5-05.

**Không** xuất lại `text_read` ở đây (lệch [5], xem báo cáo): sổ task chỉ nhận mỗi tên
một lần, mà `apps.ml.text` bị nhập cả qua `discover_submodules("apps.ml", "tasks")` lẫn
qua `importlib.util.find_spec("apps.ml.text.trainer")` của `discover_trainers` — nhập
`tasks` từ `__init__` biến hai đường ấy thành hai lượt khai cùng một task. Người gọi lấy
task ở `apps.ml.text.tasks`, đúng như mọi module có `tasks.py` khác trong repo.
"""

from apps.ml.text.reader import (
    DET_OVERLAP_PX,
    DET_TILE_PX,
    MAX_TEXT_ITEMS,
    REC_HEIGHT_PX,
    REC_MAX_WIDTH_PX,
    TEXT_CONFIDENCE_MIN,
    RapidOcrReader,
    ctc_decode,
    rec_characters,
)

__all__ = [
    "DET_OVERLAP_PX",
    "DET_TILE_PX",
    "MAX_TEXT_ITEMS",
    "REC_HEIGHT_PX",
    "REC_MAX_WIDTH_PX",
    "TEXT_CONFIDENCE_MIN",
    "RapidOcrReader",
    "ctc_decode",
    "rec_characters",
]
