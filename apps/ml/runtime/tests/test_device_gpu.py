"""Thiết bị và khoá GPU (M04): chọn CPU/CUDA, lấy khoá có TTL, gia hạn, tranh chấp, mất khoá.

Khoá chạy trên Redis **thật** (K23). TTL 600 ms, gia hạn mỗi 150 ms theo [8] B5-01: gấp 4
lần biên gia hạn, và test chờ "mất khoá" bằng vòng hỏi có hạn, không bằng một nhịp ngủ.
"""

import ast
import inspect
import logging
import threading
import time
from collections.abc import Callable, Iterator

import pytest
import torch

from apps.ml.runtime import gpu
from apps.ml.runtime.device import resolve_device
from apps.ml.runtime.errors import GPU_LOCK_LOST, ML_DEVICE_UNAVAILABLE
from apps.ml.runtime.gpu import GPU_LOCK_NAME, GpuSlot, gpu_slot
from packages.core.errors import AppError
from packages.messaging.redis import SyncRedis, safe_redis_sync, sync_result
from packages.messaging.tasks import PermanentError, TransientError
from packages.testing.fixtures.messaging import ephemeral_broker

KEY = f"lock:{GPU_LOCK_NAME}"
TTL_MS, RENEW_MS = 600, 150


@pytest.mark.parametrize(
    ("setting", "available", "expected"),
    [("cpu", True, "cpu"), ("auto", True, "cuda"), ("auto", False, "cpu"), ("cuda", True, "cuda")],
)
def test_resolve_device_m04(monkeypatch: pytest.MonkeyPatch, setting: str, available: bool, expected: str) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: available)
    assert resolve_device(setting) == expected  # type: ignore[arg-type]  # thiết lập chuỗi trong test


def test_resolve_device_m04_cuda_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(PermanentError) as caught:
        resolve_device("cuda")
    assert caught.value.code == ML_DEVICE_UNAVAILABLE


@pytest.fixture
def safe(messaging_env: None) -> Iterator[SyncRedis]:
    client = safe_redis_sync()
    client.delete(KEY)
    yield client
    client.delete(KEY)
    client.close()


def wait_for(predicate: Callable[[], bool], timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        assert time.monotonic() < deadline, "quá hạn chờ"
        time.sleep(0.02)


def test_gpu_slot_rejects_bad_timing() -> None:
    for ttl, renew in ((600, 300), (600, 0), (100, 60)):
        with pytest.raises(ValueError, match="renew_every_ms"), gpu_slot(wait_s=0, ttl_ms=ttl, renew_every_ms=renew):
            pass


def test_gpu_slot_m04_renew(safe: SyncRedis) -> None:
    """Giữ quá 2,5 TTL mà khoá vẫn của mình; thoát khối thì trả khoá."""
    with gpu_slot(wait_s=0, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as slot:
        time.sleep(TTL_MS * 2.5 / 1000)
        value = sync_result(safe.get(KEY), str)
        assert value.endswith(f":{slot.token}")
        assert sync_result(safe.pttl(KEY), int) > 0
        slot.check()
    assert safe.exists(KEY) == 0


def test_gpu_slot_m04_contention(safe: SyncRedis) -> None:
    """Người thứ hai chờ tới `wait_s` rồi `TransientError`; người trước trả thì người sau lấy được."""
    with gpu_slot(wait_s=0, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as first:
        started = time.monotonic()
        with (
            pytest.raises(TransientError, match="GPU đang bận"),
            gpu_slot(wait_s=1.0, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS),
        ):
            pass
        assert time.monotonic() - started >= 1.0
        first.check()

    release = threading.Event()

    def holder() -> None:
        with gpu_slot(wait_s=0, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS):
            release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    wait_for(lambda: safe.exists(KEY) == 1)
    threading.Timer(0.5, release.set).start()
    with gpu_slot(wait_s=10, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as second:
        second.check()
    thread.join(5)


def test_gpu_slot_m04_lost(safe: SyncRedis) -> None:
    """Khoá bị chủ khác chiếm: gia hạn bị từ chối → `lost`, `check()` ném; khoá của chủ mới không bị xoá."""
    with gpu_slot(wait_s=0, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as slot:
        safe.set(KEY, "khac:999999", px=10_000)
        wait_for(slot.lost.is_set)
        with pytest.raises(PermanentError) as caught:
            slot.check()
        assert caught.value.code == GPU_LOCK_LOST
    assert sync_result(safe.get(KEY), str) == "khac:999999"


def test_gpu_slot_m04_lost_when_redis_dies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis mất lâu hơn `ttl - renew`: khoá có thể đã về tay người khác → `lost`."""
    with ephemeral_broker(monkeypatch) as admin:
        with gpu_slot(wait_s=0, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as slot:
            admin.shutdown(nosave=True)
            wait_for(slot.lost.is_set, timeout_s=30.0)
            with pytest.raises(PermanentError):
                slot.check()
        with pytest.raises(AppError), gpu_slot(wait_s=0, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS):
            pass


def test_gpu_slot_release_survives_a_dead_redis(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Redis chết đúng lúc trả khoá: lỗi của thân nổi lên nguyên trạng, TTL dọn hộ.

    Đúng một `WARNING` của mã dự án, từ `SafeLock.release_quietly` — `gpu.py` không ghi bản thứ hai (NO-074).
    """
    slots: list[GpuSlot] = []

    def failing_body(admin: SyncRedis) -> None:
        with gpu_slot(wait_s=0, ttl_ms=60_000, renew_every_ms=20_000) as slot:
            slots.append(slot)
            admin.shutdown(nosave=True)
            raise ZeroDivisionError

    with ephemeral_broker(monkeypatch) as admin, caplog.at_level(logging.WARNING):
        with pytest.raises(ZeroDivisionError):
            failing_body(admin)
        assert not slots[0].lost.is_set()

    warnings = [
        (r.name, r.getMessage())
        for r in caplog.records
        if r.levelno >= logging.WARNING and r.name.startswith(("apps.", "packages."))
    ]
    assert warnings == [("packages.messaging.locks", "lock_release_failed")]


def test_gpu_release_has_no_catch_of_its_own() -> None:
    """`gpu.py` trả khoá chỉ qua `SafeLock.release_quietly`, không `try` nào bọc lời trả (R-07, NO-074)."""

    def releases(node: ast.AST) -> set[str]:
        funcs = (n.func for n in ast.walk(node) if isinstance(n, ast.Call))
        return {f.attr for f in funcs if isinstance(f, ast.Attribute) and f.attr.startswith("release")}

    tree = ast.parse(inspect.getsource(gpu))
    assert releases(tree) == {"release_quietly"}
    tries = [t for t in ast.walk(tree) if isinstance(t, ast.Try)]
    assert not [t.lineno for t in tries if any(releases(stmt) for stmt in t.body)]
