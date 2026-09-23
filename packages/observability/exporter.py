"""Exporter `/metrics` cho Prometheus, cổng nội bộ (BE-00 §11).

`http.server` thay vì một dependency ngoài: `packages.observability` không được kéo
`fastapi`/`starlette` (BE-00 §13.1), nên exporter tự phục vụ trên luồng nền
(`ThreadingHTTPServer`), tách khỏi vòng sự kiện asyncio của app. `start_exporter` đếm
tham chiếu: nhiều lượt gọi (nhiều router gắn `metrics_lifespan`) chia sẻ **một** server
trong tiến trình, `stop()` chỉ đóng cổng khi lượt cuối cùng buông ra.
"""

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final

from packages.observability.metrics import render
from packages.observability.settings import get_observability_settings

_log: Final = logging.getLogger(__name__)

METRICS_PATH: Final = "/metrics"
CONTENT_TYPE: Final = "text/plain; version=0.0.4; charset=utf-8"
HANDLER_TIMEOUT_S: Final = 5


class _Handler(BaseHTTPRequestHandler):
    """Chỉ `GET /metrics` → 200; `GET` đường khác hay `POST /metrics` → 404. Không log từng request."""

    timeout = HANDLER_TIMEOUT_S

    def _dispatch(self) -> None:
        if self.command == "GET" and self.path == METRICS_PATH:
            self._serve_metrics()
        else:
            self.send_error(404)

    def _serve_metrics(self) -> None:
        body = render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def log_message(self, log_format: str, *args: object) -> None:
        """Ghi đè để không log từng request ra stderr (BE-00 §11)."""


class MetricsExporter:
    """Một `ThreadingHTTPServer` sống trên luồng daemon; `.port` là cổng thật đã gắn."""

    def __init__(self, host: str, port: int) -> None:
        self._server = ThreadingHTTPServer((host, port), _Handler)
        self.port: int = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Buông một tham chiếu; server chỉ đóng thật khi đếm về 0."""
        _release(self)


_lock: Final = threading.Lock()
_instance: MetricsExporter | None = None
_refcount = 0


def start_exporter(*, host: str, port: int) -> MetricsExporter:
    """Server đang chạy trong tiến trình, hay dựng mới; mỗi lượt gọi tăng đếm tham chiếu."""
    global _instance, _refcount
    with _lock:
        if _instance is None:
            _instance = MetricsExporter(host, port)
            _refcount = 0
        _refcount += 1
        return _instance


def _release(exporter: MetricsExporter) -> None:
    global _instance, _refcount
    with _lock:
        if _instance is not exporter:
            return
        _refcount -= 1
        if _refcount <= 0:
            exporter._server.shutdown()
            exporter._server.server_close()
            _instance = None
            _refcount = 0


@asynccontextmanager
async def metrics_lifespan(app: object) -> AsyncIterator[None]:
    """`METRICS_PORT > 0` → bật exporter trong lifespan của router; cổng bận không làm hỏng app."""
    settings = get_observability_settings()
    if settings.metrics_port <= 0:
        yield
        return
    exporter: MetricsExporter | None = None
    try:
        exporter = start_exporter(host=settings.metrics_host, port=settings.metrics_port)
    except OSError as exc:
        _log.warning("metrics_exporter_unavailable", extra={"error": repr(exc)})
    try:
        yield
    finally:
        if exporter is not None:
            exporter.stop()
