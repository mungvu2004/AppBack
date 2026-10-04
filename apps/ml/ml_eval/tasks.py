"""Task `ml.infer.ml_eval.evaluate_version`: đo một bản model trên tập kiểm cố định (BE-00 §7, §9).

Ba đường theo dạng `ModelRef` (khối [6] "Task đánh giá"): `ML_BACKEND=fake` dùng bộ giả
tại chỗ, bản **ghim** là model của nhà cung cấp nên nạp tại chỗ, bản **storage** là model
người dùng nên chỉ nạp trong tiến trình con có trần bộ nhớ và trần thời gian (`sandbox`).

Luôn CPU: không `resolve_device`, không `gpu_slot`, không đọc DB. Giao lặp cho cùng số đo
nên chỉ gửi lại `evaluation_done` (`set_evaluation` của B6-01 tự idempotent, J06).
"""

import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from celery.exceptions import SoftTimeLimitExceeded

from apps.ml.ml_eval.evaluate import evaluate_family
from apps.ml.ml_eval.sandbox import RESULT_PREFIX, build_adapter
from apps.ml.ml_eval.settings import get_eval_settings
from apps.ml.runtime.child_env import allowlisted_env
from apps.ml.runtime.errors import MODEL_FORMAT_UNSUPPORTED
from apps.ml.runtime.loader import load_onnx, read_model_object
from apps.ml.runtime.tasks_util import infer_context
from packages.core.clock import SystemClock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.messaging.celery_app import send_task
from packages.messaging.tasks import TASK_TIMEOUT, PermanentError, define_task
from packages.ml_contracts.fakes import FakeObjectDetector, FakeTextReader, FakeWallSegmenter
from packages.ml_contracts.payloads import EvaluateVersionPayload, EvaluationDonePayload, ModelRef
from packages.ml_contracts.synthetic import EVAL_SET_SEEDS
from packages.storage.local import LocalDiskStorage

__all__ = ["EVALUATION_DONE_TASK", "EVAL_SEEDS", "ml_eval_evaluate_version", "on_failed", "run_sandbox"]

EVALUATION_DONE_TASK: Final = "default.training_bridge.evaluation_done"
EVAL_SEEDS: Sequence[int] = EVAL_SET_SEEDS
"""Tập kiểm của task, đọc **lúc chạy** qua thuộc tính module để test hạ xuống vài seed."""

MAX_ORT_THREADS: Final = 4
_ENV_KEEP: Final = frozenset({"PATH", "PYTHONPATH", "HOME", "LANG", "LC_ALL", "TMPDIR"})
_ENV_PREFIX: Final = ("ML_", "COVERAGE_")
"""`ML_*` là cấu hình con cần; `COVERAGE_*` để `coverage` đo được tiến trình con.

Giữ `COVERAGE_*` vô hại ở production: không tiến trình thật nào đặt chúng.
"""

_FAKES: Final[Mapping[str, Any]] = {
    "wallSegmentation": FakeWallSegmenter,
    "openingAndFurnitureDetection": FakeObjectDetector,
    "dimensionReading": FakeTextReader,
}


def on_failed(payload: EvaluateVersionPayload, code: str) -> None:
    """Báo đánh giá hỏng kèm mã cho cầu nối B6-03a (chữ ký `on_failed` của `define_task`).

    Lệch khỏi prompt [6]: prompt ghi `metrics={}`, nhưng `EvaluationDonePayload` đòi
    `metrics is None` khi `status="failed"` — theo schema.
    """
    send_task(
        EVALUATION_DONE_TASK,
        EvaluationDonePayload(version_id=payload.version_id, status="failed", metrics=None, error_code=code),
    )


def _child_env() -> dict[str, str]:
    """Môi trường tối thiểu của con: không khoá, không biến kho; luồng và arena bị chặn trên."""
    env = allowlisted_env(_ENV_KEEP, _ENV_PREFIX)
    threads = min(int(env.get("ML_ORT_THREADS", "1") or "1"), MAX_ORT_THREADS)
    env["ML_ORT_THREADS"] = str(threads)
    env["MALLOC_ARENA_MAX"] = "2"
    env["OMP_NUM_THREADS"] = str(MAX_ORT_THREADS)
    return env


def _kill_group(proc: "subprocess.Popen[str]") -> None:
    """Giết cả nhóm tiến trình con (nó có session riêng) rồi gặt, để không bỏ lại con mồ côi."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()


def _result(out: str, returncode: int) -> dict[str, float]:
    """Diễn giải dòng kết quả (có `RESULT_PREFIX`) trong stdout cùng mã thoát của con thành số đo hay lỗi có mã.

    `SIGKILL` mà cha **không** giết là OOM của cgroup `ml` dùng chung với huấn luyện —
    lỗi tạm của hạ tầng, không phải lỗi của model: `DEPENDENCY_UNAVAILABLE` → J02 thử
    lại, hết lượt thì `define_task` báo `RETRY_EXHAUSTED`.
    """
    lines = [line for line in out.splitlines() if line.startswith(RESULT_PREFIX)]
    try:
        reply = json.loads(lines[-1][len(RESULT_PREFIX) :]) if lines else {}
    except json.JSONDecodeError:
        reply = {}
    code = reply.get("code")
    if isinstance(code, str):
        raise PermanentError(code)
    metrics = reply.get("metrics")
    if returncode == 0 and isinstance(metrics, dict):
        return {str(key): float(value) for key, value in metrics.items()}
    if returncode == -signal.SIGKILL:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=5)
    raise PermanentError(MODEL_FORMAT_UNSUPPORTED)


async def run_sandbox(data: bytes, ref: ModelRef, seeds: Sequence[int]) -> dict[str, float]:
    """Chạy `evaluate_family` trên bytes trọng số trong một tiến trình con có trần (khối [6] "Hộp cát").

    Bytes đã nằm trong bộ nhớ cha (đọc từ kho với trần của bộ nạp); con chỉ thấy một thư
    mục tạm chứa đúng object ấy, nên nó không có khoá, không có client kho nào. Checksum
    và luật "ONNX không tin" vẫn do `load_onnx` kiểm trong con.
    """
    settings = get_eval_settings()
    with tempfile.TemporaryDirectory(prefix="ml-eval-") as tmp:
        key = str(ref.weights_key)
        await LocalDiskStorage(Path(tmp), SystemClock(), None).put(
            key, data, content_type="application/octet-stream", max_bytes=len(data) + 1
        )
        request = json.dumps(
            {
                "dir": tmp,
                "ref": ref.model_dump(mode="json"),
                "seeds": list(seeds),
                "max_bytes": settings.ml_eval_max_bytes,
            }
        )
        proc = subprocess.Popen(  # noqa: ASYNC220 — chờ con đồng bộ để tín hiệu quá hạn mềm tới đúng chỗ
            [sys.executable, "-m", "apps.ml.ml_eval.sandbox"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            start_new_session=True,
            env=_child_env(),
            text=True,
        )
        try:
            out, _ = proc.communicate(request, timeout=settings.ml_eval_timeout_s)
        except subprocess.TimeoutExpired as exc:
            _kill_group(proc)
            raise PermanentError(TASK_TIMEOUT) from exc
        except SoftTimeLimitExceeded:
            _kill_group(proc)
            raise
    return _result(out, proc.returncode)


async def _metrics(payload: EvaluateVersionPayload) -> dict[str, float]:
    """Số đo của bản model, theo đúng một trong ba đường của khối [6] bước 1."""
    context = infer_context()
    ref = payload.model
    if context.settings.ml_backend == "fake":
        return evaluate_family(ref.family, _FAKES[ref.family](), seeds=EVAL_SEEDS)
    if ref.pinned_name is not None:
        session = await load_onnx(context.storage, ref, models_dir=Path(context.settings.ml_models_dir))
        return evaluate_family(ref.family, build_adapter(ref, session), seeds=EVAL_SEEDS)
    data = await read_model_object(context.storage, str(ref.weights_key))
    return await run_sandbox(data, ref, EVAL_SEEDS)


@define_task(name="ml.infer.ml_eval.evaluate_version", payload=EvaluateVersionPayload, on_failed=on_failed)
async def ml_eval_evaluate_version(payload: EvaluateVersionPayload) -> None:
    """Đo một bản model trên tập kiểm cố định rồi báo cho cầu nối huấn luyện (J01, J06)."""
    metrics = await _metrics(payload)
    send_task(
        EVALUATION_DONE_TASK,
        EvaluationDonePayload(version_id=payload.version_id, status="completed", metrics=metrics, error_code=None),
    )
