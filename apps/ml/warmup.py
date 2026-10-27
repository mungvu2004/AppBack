"""Làm ấm tiến trình con của worker `ml` (PERF-03 P3): lượt chạy đầu sau khởi động chậm thêm ~50 s.

Ba thứ nạp lười gây chậm: phiên ONNX (`load_onnx`), bộ dò chữ `_detector()` của OCR và lượt
tối ưu đồ thị đầu tiên của ORT. Ở `worker_process_init` mỗi con nạp sẵn mọi bản **ghim** có
ONNX trong `ML_MODELS_DIR` (cùng checksum nên lượt thật trúng cache của `load_onnx`), dựng
bộ dò và chạy một lượt suy luận giả nhỏ cho mỗi phiên.

`ml` không đọc DB (BE-00 §2.1) nên không biết bản storage nào đang kích hoạt: các bản đó vẫn
nạp ở lượt đầu. Lỗi khi làm ấm chỉ ghi cảnh báo — worker vẫn lên. `ML_WARMUP=0` tắt hẳn
(test/CI, `ml-train`); `ML_BACKEND=fake` không có gì để làm ấm.
"""

import logging
from pathlib import Path
from typing import Final

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
from celery.signals import worker_process_init
from numpy.typing import NDArray

from apps.ml.runtime.loader import load_onnx
from apps.ml.runtime.settings import get_ml_settings
from apps.ml.runtime.tasks_util import infer_context
from apps.ml.text.reader import _detect, _detector
from packages.messaging.tasks import runner
from packages.ml_contracts.payloads import ModelRef
from packages.ml_contracts.pinned import PINNED

_log: Final = logging.getLogger(__name__)

WARMUP_VERSION_ID: Final = "mdl_" + "0" * 26
"""`version_id` hình thức cho `ModelRef` ghim của lượt làm ấm; cache của `load_onnx` khoá theo checksum."""

DYNAMIC_DIM: Final = 64
"""Cỡ thay cho trục động (trừ trục lô = 1) của tensor giả: đủ nhỏ để lượt giả chạy nhanh."""

WARMUP_PAGE_PX: Final = 64


def dummy_feed(session: ort.InferenceSession) -> dict[str, NDArray[np.float32]] | None:
    """Tensor 0 cho mọi đầu vào float của phiên; `None` khi có đầu vào không phải float."""
    feed: dict[str, NDArray[np.float32]] = {}
    for spec in session.get_inputs():
        if spec.type != "tensor(float)":
            return None
        shape = [
            dim if isinstance(dim, int) and dim > 0 else (1 if axis == 0 else DYNAMIC_DIM)
            for axis, dim in enumerate(spec.shape)
        ]
        feed[spec.name] = np.zeros(shape, dtype=np.float32)
    return feed


def _warm_session(session: ort.InferenceSession) -> None:
    """Một lượt suy luận giả để ORT tối ưu đồ thị và cấp phát trước lượt thật."""
    feed = dummy_feed(session)
    if feed is not None:
        session.run(None, feed)


def _warm_ocr_detector() -> None:
    """Dựng `_detector()` (lru_cache của tiến trình) và dò một trang trắng nhỏ."""
    _detect(_detector(), np.full((WARMUP_PAGE_PX, WARMUP_PAGE_PX, 3), 255, dtype=np.uint8))


def warm_up() -> list[str]:
    """Làm ấm mọi thứ làm được, trả tên những gì đã ấm; lỗi của từng mục chỉ ghi cảnh báo."""
    settings = get_ml_settings()
    if not settings.ml_warmup or settings.ml_backend == "fake":
        return []
    warmed: list[str] = []
    models_dir = Path(settings.ml_models_dir)
    for name, pin in PINNED.items():
        if pin.onnx_sha256 is None or not (models_dir / f"{name}.onnx").is_file():
            continue
        try:
            ref = ModelRef(
                version_id=WARMUP_VERSION_ID,
                family=pin.family,
                weights_key=None,
                pinned_name=name,
                checksum_sha256=pin.onnx_sha256,
            )
            session = runner().run(load_onnx(infer_context().storage, ref, models_dir=models_dir))
            _warm_session(session)
            warmed.append(name)
        except Exception:  # noqa: BLE001 — làm ấm là tối ưu: lỗi lạ không được làm chết worker (P3)
            _log.warning("ml_warmup_failed", extra={"model": name}, exc_info=True)
    try:
        _warm_ocr_detector()
        warmed.append("ocrDetector")
    except Exception:  # noqa: BLE001 — như trên
        _log.warning("ml_warmup_failed", extra={"model": "ocrDetector"}, exc_info=True)
    _log.info("ml_warmup_done", extra={"warmed": warmed})
    return warmed


@worker_process_init.connect
def _warm_on_start(**_: object) -> None:
    """Mỗi con prefork làm ấm trước khi nhận task (phiên ORT là của riêng từng tiến trình)."""
    warm_up()
