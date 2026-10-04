"""Test `load_plan`, `download`, `check_disk` trên kho đĩa thật (`local_storage`, B6-03b [3])."""

from collections import namedtuple
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from apps.ml.training_runner import dataset as dataset_module
from apps.ml.training_runner.dataset import DatasetPlan, check_disk, download, load_plan
from apps.ml.training_runner.errors import (
    DATASET_MANIFEST_MISMATCH,
    DATASET_OBJECT_MISMATCH,
    DATASET_SPLIT_EMPTY,
    TRAINING_DISK_FULL,
)
from apps.ml.training_runner.keys import sample_key
from apps.ml.training_runner.tests.support import (
    put_bytes,
    put_dataset,
    read_object,
    sha256_hex,
    train_payload,
)
from packages.core.clock import SystemClock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.core.ids import new_id
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.datasets import ManifestEntry
from packages.storage.keys import dataset_object
from packages.storage.local import LocalDiskStorage
from packages.storage.port import CHUNK_SIZE

_FakeUsage = namedtuple("_FakeUsage", ["free"])

pytestmark = pytest.mark.usefixtures("storage_env")


async def test_load_plan_keeps_train_and_validation(local_storage: LocalDiskStorage) -> None:
    """Manifest hợp lệ → mục `train`/`validation` giữ lại đúng số, `total_bytes` khớp tổng."""
    dataset = await put_dataset(local_storage, train=2, validation=1)
    payload = train_payload(dataset)
    plan = await load_plan(local_storage, payload)
    assert len(plan.entries) == len(dataset.entries)
    assert plan.total_bytes == dataset.total_bytes
    assert {entry.path.split("/", 1)[0] for entry in plan.entries} == {"train", "validation"}


async def test_load_plan_sha_mismatch(local_storage: LocalDiskStorage) -> None:
    """`manifest_sha256` của payload lệch manifest thật → `DATASET_MANIFEST_MISMATCH`."""
    dataset = await put_dataset(local_storage, train=1, validation=1)
    payload = train_payload(dataset).model_copy(update={"manifest_sha256": "0" * 64})
    with pytest.raises(PermanentError) as excinfo:
        await load_plan(local_storage, payload)
    assert excinfo.value.code == DATASET_MANIFEST_MISMATCH


async def test_load_plan_manifest_missing(local_storage: LocalDiskStorage) -> None:
    """Manifest vắng trên kho (chưa từng ghi) → `DATASET_MANIFEST_MISMATCH`."""
    missing_dsv = new_id("dsv", SystemClock())
    dataset = await put_dataset(local_storage, train=1, validation=1)
    payload = train_payload(dataset).model_copy(update={"dataset_version_id": missing_dsv})
    with pytest.raises(PermanentError) as excinfo:
        await load_plan(local_storage, payload)
    assert excinfo.value.code == DATASET_MANIFEST_MISMATCH


async def test_load_plan_manifest_garbage(local_storage: LocalDiskStorage) -> None:
    """Manifest là byte rác (sha khớp với chính rác, không khớp luật `parse_manifest`) → mã lệch."""
    dataset = await put_dataset(local_storage, train=1, validation=1)
    garbage = b"khong-phai-jsonl---"
    await put_bytes(local_storage, dataset_object(dataset.version_id, "manifest.jsonl"), garbage)
    payload = train_payload(dataset).model_copy(update={"manifest_sha256": sha256_hex(garbage)})
    with pytest.raises(PermanentError) as excinfo:
        await load_plan(local_storage, payload)
    assert excinfo.value.code == DATASET_MANIFEST_MISMATCH


async def test_load_plan_validation_empty(local_storage: LocalDiskStorage) -> None:
    """Tập `validation` rỗng → `DATASET_SPLIT_EMPTY`."""
    dataset = await put_dataset(local_storage, train=2, validation=0)
    payload = train_payload(dataset)
    with pytest.raises(PermanentError) as excinfo:
        await load_plan(local_storage, payload)
    assert excinfo.value.code == DATASET_SPLIT_EMPTY


async def test_download_writes_correct_bytes(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """`download` ghi đúng byte của mọi mục xuống `data_dir / entry.path`."""
    dataset = await put_dataset(local_storage, train=1, validation=1)
    payload = train_payload(dataset)
    plan = await load_plan(local_storage, payload)
    data_dir = tmp_path / "data"
    await download(local_storage, payload, plan, data_dir)
    for entry in plan.entries:
        written = (data_dir / entry.path).read_bytes()
        assert sha256_hex(written) == entry.sha256
        assert len(written) == entry.bytes


async def test_download_object_mismatch(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Tệp trên kho lệch một byte so manifest → `DATASET_OBJECT_MISMATCH`, không để tệp dở lại."""
    dataset = await put_dataset(local_storage, train=1, validation=1)
    payload = train_payload(dataset)
    plan = await load_plan(local_storage, payload)
    bad_entry = plan.entries[0]
    original = await read_object(local_storage, sample_key(dataset.version_id, bad_entry.path))
    corrupted = bytes([original[0] ^ 0xFF]) + original[1:]
    await put_bytes(local_storage, sample_key(dataset.version_id, bad_entry.path), corrupted)
    data_dir = tmp_path / "data"
    with pytest.raises(PermanentError) as excinfo:
        await download(local_storage, payload, plan, data_dir)
    assert excinfo.value.code == DATASET_OBJECT_MISMATCH
    assert not (data_dir / bad_entry.path).exists()


async def test_download_object_missing(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Tệp mẫu vắng trên kho (đã xoá) → `DATASET_OBJECT_MISMATCH`."""
    dataset = await put_dataset(local_storage, train=1, validation=1)
    payload = train_payload(dataset)
    plan = await load_plan(local_storage, payload)
    bad_entry = plan.entries[0]
    await local_storage.delete(sample_key(dataset.version_id, bad_entry.path))
    with pytest.raises(PermanentError) as excinfo:
        await download(local_storage, payload, plan, tmp_path / "data")
    assert excinfo.value.code == DATASET_OBJECT_MISMATCH


async def test_download_rejects_path_escaping_data_dir(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Chốt thứ hai ([7]): `entry.path` thoát khỏi `data_dir` → `DATASET_OBJECT_MISMATCH`.

    `parse_manifest` đã chặn đường lạ ở tầng manifest; test này dựng thẳng `DatasetPlan`
    để kiểm chốt độc lập thứ hai trong `download`.
    """
    dataset = await put_dataset(local_storage, train=1, validation=1)
    payload = train_payload(dataset)
    evil = ManifestEntry(path="../evil.png", sha256="0" * 64, bytes=0)
    plan = DatasetPlan(entries=(evil,), total_bytes=0)
    with pytest.raises(PermanentError) as excinfo:
        await download(local_storage, payload, plan, tmp_path / "data")
    assert excinfo.value.code == DATASET_OBJECT_MISMATCH


async def test_load_plan_manifest_over_cap(local_storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch) -> None:
    """Manifest vượt `MANIFEST_MAX_BYTES` → `DATASET_MANIFEST_MISMATCH`, không đọc hết object."""
    dataset = await put_dataset(local_storage, train=1, validation=1)
    monkeypatch.setattr(dataset_module, "MANIFEST_MAX_BYTES", 8)
    payload = train_payload(dataset)
    with pytest.raises(PermanentError) as excinfo:
        await load_plan(local_storage, payload)
    assert excinfo.value.code == DATASET_MANIFEST_MISMATCH


def test_check_disk_boundary_passes() -> None:
    """Đĩa còn đúng 1.2 x `total_bytes` → qua, không ném."""
    check_disk(Path("."), 1000, disk_usage=lambda _directory: _FakeUsage(free=1200))


def test_check_disk_boundary_fails() -> None:
    """Thiếu 1 byte so với 1.2 x `total_bytes` → `TRAINING_DISK_FULL`."""
    with pytest.raises(PermanentError) as excinfo:
        check_disk(Path("."), 1000, disk_usage=lambda _directory: _FakeUsage(free=1199))
    assert excinfo.value.code == TRAINING_DISK_FULL


class _BusyStorage(LocalDiskStorage):
    """Kho đĩa thật nhưng `open_read` báo kho bận (503) — sự cố tạm của phụ thuộc, không phải dữ liệu hỏng."""

    def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Luôn ném `DEPENDENCY_UNAVAILABLE` ở lượt đọc đầu tiên."""
        return _busy()


async def _busy() -> AsyncIterator[bytes]:
    """Generator rỗng ném 503 khi được duyệt (đủ để là async generator)."""
    raise AppError(DEPENDENCY_UNAVAILABLE, retry_after=1)
    yield b""


async def test_load_plan__storage_unavailable_stays_retryable(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """R-16: kho 503 khi đọc manifest lan nguyên `AppError` (thử lại được), không thành lỗi vĩnh viễn."""
    dataset = await put_dataset(local_storage, train=1, validation=1)
    busy = _BusyStorage(tmp_path / "objects", SystemClock(), None)
    with pytest.raises(AppError, match="DEPENDENCY_UNAVAILABLE"):
        await load_plan(busy, train_payload(dataset))


async def test_download__storage_unavailable_stays_retryable(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """R-16: kho 503 khi tải mẫu lan nguyên `AppError`, và tệp dở vẫn bị xoá."""
    dataset = await put_dataset(local_storage, train=1, validation=1)
    payload = train_payload(dataset)
    plan = await load_plan(local_storage, payload)
    busy = _BusyStorage(tmp_path / "objects", SystemClock(), None)
    with pytest.raises(AppError, match="DEPENDENCY_UNAVAILABLE"):
        await download(busy, payload, plan, tmp_path / "data")
    assert not (tmp_path / "data" / plan.entries[0].path).exists()
