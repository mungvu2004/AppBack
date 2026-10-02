"""Tiến trình con của hộp cát đánh giá: nạp model người dùng và chạy vòng đánh giá, cách ly.

Chạy bằng `python -m apps.ml.ml_eval.sandbox`. Giao thức: **một** object JSON vào stdin,
**một** dòng JSON ra stdout — `{"metrics": {...}}` hay `{"code": "<mã>"}`; mọi thứ khác
(thoát ≠ 0, tín hiệu) do tiến trình cha diễn giải.

Bất biến: `RLIMIT_AS` đặt **trước** lần nhập `onnxruntime`/`apps.ml.runtime` đầu tiên —
ORT cấp bộ nhớ ngay lúc nhập, trần đặt sau là trần không có tác dụng. Vì vậy mọi nhập
nặng nằm trong `_evaluate`, mức module chỉ có thư viện chuẩn.

Con **không** cầm khoá hay client storage nào: cha chép bytes trọng số vào một thư mục
tạm và con dựng `LocalDiskStorage` trên thư mục ấy, nên lỗi tạm của kho thật (J02) xảy ra
ở cha, còn checksum và luật "ONNX không tin" vẫn do chính `load_onnx` kiểm ở đây.
"""

import json
import resource
import sys
from typing import IO, Any, Final

__all__ = ["main"]

MODEL_FORMAT_UNSUPPORTED: Final = "MODEL_FORMAT_UNSUPPORTED"
"""Lặp lại hằng của `apps.ml.runtime.errors`: module ấy kéo `onnxruntime` vào."""


def build_adapter(ref: Any, session: Any) -> Any:
    """Adapter của họ model trên một phiên ONNX đã kiểm (khối [6] bước 2).

    Ở đây chứ không ở `tasks.py` để tiến trình con khỏi nhập module task (và cả Celery
    của nó) chỉ để dựng adapter; `tasks.py` nhập ngược lại từ đây.
    """
    from apps.ml.objects.detector import YoloOnnxDetector
    from apps.ml.objects.labels import labels_for
    from apps.ml.text.reader import RapidOcrReader
    from apps.ml.walls.segformer import SegformerOnnxSegmenter

    if ref.family == "wallSegmentation":
        return SegformerOnnxSegmenter(session)
    if ref.family == "openingAndFurnitureDetection":
        return YoloOnnxDetector(session, labels_for(ref))
    return RapidOcrReader.from_session(session, pinned_name=ref.pinned_name)


def _evaluate(request: dict[str, Any]) -> dict[str, float]:
    """Nạp trọng số từ thư mục cha đưa rồi chạy `evaluate_family`; mọi nhập nặng ở đây."""
    import asyncio
    from pathlib import Path

    from apps.ml.ml_eval.evaluate import evaluate_family
    from apps.ml.runtime.loader import load_onnx
    from packages.core.clock import SystemClock
    from packages.ml_contracts.payloads import ModelRef
    from packages.storage.local import LocalDiskStorage

    root = Path(request["dir"])
    ref = ModelRef.model_validate(request["ref"])
    storage = LocalDiskStorage(root, SystemClock(), None)
    session = asyncio.run(load_onnx(storage, ref, models_dir=root))
    return evaluate_family(ref.family, build_adapter(ref, session), seeds=request["seeds"])


def _reply(request: dict[str, Any]) -> dict[str, Any]:
    """Kết quả hay mã lỗi của một yêu cầu; `MemoryError` (chạm `RLIMIT_AS`) là lỗi định dạng."""
    from packages.messaging.tasks import PermanentError

    try:
        return {"metrics": _evaluate(request)}
    except PermanentError as exc:
        return {"code": exc.code}
    except MemoryError:
        return {"code": MODEL_FORMAT_UNSUPPORTED}


def main(stdin: IO[str], stdout: IO[str]) -> None:
    """Đọc yêu cầu, đặt trần bộ nhớ, ghi đúng một dòng JSON ra `stdout`.

    Nhận luồng làm tham số để test gọi thẳng được (không cần dựng tiến trình).
    """
    request = json.load(stdin)
    max_bytes = int(request["max_bytes"])
    resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
    stdout.write(json.dumps(_reply(request)) + "\n")
    stdout.flush()


if __name__ == "__main__":
    main(sys.stdin, sys.stdout)
