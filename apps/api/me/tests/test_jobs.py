"""Lịch dọn ảnh đại diện cũ/mồ côi (B1-04 [6] "Dọn rác"; J01, J06; ranh giới nhập)."""

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.me.jobs import TASK_NAME, purge_avatars, run_purge_avatars
from apps.api.me.tests.support import png_bytes
from packages.core.settings import reset_settings_cache
from packages.db.settings import reset_database_settings_cache
from packages.messaging.schedules import schedule_entries
from packages.storage.keys import avatar as avatar_key_of
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")


def _ulid(n: int) -> str:
    """26 ký tự Crockford hợp lệ, chỉ đổi chữ số cuối — đủ phân biệt các object mẫu của test."""
    return f"{n:026d}"


async def _seed_object(storage: LocalDiskStorage, user_id: str, n: int, ext: str = "png") -> str:
    key = avatar_key_of(user_id, _ulid(n), ext)
    await storage.put(key, png_bytes(), content_type="image/png", max_bytes=2 * 1024 * 1024)
    return key


async def test_purge_avatars__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Ảnh cũ và ảnh của người đã xoá bị xoá; ảnh hiện tại và khoá lạ ngoài mẫu còn nguyên."""
    current_user = await make_user(db_session)
    deleted_user = await make_user(db_session)
    deleted_user.deleted_at = fake_clock.now()
    await db_session.commit()

    current_key = await _seed_object(local_storage, current_user.id, 1)
    stale_key = await _seed_object(local_storage, current_user.id, 2)
    deleted_key = await _seed_object(local_storage, deleted_user.id, 3)
    foreign_key = "users/usr_00000000000000000000000000/nao-do/khac.txt"
    await local_storage.put(foreign_key, b"khong-phai-anh", content_type="text/plain", max_bytes=1024)

    current_user.avatar_key = current_key
    await db_session.commit()

    # `last_modified` là giờ thật của hệ thống tệp (gán lúc `put`, không theo `fake_clock`) —
    # đặt đồng hồ giả theo giờ thật + 2 ngày để cutoff (giờ thật + 1 ngày) vượt qua nó.
    fake_clock.set(datetime.now(UTC) + timedelta(days=2))

    removed = await run_purge_avatars(db_sessionmaker, local_storage, fake_clock)

    assert removed == 2
    assert await local_storage.stat(current_key) is not None
    assert await local_storage.stat(stale_key) is None
    assert await local_storage.stat(deleted_key) is None
    assert await local_storage.stat(foreign_key) is not None


async def test_purge_avatars__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Giao lặp: lượt thứ hai không xoá thêm gì (idempotent)."""
    user = await make_user(db_session)
    await _seed_object(local_storage, user.id, 4)
    fake_clock.set(datetime.now(UTC) + timedelta(days=2))

    assert await run_purge_avatars(db_sessionmaker, local_storage, fake_clock) == 1
    assert await run_purge_avatars(db_sessionmaker, local_storage, fake_clock) == 0


async def test_purge_avatars_runs_in_batches(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Lô nhỏ hơn số object phải xoá: vòng lặp lô (`_batches`) chạy tiếp cho tới hết."""
    user = await make_user(db_session)
    for n in range(5, 8):
        await _seed_object(local_storage, user.id, n)
    fake_clock.set(datetime.now(UTC) + timedelta(days=2))

    assert await run_purge_avatars(db_sessionmaker, local_storage, fake_clock, batch=1) == 3


def test_purge_avatars_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test khói: gọi hàm lịch thật (`SystemClock()`, `worker_sessionmaker()`, kho local); DB rỗng nên không xoá gì."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(REPO_ROOT / ".pytest-tmp-me-avatars"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-jobs-smoke-0000001")
    reset_settings_cache()
    reset_database_settings_cache()
    reset_storage_settings_cache()
    try:
        purge_avatars()
    finally:
        reset_database_settings_cache()
        reset_settings_cache()
        reset_storage_settings_cache()


def test_purge_avatars_schedule_is_registered() -> None:
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[TASK_NAME].function == "purge_avatars"


def test_jobs_import_without_web_or_crypto_packages() -> None:
    """Worker nhập `apps.api.me.jobs` để chạy task/beat: nhập được khi bốn gói web/crypto bị chặn."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", f"import sys; {blocked}; import apps.api.me.jobs"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
