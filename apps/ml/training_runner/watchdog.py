"""Lý do dừng dùng chung và luồng canh của tiến trình con huấn luyện (BE-00 §7 "Luồng canh").

Trainer có thể lì: không bao giờ hỏi `cancelled()`, hay kẹt trong một epoch dài. Runner vì
thế soát lý do dừng trong một luồng riêng (`probe`) và nếu `train` không trả sau `grace_s`
thì gọi `on_expire(reason)` **đúng một lần** — dọn thư mục tạm, gửi `finished`, thoát.
Lý do đầu tiên thắng: huỷ rồi quá giờ vẫn báo `cancelled`, không đổi ngược lại.
"""

import logging
import threading
import time
from collections.abc import Callable
from typing import Final

_log: Final = logging.getLogger(__name__)

JOIN_TIMEOUT_S: Final = 5.0
"""Trần `join` của mọi luồng daemon trong module (`slot`, `reporter` nhập lại — một nguồn, R-07)."""


class StopState:
    """Lý do dừng của lượt, an toàn luồng: luồng canh ghi, luồng chính đọc khi `train` trả."""

    def __init__(self) -> None:
        """Chưa có lý do; `request` đầu tiên chốt giá trị, các lần sau bị bỏ qua."""
        self._lock = threading.Lock()
        self._reason: str | None = None

    def request(self, reason: str) -> None:
        """Ghi lý do dừng nếu chưa có lý do nào (lý do đầu thắng)."""
        with self._lock:
            if self._reason is None:
                self._reason = reason

    @property
    def reason(self) -> str | None:
        """Lý do dừng đã chốt, hay `None` khi lượt vẫn được chạy tiếp."""
        with self._lock:
            return self._reason


class Watchdog:
    """Luồng daemon soát `probe()` mỗi `poll_s`; có lý do quá `grace_s` mà `train` chưa trả → `on_expire`.

    Daemon để tiến trình tắt giữa chừng không bị luồng này chặn. `on_expire` chạy trong
    luồng canh (nó tự `exit`), nên chỉ được gọi khi `train_returned()` chưa tới.
    """

    def __init__(
        self,
        stop: StopState,
        *,
        grace_s: float,
        poll_s: float,
        probe: Callable[[], None],
        on_expire: Callable[[str], None],
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        """Luồng chưa chạy tới khi `start()`; `monotonic` tiêm được cho test đo grace."""
        self._stop = stop
        self._grace_s = grace_s
        self._poll_s = poll_s
        self._probe = probe
        self._on_expire = on_expire
        self._monotonic = monotonic or time.monotonic
        self._returned = threading.Event()
        self._stopping = threading.Event()
        self._expired = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="training-watchdog", daemon=True)

    @property
    def expired(self) -> bool:
        """Luồng canh đã nổ: luồng chính không được `put` hay gửi `finished` lần hai."""
        return self._expired.is_set()

    def start(self) -> None:
        """Bật luồng canh (gọi đúng một lần, ngay trước khi gọi `train`)."""
        self._thread.start()

    def train_returned(self) -> None:
        """`train` đã trả: thôi đếm grace, luồng canh không bao giờ nổ nữa."""
        self._returned.set()

    def stop(self) -> None:
        """Dừng luồng canh và `join` tối đa `JOIN_TIMEOUT_S` (gọi trong `finally`)."""
        self._stopping.set()
        if self._thread.is_alive():
            self._thread.join(JOIN_TIMEOUT_S)

    def _loop(self) -> None:
        """Mỗi `poll_s`: soát lý do dừng; có lý do thì đếm grace tới khi `train` trả."""
        since: float | None = None
        while not self._stopping.wait(self._poll_s):
            self._probe()
            reason = self._stop.reason
            if reason is None:
                continue
            if self._returned.is_set():
                return
            since = self._monotonic() if since is None else since
            if self._monotonic() - since > self._grace_s:
                self._fire(reason)
                return

    def _fire(self, reason: str) -> None:
        """Nổ đúng một lần: `train` không trả trong grace, lượt phải chết cùng tiến trình."""
        self._expired.set()
        _log.warning("training_watchdog_expired", extra={"reason": reason})
        self._on_expire(reason)
