"""Lõi phát hành `run_library_publish` (B2-06 [6], [8]): J01, J06, lô, tự lành, lỗi storage, K36."""

import logging
import zlib
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.library.assets import run_library_publish
from apps.api.library.tests._helpers import LIST_PATH, fail_put, headers_of, seed_and_publish, spy
from packages.core.error_codes import PAYLOAD_TOO_LARGE
from packages.core.errors import AppError
from packages.db.models.library import LibraryItemRow
from packages.domain.library import CATALOGUE, build_glb
from packages.storage.keys import library_object
from packages.storage.local import LocalDiskStorage
from packages.storage.s3 import S3Storage
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

COUNT = len(CATALOGUE)


async def _rows(db: AsyncSession) -> list[dict[str, Any]]:
    """Ảnh chụp mọi cột của mọi dòng (theo `id`), để so sánh trước/sau một lượt."""
    db.expire_all()
    rows = (await db.execute(select(LibraryItemRow).order_by(LibraryItemRow.id))).scalars().all()
    return [{col.name: getattr(row, col.name) for col in LibraryItemRow.__table__.columns} for row in rows]


async def test_publish_library_assets__J01(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """DB mới + seed + một lượt → #14 đủ 16 mục; `sha256` object khớp; `fileSizeBytes` = `stat.size`."""
    user = await make_user(db_session)
    report = await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock)
    assert (report.published, report.verified, report.skipped, report.failed) == (COUNT, 0, 0, 0)

    items = (await api_client.get(LIST_PATH, headers=headers_of(user))).json()
    assert len(items) == COUNT
    by_id = {item.id: item for item in CATALOGUE}
    for out in items:
        info = await local_storage.stat(library_object(out["id"], "model.glb"))
        assert info is not None
        assert info.sha256 == build_glb(by_id[out["id"]]).sha256
        assert out["fileSizeBytes"] == info.size
        assert info.kind == "glb"
        preview = await local_storage.stat(library_object(out["id"], "preview.png"))
        assert preview is not None
        assert preview.kind == "png"


async def test_run_library_publish_on_s3(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    s3_storage: S3Storage,
    fake_clock: FakeClock,
) -> None:
    """Cùng luồng với MinIO thật: 16 mục, `sha256` và kích thước object khớp dòng DB."""
    report = await seed_and_publish(db_session, db_sessionmaker, s3_storage, fake_clock)
    assert report.published == COUNT
    for row in await _rows(db_session):
        info = await s3_storage.stat(row["model_key"])
        assert info is not None
        assert (info.sha256, info.size, info.kind) == (row["model_sha256"], row["file_size_bytes"], "glb")


async def test_run_library_publish_batches(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`batch=10`: sau lượt đầu #14 có 10 mục, sau lượt hai đủ 16 (mục còn lại để lượt sau)."""
    user = await make_user(db_session)
    first = await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock, batch=10)
    assert first.published == 10
    assert len((await api_client.get(LIST_PATH, headers=headers_of(user))).json()) == 10
    second = await run_library_publish(db_sessionmaker, local_storage, fake_clock, batch=10)
    assert (second.published, second.skipped) == (COUNT - 10, 10)
    assert len((await api_client.get(LIST_PATH, headers=headers_of(user))).json()) == COUNT


async def test_publish_library_assets__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Giao lặp: lượt hai không `put`, không `stat`, dòng không đổi một cột nào."""
    await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock)
    before = await _rows(db_session)
    puts = spy(monkeypatch, local_storage, "put")
    stats = spy(monkeypatch, local_storage, "stat")

    report = await run_library_publish(db_sessionmaker, local_storage, fake_clock)

    assert (report.published, report.skipped) == (0, COUNT)
    assert puts == []
    assert stats == []
    assert await _rows(db_session) == before


async def test_library_publish_self_heals_deleted_object(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Object bị xoá ngoài luồng: qua `LIBRARY_VERIFY_AFTER_S` lượt kế `put` lại đúng object đó, giữ `published_at`."""
    await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock)
    before = {row["id"]: row for row in await _rows(db_session)}
    key = library_object("chair-stool", "model.glb")
    await local_storage.delete(key)
    puts = spy(monkeypatch, local_storage, "put")
    fake_clock.advance(timedelta(hours=2))

    report = await run_library_publish(db_sessionmaker, local_storage, fake_clock)

    assert (report.published, report.verified) == (1, COUNT - 1)
    assert puts == [key]
    assert await local_storage.stat(key) is not None
    after = {row["id"]: row for row in await _rows(db_session)}
    assert after["chair-stool"]["published_at"] == before["chair-stool"]["published_at"]
    assert after["chair-stool"]["verified_at"] == fake_clock.now()


async def test_library_publish_survives_storage_outage(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Storage ném `DEPENDENCY_UNAVAILABLE`: mục chưa phát hành, log từng mục; lượt sau phát hành."""
    with pytest.MonkeyPatch.context() as broken:
        fail_put(broken, local_storage)
        with caplog.at_level(logging.WARNING, logger="apps.api.library.assets"):
            report = await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock)
    assert (report.published, report.failed) == (0, COUNT)
    assert len([r for r in caplog.records if r.message == "library_publish_failed"]) == COUNT
    assert all(row["published_at"] is None for row in await _rows(db_session))

    retry = await run_library_publish(db_sessionmaker, local_storage, fake_clock)
    assert (retry.published, retry.failed) == (COUNT, 0)


async def test_library_publish_other_app_error_propagates(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chỉ `DEPENDENCY_UNAVAILABLE` bị nuốt: lỗi có mã khác (ở đây 413) đi tiếp lên người gọi."""

    async def too_large(*_args: Any, **_kwargs: Any) -> Any:
        """`put` vượt `max_bytes`."""
        raise PAYLOAD_TOO_LARGE.error()

    monkeypatch.setattr(local_storage, "put", too_large)
    with pytest.raises(AppError) as raised:
        await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock)
    assert raised.value.code is PAYLOAD_TOO_LARGE


async def test_library_publish_mismatch_not_published(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Object ghi ra lệch `sha256` khi `stat` lại → log `library_asset_mismatch`, mục không được phát hành (K22)."""
    real_put = local_storage.put

    async def corrupting(key: str, data: bytes, **kwargs: Any) -> Any:
        """`put` thật rồi làm hỏng byte đã lưu."""
        return await real_put(key, data[:-1] + bytes([data[-1] ^ 1]), **kwargs)

    monkeypatch.setattr(local_storage, "put", corrupting)
    with caplog.at_level(logging.ERROR, logger="apps.api.library.assets"):
        report = await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock)
    assert (report.published, report.failed) == (0, COUNT)
    assert len([r for r in caplog.records if r.message == "library_asset_mismatch"]) == COUNT
    assert all(row["published_at"] is None for row in await _rows(db_session))


async def test_library_publish_holds_no_db_connection_during_put(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """K36: trong lúc `put`, không kết nối nào của pool đang bị mượn."""
    pool = db_sessionmaker.kw["bind"].pool
    checked_out: list[int] = []
    real_put = local_storage.put

    async def watching(key: str, data: bytes, **kwargs: Any) -> Any:
        """Ghi số kết nối đang mượn rồi gọi `put` thật."""
        checked_out.append(pool.checkedout())
        return await real_put(key, data, **kwargs)

    monkeypatch.setattr(local_storage, "put", watching)
    await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock, batch=3)
    assert len(checked_out) == 6
    assert set(checked_out) == {0}


async def test_library_publish_ignores_rows_outside_catalogue(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Dòng không còn trong `catalogue` truyền vào không được dựng hay phát hành."""
    await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock, batch=0)
    report = await run_library_publish(db_sessionmaker, local_storage, fake_clock, catalogue=CATALOGUE[:3])
    assert report.published == 3
    published = [row["id"] for row in await _rows(db_session) if row["published_at"] is not None]
    assert sorted(published) == sorted(item.id for item in CATALOGUE[:3])


async def test_run_library_publish__other_zlib_build_skips(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NO-239: môi trường khác bản zlib (cùng ảnh, byte nén khác) không `put` lại và không đặt lại `published_at`."""
    await seed_and_publish(db_session, db_sessionmaker, local_storage, fake_clock)
    before = await _rows(db_session)
    real_compress = zlib.compress
    monkeypatch.setattr(zlib, "compress", lambda data: real_compress(data, 1))
    puts = spy(monkeypatch, local_storage, "put")

    report = await run_library_publish(db_sessionmaker, local_storage, fake_clock)

    assert (report.published, report.verified, report.skipped, report.failed) == (0, 0, COUNT, 0)
    assert puts == []
    assert await _rows(db_session) == before
