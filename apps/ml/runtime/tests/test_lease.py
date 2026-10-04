"""Lõi `held_lease` (NO-308): hai tiến trình tranh một khoá trên Redis thật; lớp vỏ `SafeLockOps`; luồng gia hạn chết.

Đường Redis thật đi qua `gpu_slot` (lớp vỏ `SafeLock`); mất khoá khi Redis hỏng quá hạn đã có ở
`test_device_gpu.py`/`training_runner/tests/test_slot.py`. Nhánh luồng gia hạn chết vì lỗi lạ
không cần Redis.
"""

import subprocess
import sys
import textwrap
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from apps.ml.runtime import gpu
from apps.ml.runtime.gpu import GPU_LOCK_NAME, SafeLockOps, gpu_slot
from apps.ml.runtime.lease import RenewThread
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, INTERNAL
from packages.core.errors import AppError, ErrorCode
from packages.messaging.locks import SafeLock
from packages.messaging.redis import AsyncRedis, SyncRedis, safe_redis_sync
from packages.messaging.tasks import TransientError

REPO_ROOT = Path(__file__).resolve().parents[4]
KEY = f"lock:{GPU_LOCK_NAME}"
TTL_MS = 600
RENEW_MS = 200

_HOLDER = textwrap.dedent(
    """
    import sys
    from apps.ml.runtime.gpu import gpu_slot
    with gpu_slot(wait_s=0, ttl_ms={ttl}, renew_every_ms={renew}) as slot:
        print("held", flush=True)
        sys.stdin.readline()
        slot.check()
    print("released", flush=True)
    """
)
"""Tiến trình thứ hai giữ khoá tới khi đọc được một dòng stdin (qua nhiều nhịp gia hạn); ngoặc nhọn là chỗ `format`."""


@pytest.fixture
def safe(messaging_env: None) -> Iterator[SyncRedis]:
    """Client Redis `safe` thật, khoá GPU đã xoá trước và sau test."""
    client = safe_redis_sync()
    client.delete(KEY)
    yield client
    client.delete(KEY)
    client.close()


def test_held_lease__second_process_waits_for_first(safe: SyncRedis) -> None:
    """Tiến trình khác giữ khoá qua nhiều TTL: lượt chờ 1 s → `TransientError`; nó trả thì lượt chờ lấy được."""
    holder = subprocess.Popen(  # noqa: S603 — trình thông dịch của chính venv, mã cố định
        [sys.executable, "-c", _HOLDER.format(ttl=TTL_MS, renew=RENEW_MS)],
        cwd=REPO_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdin is not None
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"
        with (
            pytest.raises(TransientError, match="đang bận"),
            gpu_slot(wait_s=1, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS),
        ):
            pass
        holder.stdin.write("tha\n")
        holder.stdin.flush()
        with gpu_slot(wait_s=15, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as slot:
            slot.check()
            assert str(safe.get(KEY)).endswith(f":{slot.token}")
        assert holder.wait(15) == 0
        assert holder.stdout.read().strip() == "released"
    finally:
        holder.kill()
        holder.wait(15)


def test_renew_thread__crash_marks_lost() -> None:
    """`step()` ném lỗi lạ khi chưa được báo dừng → luồng chết nhưng bật `lost` (fail-closed)."""
    lost = threading.Event()

    def step() -> bool | None:
        """Lỗi lập trình giả lập trong nhịp gia hạn."""
        raise RuntimeError("hỏng")

    thread = RenewThread(interval_s=0.01, step=step, lost=lost)
    thread.start()
    assert lost.wait(5)
    thread.stop()
    assert not thread.is_alive()


def test_safe_lock_ops__renew_maps_only_dependency_errors(monkeypatch: pytest.MonkeyPatch, safe: SyncRedis) -> None:
    """Redis không phục vụ được → `None` (lõi tính hạn); `AppError` khác nổi lên nguyên dạng."""
    raised: list[ErrorCode] = [DEPENDENCY_UNAVAILABLE, INTERNAL]

    async def failing(_lock: SafeLock, _token: int) -> bool:
        """Gia hạn ném `AppError` theo mã kế tiếp của `raised`."""
        code = raised.pop(0)
        raise AppError(code, retry_after=1) if code.status == 503 else AppError(code)

    ops = SafeLockOps(GPU_LOCK_NAME, TTL_MS)
    try:
        token = ops.try_acquire()
        assert token is not None
        with monkeypatch.context() as patch:
            patch.setattr(SafeLock, "renew", failing)
            assert ops.renew(token) is None
            with pytest.raises(AppError) as caught:
                ops.renew(token)
            assert caught.value.code is INTERNAL
        assert ops.renew(token) is True
        ops.release_quietly(token)
        assert safe.exists(KEY) == 0
    finally:
        ops.close()


def test_safe_lock_ops__client_failure_stops_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dựng client lỗi → vòng sự kiện và luồng của nó đã dừng khi lỗi nổi lên."""

    async def broken() -> AsyncRedis:
        """Dựng client thất bại."""
        raise OSError("không dựng được client")

    monkeypatch.setattr(gpu, "_client", broken)
    with pytest.raises(OSError, match="không dựng được"):
        SafeLockOps(GPU_LOCK_NAME, TTL_MS)
    assert "gpu-slot-loop" not in {t.name for t in threading.enumerate()}
