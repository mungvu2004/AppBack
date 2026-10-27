"""Chọn providers `onnxruntime` theo `ML_DEVICE` (PERF-03 P1): CUDA khi có, lỗi CUDA → CPU."""

import logging
from typing import Any

import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import pytest

from apps.ml.runtime import loader
from apps.ml.runtime.loader import CPU_PROVIDERS, CUDA_PROVIDERS, select_providers
from apps.ml.runtime.tests.helpers import add_model

WITH_CUDA = ["CUDAExecutionProvider", "CPUExecutionProvider"]
CPU_ONLY = ["CPUExecutionProvider"]


@pytest.mark.parametrize(
    ("device", "available", "expected"),
    [
        ("cpu", WITH_CUDA, CPU_PROVIDERS),
        ("cpu", CPU_ONLY, CPU_PROVIDERS),
        ("auto", WITH_CUDA, CUDA_PROVIDERS),
        ("auto", CPU_ONLY, CPU_PROVIDERS),
        ("cuda", WITH_CUDA, CUDA_PROVIDERS),
        ("cuda", CPU_ONLY, CUDA_PROVIDERS),
    ],
)
def test_select_providers(
    monkeypatch: pytest.MonkeyPatch, device: Any, available: list[str], expected: tuple[str, ...]
) -> None:
    """`cpu` luôn CPU; `auto` chỉ CUDA khi bản ORT có provider; `cuda` luôn thử CUDA (lỗi thì `_session` lùi)."""
    monkeypatch.setattr(loader.ort, "get_available_providers", lambda: available)
    assert select_providers(device) == expected


def test_cuda_session_error_falls_back_to_cpu(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Tạo phiên CUDA ném lỗi → cảnh báo một lần, phiên trả về chạy CPU."""
    real = ort.InferenceSession

    def fake(data: bytes, *, sess_options: Any, providers: list[str]) -> Any:
        """Ném như ORT thiếu libcudnn khi có CUDA trong `providers`, không thì phiên thật."""
        if "CUDAExecutionProvider" in providers:
            raise RuntimeError("libcudnn.so.9: cannot open shared object file")
        return real(data, sess_options=sess_options, providers=providers)

    monkeypatch.setattr(loader.ort, "InferenceSession", fake)
    with caplog.at_level(logging.INFO, logger=loader.__name__):
        session = loader._session(add_model().SerializeToString(), 1, CUDA_PROVIDERS)
    assert session.get_providers() == CPU_ONLY
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "rơi về CPU" in warnings[0].getMessage()


def test_cuda_providers_on_cpu_build_run_on_cpu(caplog: pytest.LogCaptureFixture) -> None:
    """ORT bản CPU nhận danh sách có CUDA vẫn dựng phiên CPU; log ghi provider thực dùng."""
    with caplog.at_level(logging.INFO, logger=loader.__name__):
        session = loader._session(add_model().SerializeToString(), 1, CUDA_PROVIDERS)
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        assert session.get_providers() == CPU_ONLY
    assert any("providers" in r.getMessage() and r.levelno == logging.INFO for r in caplog.records)


def test_cpu_session_skips_preload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phiên CPU không gọi `preload_dlls` (tiến trình CPU không nạp thư viện CUDA)."""
    calls: list[int] = []
    monkeypatch.setattr(loader.ort, "preload_dlls", lambda: calls.append(1), raising=False)
    session = loader._session(add_model().SerializeToString(), 1)
    assert session.get_providers() == CPU_ONLY
    assert calls == []


def test_preload_missing_or_failing_is_harmless(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """ORT không có `preload_dlls` → bỏ qua; hàm ném → chỉ cảnh báo."""
    monkeypatch.delattr(loader.ort, "preload_dlls", raising=False)
    loader._preload_cuda_dlls()

    def boom() -> None:
        """Giả `preload_dlls` thiếu thư viện."""
        raise OSError("libcublasLt.so.12 not found")

    monkeypatch.setattr(loader.ort, "preload_dlls", boom, raising=False)
    with caplog.at_level(logging.WARNING, logger=loader.__name__):
        loader._preload_cuda_dlls()
    assert any("preload_dlls" in r.getMessage() for r in caplog.records)


@pytest.mark.gpu
def test_real_gpu_session_uses_cuda() -> None:
    """Ảnh `ml` cuda trên máy có GPU: phiên ưu tiên `CUDAExecutionProvider`."""
    session = loader._session(add_model().SerializeToString(), 1, CUDA_PROVIDERS)
    assert session.get_providers()[0] == "CUDAExecutionProvider"
