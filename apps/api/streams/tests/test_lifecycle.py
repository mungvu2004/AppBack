"""Hẹn giờ xoá stream upload và ranh giới nhập của module dùng chung với worker (B4-01 [2], [12])."""

import subprocess
import sys
from pathlib import Path
from typing import Final

from apps.api.streams.lifecycle import UPLOAD_STREAM_TTL_S, finalize_upload_stream, finalize_upload_stream_sync
from packages.messaging.redis import AsyncRedis, streams_redis_sync, sync_result
from packages.messaging.streams import EventBus, SyncEventBus, upload_stream

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")
WORKER_MODULES: Final = ("apps.api.streams.lifecycle", "apps.api.streams.jobs")

UPLOAD_ID: Final = "upl_01ARZ3NDEKTSV4RRFFQ69G5FAV"
EVENT: Final = {"uploadId": UPLOAD_ID, "step": "ingest"}


def _python(code: str) -> subprocess.CompletedProcess[str]:
    """Chạy một đoạn Python ở gốc repo, trả kết quả (không ném khi mã thoát khác 0)."""
    return subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


async def test_finalize_upload_stream_sets_the_ttl(event_bus: EventBus, streams_client: AsyncRedis) -> None:
    """Lượt tải vào trạng thái cuối → stream hết hạn sau 24 giờ (BE-00 §7)."""
    key = upload_stream(UPLOAD_ID)
    await event_bus.publish(key, EVENT)
    assert await streams_client.ttl(key) == -1
    await finalize_upload_stream(event_bus, UPLOAD_ID)
    assert 0 < await streams_client.ttl(key) <= UPLOAD_STREAM_TTL_S


def test_finalize_upload_stream_sync_sets_the_ttl(messaging_env: None) -> None:
    """Bản đồng bộ (callback sau commit) đặt cùng hạn; chạy ngoài vòng sự kiện."""
    client = streams_redis_sync()
    key = upload_stream(UPLOAD_ID)
    try:
        SyncEventBus(client).publish(key, EVENT)
        finalize_upload_stream_sync(SyncEventBus(client), UPLOAD_ID)
        assert 0 < sync_result(client.ttl(key), int) <= UPLOAD_STREAM_TTL_S
    finally:
        client.delete(key)  # không `flushdb`: DB streams dùng chung cả phiên (TEST-05)
        client.close()


def test_worker_modules_import_without_web_or_crypto_packages() -> None:
    """`lifecycle` và `jobs` nhập được khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn (BE-00 §2.1)."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    imports = "; ".join(f"import {name}" for name in WORKER_MODULES)
    result = _python(f"import sys; {blocked}; {imports}")
    assert result.returncode == 0, result.stderr
