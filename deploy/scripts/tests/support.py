"""Trợ giúp chung cho test script B0-10 (`deploy/scripts`, `deploy/backup`) — không phải test.

Hai công cụ, dùng lại ở mọi file test của B0-10 (R-07):
- `HttpStub`: máy chủ HTTP thử (`http.server`) — trả đáp án theo đường dẫn, ghi lại mọi
  thân POST (kiểm thân tin cảnh báo `{"text","content"}`, `smoke.sh`).
- `fake_bin` + `run_script`: lệnh giả đặt đầu `PATH`, mỗi lần gọi ghi một dòng
  `<tên> <đối số>` vào `$FAKE_LOG` — **chỉ** để kiểm thứ tự lệnh (B0-10 [8]), không thay
  dịch vụ thật trong kiểm chạy thật.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import TracebackType

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Reply:
    """Đáp án cố định cho một đường dẫn của `HttpStub`."""

    status: int = 200
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)
    delay_s: float = 0.0
    """Ngủ trước khi trả lời — dựng route "treo" để kiểm ngân sách `--max-time` (smoke.sh)."""


class HttpStub:
    """Máy chủ HTTP thử trên `127.0.0.1:<cổng ngẫu nhiên>`, chạy luồng nền.

    `routes` ánh xạ đường dẫn (không query) → `Reply`; đường lạ trả 404 thân rỗng.
    Mọi POST được ghi vào `posts` dạng `(đường dẫn, thân)` theo thứ tự nhận.
    Dùng làm context manager để máy chủ luôn tắt, kể cả khi test hỏng.
    """

    def __init__(self, routes: Mapping[str, Reply] | None = None, post_reply: Reply | None = None) -> None:
        """Nhận bảng đường dẫn cho GET và đáp án chung cho POST (mặc định 200)."""
        self.routes = dict(routes or {})
        self.post_reply = post_reply or Reply()
        self.posts: list[tuple[str, bytes]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        """Gốc URL không có `/` cuối, vd `http://127.0.0.1:43127`."""
        host, port = self._server.server_address[:2]
        return f"http://{host!s}:{port}"

    def __enter__(self) -> HttpStub:
        """Bật máy chủ."""
        self._thread.start()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        """Tắt máy chủ và giải phóng cổng."""
        self._server.shutdown()
        self._server.server_close()

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        """Lớp xử lý đóng gói `self` — `http.server` chỉ nhận lớp, không nhận thể hiện."""
        stub = self

        class Handler(BaseHTTPRequestHandler):
            """Trả `Reply` theo đường dẫn; ghi thân POST."""

            def _send(self, reply: Reply) -> None:
                """Ngủ `delay_s` (nếu có) rồi gửi mã, header và thân của `reply`."""
                if reply.delay_s:
                    time.sleep(reply.delay_s)
                self.send_response(reply.status)
                for name, value in reply.headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(reply.body)))
                self.end_headers()
                self.wfile.write(reply.body)

            def do_GET(self) -> None:
                """GET: tra bảng đường dẫn."""
                self._send(stub.routes.get(self.path.split("?")[0], Reply(404)))

            def do_POST(self) -> None:
                """POST: ghi thân rồi trả `post_reply`."""
                length = int(self.headers.get("Content-Length") or 0)
                stub.posts.append((self.path, self.rfile.read(length)))
                self._send(stub.post_reply)

            def log_message(self, format: str, *args: object) -> None:
                """Im lặng — log truy cập làm rối output pytest."""

        return Handler


def fake_bin(directory: Path, commands: Mapping[str, str]) -> Path:
    """Tạo lệnh giả trong `directory`; trả `directory` để đặt đầu `PATH`.

    `commands` ánh xạ tên lệnh → thân bash chạy **sau** dòng ghi log. Mỗi lần gọi ghi
    `<tên> <đối số…>` vào `$FAKE_LOG` (bắt buộc đặt biến này khi chạy). Thân rỗng = thoát 0.
    Thân có thể đọc `"$@"` để quyết định mã thoát/stdout, vd làm `migrate` hỏng.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in commands.items():
        path = directory / name
        path.write_text(
            '#!/usr/bin/env bash\nprintf \'%s\\n\' "$(basename "$0") $*" >> "$FAKE_LOG"\n' + body + "\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
    return directory


def run_script(
    script: Path,
    args: Sequence[str] = (),
    *,
    env: Mapping[str, str] | None = None,
    bin_dir: Path | None = None,
    stdin: str | None = None,
    timeout: float = 60,
) -> subprocess.CompletedProcess[str]:
    """Chạy `bash <script> <args>`, môi trường hiện tại + `env`, `bin_dir` đứng đầu `PATH`.

    Không ném khi mã thoát khác 0 — test tự kiểm `returncode`, stdout, stderr.
    `APPBACK_API_SWAP_SETTLE_S=0` mặc định (`env` ghi đè được): `lib.sh` `swap_api`
    ngủ thật theo biến này (mặc định sản xuất 11s, chờ nginx tự dịch lại DNS) — test
    dùng docker giả nên không cần chờ, giữ mặc định thật sẽ làm MỌI test đụng
    `swap_api` chậm thêm 11s không lý do (review round 1 R-05).
    """
    full_env = {**os.environ, "APPBACK_API_SWAP_SETTLE_S": "0", **(env or {})}
    if bin_dir is not None:
        full_env["PATH"] = f"{bin_dir}{os.pathsep}{full_env.get('PATH', '')}"
    return subprocess.run(  # noqa: S603 — script của repo, đối số do test đặt
        ["bash", str(script), *args],  # noqa: S607 — "bash" có sẵn trên PATH
        env=full_env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def read_log(log: Path) -> Iterator[str]:
    """Các dòng của `$FAKE_LOG` theo thứ tự gọi; chưa có lệnh nào → rỗng."""
    if log.exists():
        yield from log.read_text(encoding="utf-8").splitlines()
