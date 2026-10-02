"""Trần và tín hiệu của hộp cát đánh giá (khối [8] "Task đánh giá", hai mục `sandbox`).

Hộp cát là tiến trình thật: không mock `subprocess`, `onnxruntime` hay Celery (K23). Ba
đường thoát của tiến trình con được kiểm riêng — chạm `RLIMIT_AS`, quá hạn, bị `SIGKILL`
từ ngoài — vì mỗi đường cho một mã khác và chỉ đường thứ ba là lỗi **tạm**.
"""

import asyncio
import contextlib
import os
import resource
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from apps.ml.ml_eval import tasks
from apps.ml.ml_eval.tests.helpers import NUM_CLASSES, SEEDS, const_yolo, pinned_ref
from apps.ml.objects.tests.onnx_models import load_session, make_const_yolo, storage_ref, yolo_output
from apps.ml.runtime.errors import MODEL_FORMAT_UNSUPPORTED
from packages.core.clock import SystemClock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.messaging.tasks import TASK_TIMEOUT, PermanentError
from packages.storage.local import LocalDiskStorage

WAIT_S = 60.0
KILL_WAIT_S = 45.0


def _fat_yolo() -> bytes:
    """ONNX hợp lệ nhưng hằng đầu ra ~256 MiB: nạp nó là vượt mọi trần nhỏ của test."""
    big: NDArray[np.float32] = np.zeros((1, 4 + NUM_CLASSES, 4_400_000), dtype=np.float32)
    return make_const_yolo(big, input_shape=(1, 3, 640, 640))


def _run(data: bytes) -> dict[str, float]:
    """Chạy hộp cát trên bytes model, dùng `ModelRef` dạng storage của chính bytes ấy."""
    ref, _ = storage_ref(data)
    return asyncio.run(tasks.run_sandbox(data, ref, SEEDS))


def _limits_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ca trần bộ nhớ: model cấp phát vượt `ML_EVAL_MAX_BYTES` nhỏ → `MODEL_FORMAT_UNSUPPORTED`, cha còn sống."""
    monkeypatch.setenv("ML_EVAL_MAX_BYTES", str(64 * 1024 * 1024))
    with pytest.raises(PermanentError) as caught:
        _run(_fat_yolo())
    assert caught.value.code == MODEL_FORMAT_UNSUPPORTED
    assert os.getpid() > 0


def _limits_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ca quá hạn: `ML_EVAL_TIMEOUT_S` nhỏ → `TASK_TIMEOUT`; cả nhóm tiến trình con đã chết."""
    monkeypatch.setenv("ML_EVAL_TIMEOUT_S", "0.2")
    pids: list[int] = []
    real = subprocess.Popen

    def spy(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        """Ghi lại pid của con để kiểm nó đã chết sau khi hộp cát bỏ cuộc."""
        proc: subprocess.Popen[str] = real(*args, **kwargs)  # type: ignore[call-overload]  # chuyển tiếp nguyên vẹn
        pids.append(proc.pid)
        return proc

    monkeypatch.setattr(subprocess, "Popen", spy)
    with pytest.raises(PermanentError) as caught:
        _run(const_yolo())
    assert caught.value.code == TASK_TIMEOUT
    (pid,) = pids
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def _limits_killed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ca bị giết: con nhận `SIGKILL` từ ngoài (OOM cgroup) → lỗi **tạm** `DEPENDENCY_UNAVAILABLE`.

    Hạ `ML_EVAL_TIMEOUT_S` xuống `KILL_WAIT_S`: nếu cha không nhận ra con đã chết thì test
    hỏng ở `TASK_TIMEOUT` sau ngần ấy giây chứ không treo cả lượt cổng.
    """
    monkeypatch.setenv("ML_EVAL_TIMEOUT_S", str(KILL_WAIT_S))
    real = subprocess.Popen

    def spy(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        """Dựng con rồi hẹn một luồng giết nó, giả lập OOM của cgroup dùng chung."""
        proc: subprocess.Popen[str] = real(*args, **kwargs)  # type: ignore[call-overload]  # chuyển tiếp nguyên vẹn
        threading.Timer(0.3, lambda: _kill(proc.pid)).start()
        return proc

    monkeypatch.setattr(subprocess, "Popen", spy)
    with pytest.raises(AppError) as caught:
        _run(const_yolo())
    assert caught.value.code is DEPENDENCY_UNAVAILABLE


def _kill(pid: int) -> None:
    """Giết tiến trình con, bỏ qua trường hợp nó đã thoát trước."""
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)


def test_ml_eval_sandbox_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ba đường thoát của trần hộp cát, mỗi ca một ngữ cảnh `monkeypatch` riêng (khối [8]).

    Một test cho cả ba vì khối [8] gọi tên đúng như vậy; mỗi ca vẫn tách thành một hàm
    để hỏng ở đâu thì stack chỉ thẳng vào đó.
    """
    for case in (_limits_memory, _limits_timeout, _limits_killed):
        with monkeypatch.context() as patched:
            case(patched)


def test_ml_eval_sandbox_child_env_is_minimal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con không thấy khoá nào; luồng và arena bị chặn trên (khối [6] "Hộp cát")."""
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s3cret")
    monkeypatch.setenv("ML_ORT_THREADS", "32")
    env = tasks._child_env()
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert env["ML_ORT_THREADS"] == str(tasks.MAX_ORT_THREADS)
    assert env["MALLOC_ARENA_MAX"] == "2"
    assert env["PYTHONPATH"]


def test_ml_eval_sandbox_real_size(tmp_path: Path) -> None:
    """ONNX thật cỡ `yolov8n` (`imgsz=640`, 11 lớp), trần mặc định → số đo, không chạm trần.

    Cờ ngoại tuyến đặt bằng `prepare_ultralytics()` của trainer — một chỗ duy nhất trong repo
    biết bộ cờ `YOLO_*` và thư mục cấu hình 0700 (R-02).
    """
    from apps.ml.runtime.export_yolo import export_yolo
    from apps.ml.training_yolo.trainer import prepare_ultralytics

    config = prepare_ultralytics()
    (config / "Arial.ttf").touch()  # `check_font` còn tìm ngay dưới `YOLO_CONFIG_DIR`
    import ultralytics

    cfg = tmp_path / "yolov8n.yaml"
    cfg.write_text(_yolo_cfg_with_11_classes(), encoding="utf-8")
    model: Any = ultralytics.YOLO(cfg)  # type: ignore[attr-defined]  # ultralytics không khai __all__
    pt_path = tmp_path / "yolov8n.pt"
    model.save(pt_path)
    onnx_path = tmp_path / "model.onnx"
    export_yolo(pt_path, onnx_path, source_sha256=_sha256(pt_path), imgsz=640)
    metrics = _run(onnx_path.read_bytes())
    assert list(metrics) == ["map50"]
    assert 0.0 <= metrics["map50"] <= 1.0


def _yolo_cfg_with_11_classes() -> str:
    """Bản `yolov8n.yaml` của wheel với `nc = 11`: đầu ra ONNX đúng `4 + len(ARTIFACT_LABELS)` kênh."""
    import re

    from ultralytics.utils import ROOT  # nhập sau khi đặt cờ ngoại tuyến

    source = (Path(ROOT) / "cfg" / "models" / "v8" / "yolov8.yaml").read_text(encoding="utf-8")
    return re.sub(r"^nc:.*$", f"nc: {NUM_CLASSES}", source, count=1, flags=re.MULTILINE)


def _sha256(path: Path) -> str:
    """SHA-256 của một tệp, theo khúc (dùng lại hàm của `packages.ml_contracts.pinned`)."""
    from packages.ml_contracts.pinned import file_sha256

    return str(file_sha256(path))


def test_ml_eval_sandbox_main_reports_code(tmp_path: Path) -> None:
    """Gọi thẳng `sandbox.main`: model sai số kênh cho một dòng JSON mang mã, không ném."""
    import io
    import json

    from apps.ml.ml_eval import sandbox

    data = make_const_yolo(yolo_output([], nc=NUM_CLASSES + 1), input_shape=(1, 3, 640, 640))
    ref, key = storage_ref(data)
    storage = LocalDiskStorage(tmp_path, SystemClock(), None)
    asyncio.run(storage.put(str(key), data, content_type="application/octet-stream", max_bytes=len(data) + 1))
    request = {
        "dir": str(tmp_path),
        "ref": ref.model_dump(mode="json"),
        "seeds": list(SEEDS),
        "max_bytes": resource.getrlimit(resource.RLIMIT_AS)[1],
    }
    out = io.StringIO()
    limit = resource.getrlimit(resource.RLIMIT_AS)
    try:
        sandbox.main(io.StringIO(json.dumps(request)), out)
    finally:
        resource.setrlimit(resource.RLIMIT_AS, limit)  # `main` đặt trần cho chính tiến trình pytest
    assert json.loads(out.getvalue()) == {"code": MODEL_FORMAT_UNSUPPORTED}


def test_ml_eval_sandbox_kills_group_on_soft_time_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quá hạn mềm của Celery trong lúc chờ con: con bị giết, ngoại lệ đi tiếp (J05)."""
    from celery.exceptions import SoftTimeLimitExceeded

    pids: list[int] = []
    real = subprocess.Popen

    def spy(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        """Dựng con thật rồi làm `communicate` của nó ném quá hạn mềm."""
        proc: subprocess.Popen[str] = real(*args, **kwargs)  # type: ignore[call-overload]  # chuyển tiếp nguyên vẹn
        pids.append(proc.pid)

        def raising(*_args: object, **_kwargs: object) -> tuple[str, str]:
            """Giả lập tín hiệu quá hạn mềm tới đúng lúc cha đang chờ con."""
            raise SoftTimeLimitExceeded

        monkeypatch.setattr(proc, "communicate", raising)
        return proc

    monkeypatch.setattr(subprocess, "Popen", spy)
    with pytest.raises(SoftTimeLimitExceeded):
        _run(const_yolo())
    (pid,) = pids
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise AssertionError("tiến trình con vẫn sống sau khi hộp cát bỏ cuộc")


def test_ml_eval_sandbox_reply_on_memory_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con chạm `RLIMIT_AS` giữa lúc nạp: trả mã định dạng chứ không để `MemoryError` lọt ra."""
    from apps.ml.ml_eval import sandbox

    def out_of_memory(_request: dict[str, object]) -> dict[str, float]:
        """Thay vòng đánh giá bằng một lần chạm trần bộ nhớ."""
        raise MemoryError

    monkeypatch.setattr(sandbox, "_evaluate", out_of_memory)
    assert sandbox._reply({}) == {"code": MODEL_FORMAT_UNSUPPORTED}


@pytest.mark.parametrize(
    ("out", "returncode"),
    [("", 1), ("không phải json", 0), ('{"metrics": null}', 0), ('{"metrics": {}}', 2)],
)
def test_ml_eval_sandbox_result_without_metrics(out: str, returncode: int) -> None:
    """Stdout không mang số đo dùng được → `MODEL_FORMAT_UNSUPPORTED`, bất kể mã thoát."""
    with pytest.raises(PermanentError) as caught:
        tasks._result(out, returncode)
    assert caught.value.code == MODEL_FORMAT_UNSUPPORTED


def test_ml_eval_sandbox_kill_group_tolerates_dead_child() -> None:
    """Con đã thoát trước khi cha giết: `_kill_group` im lặng gặt xác, không ném."""
    proc = subprocess.Popen(  # argv cố định của test
        [sys.executable, "-c", "pass"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        start_new_session=True,
        text=True,
    )
    proc.wait()
    tasks._kill_group(proc)
    assert proc.returncode == 0


@pytest.mark.parametrize("family", ["wallSegmentation", "dimensionReading"])
def test_ml_eval_sandbox_build_adapter_rejects_wrong_family_model(family: str) -> None:
    """Adapter của hai họ còn lại từ chối phiên YOLO: mỗi họ một nhánh của `build_adapter`.

    Phiên `onnxruntime` là thật (K23); chỉ hình dạng của nó sai với họ được yêu cầu.
    """
    from apps.ml.ml_eval import sandbox

    session = load_session(LocalDiskStorage(Path(mkdtemp()), SystemClock(), None), const_yolo())
    with pytest.raises(PermanentError):
        sandbox.build_adapter(pinned_ref(family), session)
