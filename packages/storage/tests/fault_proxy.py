"""Proxy HTTP tiêm lỗi đứng trước MinIO **thật** (K23: không mock MinIO).

MinIO không trả 5xx hay lỗi từng object theo yêu cầu, nên test đặt proxy này giữa client
`minio` và container thật: request nào khớp một lỗi đã hẹn thì nhận đúng phản hồi đó, mọi
request khác chuyển nguyên văn (kể cả `Host`, để chữ ký SigV4 vẫn khớp) tới MinIO. Proxy
cũng ghi lại (method, đường) của mọi request để test đếm lượt đi-về.
"""

import http.client
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final
from urllib.parse import parse_qs, urlsplit

UPSTREAM_TIMEOUT_S: Final = 15.0
_HOP_HEADERS: Final = frozenset(("connection", "content-length", "transfer-encoding", "keep-alive"))


@dataclass(frozen=True)
class Fault:
    """Phản hồi tiêm cho request đầu tiên cùng `method` và có khoá query `query` (nếu đặt)."""

    method: str
    status: int
    body: bytes
    query: str | None = None


def s3_error_xml(code: str) -> bytes:
    """Thân lỗi S3 dạng XML như MinIO/AWS trả (`S3Error.fromxml` đọc được)."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Error><Code>{code}</Code><Message>lỗi tiêm</Message><Resource>/</Resource>"
        "<RequestId>fault</RequestId><HostId>fault</HostId></Error>"
    ).encode()


def delete_error_xml(key: str, code: str) -> bytes:
    """`DeleteResult` 200 của `DeleteObjects` báo lỗi riêng một object."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<DeleteResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<Error><Key>{key}</Key><Code>{code}</Code><Message>lỗi tiêm</Message></Error></DeleteResult>"
    ).encode()


class FaultProxy(ThreadingHTTPServer):
    """Máy chủ proxy chạy trên luồng nền; `endpoint` là `host:port` cho client `minio`."""

    daemon_threads = True

    def __init__(self, upstream: str) -> None:
        super().__init__(("127.0.0.1", 0), _Relay)
        self.upstream = upstream
        self.faults: list[Fault] = []
        self.requests: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    @property
    def endpoint(self) -> str:
        """`host:port` mà client `minio` trỏ tới."""
        return f"127.0.0.1:{self.server_address[1]}"

    def take(self, method: str, path: str) -> Fault | None:
        """Ghi request, rồi lấy (và bỏ) lỗi đã hẹn đầu tiên khớp nó."""
        query = parse_qs(urlsplit(path).query, keep_blank_values=True)
        with self._lock:
            self.requests.append((method, path))
            for fault in self.faults:
                if fault.method == method and (fault.query is None or fault.query in query):
                    self.faults.remove(fault)
                    return fault
        return None


class _Relay(BaseHTTPRequestHandler):
    """Một request: trả lỗi đã hẹn, hoặc chuyển nguyên văn tới MinIO."""

    protocol_version = "HTTP/1.1"
    server: FaultProxy

    def _relay(self) -> None:
        """Đọc thân, chọn phản hồi, gửi lại cho client."""
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        fault = self.server.take(self.command, self.path)
        if fault is not None:
            status, headers, payload = fault.status, [("Content-Type", "application/xml")], fault.body
        else:
            status, headers, payload = self._forward(body)
        self.send_response(status)
        for name, value in headers:
            if name.lower() not in _HOP_HEADERS:
                self.send_header(name, value)
        # HEAD giữ `Content-Length` của MinIO: `stat_object` đọc kích thước từ đó.
        upstream_length = next((value for name, value in headers if name.lower() == "content-length"), "0")
        self.send_header("Content-Length", upstream_length if self.command == "HEAD" else str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _forward(self, body: bytes | None) -> tuple[int, list[tuple[str, str]], bytes]:
        """Gửi request (giữ mọi header) tới MinIO và đọc trọn phản hồi."""
        host, port = self.server.upstream.rsplit(":", 1)
        connection = http.client.HTTPConnection(host, int(port), timeout=UPSTREAM_TIMEOUT_S)
        try:
            connection.putrequest(self.command, self.path, skip_host=True, skip_accept_encoding=True)
            for name, value in self.headers.items():
                connection.putheader(name, value)
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, response.getheaders(), response.read()
        finally:
            connection.close()

    def log_message(self, format: str, *args: object) -> None:
        """Im lặng: log truy cập của proxy không giúp gì cho test."""


@contextmanager
def fault_proxy(upstream: str) -> Iterator[FaultProxy]:
    """Proxy chạy suốt khối `with`, tắt và đóng cổng khi ra."""
    proxy = FaultProxy(upstream)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    try:
        yield proxy
    finally:
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=UPSTREAM_TIMEOUT_S)


# `BaseHTTPRequestHandler` gọi `do_<METHOD>`; gắn bằng `setattr` để tên hoa không vướng N802/N815.
for _method in ("GET", "HEAD", "PUT", "POST", "DELETE"):
    setattr(_Relay, f"do_{_method}", _Relay._relay)
