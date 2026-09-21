"""Riêng `LocalDiskStorage`: token tệp và lỗi đĩa (C13)."""

import errno
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO, cast

import pytest

from packages.core.errors import AppError
from packages.core.settings import reset_settings_cache
from packages.storage import keys
from packages.storage.local import FILES_ROUTE, LocalDiskStorage
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.storage import PUBLIC_BASE_URL, STORAGE_SECRET

PROJECT = "prj_01ARZ3NDEKTSV4RRFFQ69G5FAV"
FLOOR = "L-ABCDEFGHIJ"
UPLOAD = "upl_01ARZ3NDEKTSV4RRFFQ69G5FBW"
KEY = keys.upload_page(PROJECT, FLOOR, UPLOAD, 0)
PNG = b"\x89PNG\r\n\x1a\n" + b"pixels" * 8
MAX_BYTES = 1024 * 1024
NEW_SECRET = "secret-sau-khi-xoay-khoa-cua-b0-04"  # noqa: S105 — khoá giả của test, không phải bí mật thật


class _FailingFile:
    """File thật nhưng `write` ném `OSError` — điểm tiêm lỗi đĩa cho C13."""

    def __init__(self, path: Path, code: int) -> None:
        self._handle = path.open("wb")
        self._code = code

    def write(self, data: bytes) -> int:
        raise OSError(self._code, "tiêm lỗi ghi")

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "_FailingFile":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def failing_open(code: int) -> Callable[[Path], BinaryIO]:
    def _open(path: Path) -> BinaryIO:
        return cast("BinaryIO", _FailingFile(path, code))

    return _open


def token_of(url: str) -> str:
    return url.rsplit("/", 1)[-1]


async def sign(storage: LocalDiskStorage, filename: str | None = None) -> str:
    """Ghi một object rồi trả token của URL ký — dùng lại ở mọi test token."""
    await storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)
    signed = await storage.signed_url(KEY, disposition="attachment", filename=filename)
    return token_of(signed.url)


async def test_signed_url_goes_through_the_files_route(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """K15: URL không bao giờ trỏ thẳng đường dẫn tệp."""
    await local_storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    signed = await local_storage.signed_url(KEY, disposition="attachment", filename="bản vẽ.png")

    assert signed.url.startswith(f"{PUBLIC_BASE_URL}{FILES_ROUTE}")
    assert str(tmp_path) not in signed.url
    assert KEY not in signed.url


async def test_verify_token_returns_the_grant(local_storage: LocalDiskStorage) -> None:
    token = await sign(local_storage, "bản vẽ tầng 1.png")

    grant = local_storage.verify_token(token)

    assert grant.key == KEY
    assert grant.disposition == "attachment"
    assert grant.filename == "ban ve tang 1.png"


async def test_verify_token_without_filename(local_storage: LocalDiskStorage) -> None:
    grant = local_storage.verify_token(await sign(local_storage))

    assert grant.filename is None


@pytest.mark.parametrize("part", [0, 1])
async def test_verify_token_rejects_tampered_token(local_storage: LocalDiskStorage, part: int) -> None:
    pieces = (await sign(local_storage)).split(".")
    pieces[part] = f"{pieces[part][:-1]}{'A' if pieces[part][-1] != 'A' else 'B'}"

    with pytest.raises(AppError, match="NOT_FOUND"):
        local_storage.verify_token(".".join(pieces))


@pytest.mark.parametrize("bad", ["", "khong-co-cham", "a.b.c", "!!!.!!!", "e30.YWJj"])
async def test_verify_token_rejects_garbage(local_storage: LocalDiskStorage, bad: str) -> None:
    with pytest.raises(AppError, match="NOT_FOUND"):
        local_storage.verify_token(bad)


async def test_verify_token_rejects_expired(local_storage: LocalDiskStorage, fake_clock: FakeClock) -> None:
    token = await sign(local_storage)

    fake_clock.advance(timedelta(hours=3))

    with pytest.raises(AppError, match="NOT_FOUND"):
        local_storage.verify_token(token)


async def test_verify_token_accepts_token_signed_with_previous_secret(
    local_storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await sign(local_storage)

    monkeypatch.setenv("SECRET_KEY", NEW_SECRET)
    monkeypatch.setenv("SECRET_KEY_PREVIOUS", STORAGE_SECRET)
    reset_settings_cache()

    assert local_storage.verify_token(token).key == KEY


async def test_verify_token_rejects_token_of_a_retired_secret(
    local_storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await sign(local_storage)

    monkeypatch.setenv("SECRET_KEY", NEW_SECRET)
    monkeypatch.delenv("SECRET_KEY_PREVIOUS", raising=False)
    reset_settings_cache()

    with pytest.raises(AppError, match="NOT_FOUND"):
        local_storage.verify_token(token)


async def test_put_on_full_disk_returns_503_and_leaves_no_temp_file(
    tmp_path: Path, fake_clock: FakeClock, storage_env: None
) -> None:
    root = tmp_path / "objects"
    storage = LocalDiskStorage(root, fake_clock, PUBLIC_BASE_URL, _open=failing_open(errno.ENOSPC))

    with pytest.raises(AppError, match="DEPENDENCY_UNAVAILABLE") as raised:
        await storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    assert raised.value.code.status == 503
    assert raised.value.retry_after == 5
    assert [path for path in root.rglob("*") if path.is_file()] == []


async def test_put_does_not_swallow_other_os_errors(tmp_path: Path, fake_clock: FakeClock, storage_env: None) -> None:
    storage = LocalDiskStorage(tmp_path, fake_clock, PUBLIC_BASE_URL, _open=failing_open(errno.EACCES))

    with pytest.raises(OSError, match="tiêm lỗi ghi"):
        await storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)


async def test_list_prefix_skips_metadata_files(local_storage: LocalDiskStorage) -> None:
    await local_storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    found = [info.key async for info in local_storage.list_prefix(keys.project_prefix(PROJECT))]

    assert found == [KEY]
    assert (local_storage._path(KEY).parent / f"{Path(KEY).name}.meta.json").exists()


async def test_stat_uses_filesystem_time(local_storage: LocalDiskStorage) -> None:
    await local_storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    stored = await local_storage.stat(KEY)

    assert stored is not None
    assert abs((stored.last_modified - datetime.now(UTC)).total_seconds()) < 60


async def test_delete_prefix_raises_instead_of_reporting_success(local_storage: LocalDiskStorage) -> None:
    """NO-012: xoá hỏng (tiền tố là một **tệp**, `rmtree` gặp `ENOTDIR`) nổi lên, không báo thành công giả."""
    prefix = keys.project_prefix(PROJECT)
    blocker = local_storage._path(prefix.rstrip("/"))
    blocker.parent.mkdir(parents=True)
    blocker.write_bytes(b"khong-phai-thu-muc")

    with pytest.raises(NotADirectoryError):
        await local_storage.delete_prefix(prefix)

    assert blocker.exists()


async def test_delete_prefix_of_a_missing_prefix_is_silent(local_storage: LocalDiskStorage) -> None:
    """Tiền tố chưa từng có object: dọn rác không có gì để xoá, không lỗi."""
    await local_storage.delete_prefix(keys.project_prefix(PROJECT))
