"""Exporter `/metrics` cho Prometheus, cổng nội bộ (BE-00 §11).

`http.server` thay vì một dependency ngoài: `packages.observability` không được kéo
`fastapi`/`starlette` (BE-00 §13.1), nên exporter tự phục vụ trên luồng nền
(`ThreadingHTTPServer`), tách khỏi vòng sự kiện asyncio của app. `start_exporter` đếm
tham chiếu: nhiều lượt gọi (nhiều router gắn `metrics_lifespan`) chia sẻ **một** server
trong tiến trình, `stop()` chỉ đóng cổng khi lượt cuối cùng buông ra.
"""

import asyncio
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
POLL_INTERVAL_S: Final = 0.05
"""`serve_forever` mặc định poll 0,5 s: `shutdown()` chờ tới một vòng poll trước khi trả
về, nên mọi app test có `metrics_lifespan` (mọi module, không riêng telemetry) trả tới
0,5 s lúc tắt lifespan. 50 ms đủ nhỏ để không cộng dồn thấy được qua hàng trăm test,
vẫn đủ lớn để không bận CPU vô ích (PERF-04)."""


class _Handler(BaseHTTPRequestHandler):
    """Chỉ `GET /metrics` → 200; mọi đường/method khác → 404. Không log từng request."""

    timeout = HANDLER_TIMEOUT_S

    def _dispatch(self) -> None:
        """Một hàm cho mọi method: `GET /metrics` → 200, còn lại → 404 (không nhánh chết)."""
        if self.command == "GET" and self.path == METRICS_PATH:
            self._serve_metrics()
        else:
            self.send_error(404)

    def _serve_metrics(self) -> None:
        """200 `text/plain` với toàn bộ registry đã render."""
        body = render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # `http.server` gọi `do_<METHOD>`; thiếu `do_<METHOD>` là 501 mặc định của
    # `BaseHTTPRequestHandler`, nên method lạ cũng phải khai để `_dispatch()` (một thân
    # duy nhất, không nhánh chết) đưa nó về 404.
    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    def do_PATCH(self) -> None:
        self._dispatch()

    def do_HEAD(self) -> None:
        self._dispatch()

    def do_OPTIONS(self) -> None:
        self._dispatch()

    def log_message(self, log_format: str, *args: object) -> None:
        """Ghi đè để không log từng request ra stderr (BE-00 §11)."""


class MetricsExporter:
    """Một `ThreadingHTTPServer` sống trên luồng daemon; `.port` là cổng thật đã gắn."""

    def __init__(self, host: str, port: int) -> None:
        self._server = ThreadingHTTPServer((host, port), _Handler)
        self.port: int = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": POLL_INTERVAL_S}, daemon=True
        )
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
        # `stop()` có thể chờ tới `POLL_INTERVAL_S` (ThreadingHTTPServer.shutdown() chặn
        # tới vòng poll kế tiếp) — đẩy sang luồng khác để không chặn vòng sự kiện lúc
        # lifespan đóng (PERF-04).
        if exporter is not None:
            await asyncio.to_thread(exporter.stop)
