"""Exporter `/metrics`: đếm tham chiếu, 404 ngoài route, cổng bận (B7-01 [6], [8])."""

import socket
from collections.abc import Iterator

import httpx
import pytest

from packages.observability import exporter as exporter_module
from packages.observability.exporter import CONTENT_TYPE, metrics_lifespan, start_exporter
from packages.observability.metrics import counter, reset_registry
from packages.observability.settings import get_observability_settings, reset_observability_settings_cache


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    reset_registry()
    yield
    reset_observability_settings_cache()
    assert exporter_module._instance is None, "test phải tự stop() mọi exporter đã start"


async def test_get_metrics_returns_rendered_text() -> None:
    hits = counter("appback_exporter_probe_total", help="đếm cho test exporter")
    hits.inc()
    exporter = start_exporter(host="127.0.0.1", port=0)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{exporter.port}/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == CONTENT_TYPE
        assert "appback_exporter_probe_total 1.0" in response.text
    finally:
        exporter.stop()


async def test_other_path_and_method_are_404() -> None:
    exporter = start_exporter(host="127.0.0.1", port=0)
    try:
        async with httpx.AsyncClient() as client:
            base = f"http://127.0.0.1:{exporter.port}"
            assert (await client.get(f"{base}/x")).status_code == 404
            assert (await client.post(f"{base}/metrics")).status_code == 404
    finally:
        exporter.stop()


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def test_every_other_method_on_metrics_is_404(method: str) -> None:
    """Prompt B7-01 [6]: 'đường khác, method khác → 404', không phải 501 mặc định của `http.server`."""
    exporter = start_exporter(host="127.0.0.1", port=0)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(method, f"http://127.0.0.1:{exporter.port}/metrics")
        assert response.status_code == 404
    finally:
        exporter.stop()


async def test_two_starts_share_one_server_and_stop_is_reference_counted() -> None:
    """Gọi hai lần → cùng server; `stop()` lần một vẫn trả lời, lần hai tắt."""
    first = start_exporter(host="127.0.0.1", port=0)
    second = start_exporter(host="127.0.0.1", port=first.port)
    assert first is second

    async def alive() -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{first.port}/metrics")
            return response.status_code == 200

    assert await alive()
    first.stop()
    assert await alive(), "vẫn còn một tham chiếu, server phải sống"
    second.stop()
    with pytest.raises(httpx.ConnectError):
        await alive()


async def test_busy_port_does_not_crash_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cổng đang bận (`OSError`) → `metrics_lifespan` không ném, chỉ log."""
    busy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    busy.bind(("127.0.0.1", 0))
    busy.listen(1)
    port = busy.getsockname()[1]
    monkeypatch.setenv("METRICS_HOST", "127.0.0.1")
    monkeypatch.setenv("METRICS_PORT", str(port))
    reset_observability_settings_cache()
    try:
        async with metrics_lifespan(object()):
            pass
    finally:
        busy.close()
        reset_observability_settings_cache()


async def test_lifespan_is_noop_when_metrics_port_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_PORT", "0")
    reset_observability_settings_cache()
    async with metrics_lifespan(object()):
        pass
    assert exporter_module._instance is None
    reset_observability_settings_cache()


def test_stop_on_a_stale_exporter_is_a_noop() -> None:
    """`stop()` gọi trên một `MetricsExporter` đã bị thay bởi lượt khác thì không làm gì."""
    exporter = start_exporter(host="127.0.0.1", port=0)
    exporter.stop()
    exporter.stop()  # lượt thứ hai: _instance đã None, không có gì để buông


def test_settings_read_env_once_per_process() -> None:
    assert isinstance(get_observability_settings().metrics_port, int)
