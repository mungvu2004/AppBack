"""Làm ấm `ml` (PERF-03 P3): tắt được bằng `ML_WARMUP=0`, lỗi không làm chết worker, lượt giả chạy thật."""

import logging
from pathlib import Path
from types import SimpleNamespace

import onnx
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import pytest
from onnx import TensorProto, helper

from apps.ml import warmup
from packages.ml_contracts.payloads import ModelRef
from packages.ml_contracts.pinned import PINNED


def _identity_session() -> ort.InferenceSession:
    """Phiên ORT nhỏ `Identity` có trục lô và trục rộng động, như model rec của OCR."""
    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, ["N", 3, "W"])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, ["N", 3, "W"])
    graph = helper.make_graph([helper.make_node("Identity", ["x"], ["y"])], "g", [x], [y])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    return ort.InferenceSession(model.SerializeToString(), providers=["CPUExecutionProvider"])


@pytest.fixture
def warm_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Bật làm ấm, `ML_MODELS_DIR` tạm có tệp `yolov8n.onnx`, kho giả (bản ghim không đọc kho)."""
    monkeypatch.setenv("ML_WARMUP", "1")
    monkeypatch.setenv("ML_BACKEND", "onnx")
    monkeypatch.setenv("ML_MODELS_DIR", str(tmp_path))
    (tmp_path / "yolov8n.onnx").write_bytes(b"\x08")
    monkeypatch.setattr(warmup, "infer_context", lambda: SimpleNamespace(storage=None))
    monkeypatch.setattr(warmup, "_warm_ocr_detector", lambda: None)
    return tmp_path


def test_dummy_feed_fills_dynamic_axes() -> None:
    """Trục lô động → 1, trục khác động → `DYNAMIC_DIM`, trục cố định giữ nguyên."""
    feed = warmup.dummy_feed(_identity_session())
    assert feed is not None
    assert feed["x"].shape == (1, 3, warmup.DYNAMIC_DIM)


def test_warm_up_is_off_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ML_WARMUP=0` (mặc định của test, CI, `ml-train`): không nạp gì, không chạy gì."""
    monkeypatch.setenv("ML_WARMUP", "0")
    called: list[str] = []
    monkeypatch.setattr(warmup, "_warm_ocr_detector", lambda: called.append("ocr"))
    assert warmup.warm_up() == []
    assert called == []


def test_warm_up_loads_pinned_and_runs_a_dummy_pass(warm_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bản ghim có tệp ONNX được nạp qua `load_onnx` với checksum ghim (lượt thật trúng cache)."""
    refs: list[ModelRef] = []
    session = _identity_session()

    async def fake_load(_storage: object, ref: ModelRef, *, models_dir: Path) -> ort.InferenceSession:
        """Ghi lại `ModelRef` được xin, trả phiên nhỏ thật."""
        refs.append(ref)
        return session

    monkeypatch.setattr(warmup, "load_onnx", fake_load)
    assert warmup.warm_up() == ["yolov8n", "ocrDetector"]
    assert [ref.pinned_name for ref in refs] == ["yolov8n"]
    assert refs[0].checksum_sha256 == PINNED["yolov8n"].onnx_sha256


def test_warm_up_failure_only_warns(
    warm_env: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Case lỗi: model hỏng và bộ dò hỏng chỉ ghi cảnh báo — `warm_up` không ném, worker vẫn lên."""

    async def broken_load(*_: object, **__: object) -> ort.InferenceSession:
        """Nạp hỏng như một tệp ONNX sai checksum."""
        raise RuntimeError("hỏng")

    def broken_detector() -> None:
        """Bộ dò dựng hỏng."""
        raise RuntimeError("hỏng")

    monkeypatch.setattr(warmup, "load_onnx", broken_load)
    monkeypatch.setattr(warmup, "_warm_ocr_detector", broken_detector)
    with caplog.at_level(logging.WARNING, logger=warmup.__name__):
        assert warmup.warm_up() == []
    assert [record.message for record in caplog.records].count("ml_warmup_failed") == 2


def test_warm_session_skips_non_float_inputs() -> None:
    """Đầu vào không phải float → `dummy_feed` trả `None`, không chạy lượt giả nào."""
    spec = SimpleNamespace(name="ids", type="tensor(int64)", shape=[1, 8])

    def run(*_: object) -> None:
        """Không được gọi: không dựng được tensor giả cho đầu vào nguyên."""
        raise AssertionError("không được chạy")

    session = SimpleNamespace(get_inputs=lambda: [spec], run=run)
    assert warmup.dummy_feed(session) is None
    warmup._warm_session(session)


def test_warm_ocr_detector_runs_one_white_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bộ dò OCR được dựng và dò một trang trắng `WARMUP_PAGE_PX` vuông, 3 kênh."""
    pages: list[tuple[object, tuple[int, ...], int]] = []
    detector = object()
    monkeypatch.setattr(warmup, "_detector", lambda: detector)
    monkeypatch.setattr(warmup, "_detect", lambda det, page: pages.append((det, page.shape, int(page.min()))))
    warmup._warm_ocr_detector()
    assert pages == [(detector, (warmup.WARMUP_PAGE_PX, warmup.WARMUP_PAGE_PX, 3), 255)]


def test_worker_process_init_warms_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """Receiver `worker_process_init` gọi `warm_up` một lần cho mỗi con prefork."""
    calls: list[str] = []

    def fake_warm_up() -> list[str]:
        """Ghi lại lượt gọi."""
        calls.append("warm")
        return []

    monkeypatch.setattr(warmup, "warm_up", fake_warm_up)
    warmup._warm_on_start(sender=None)
    assert calls == ["warm"]
