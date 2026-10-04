"""`SampleWriter` — ghi mẫu và manifest với kho thật (K23: không mock storage)."""

import hashlib
import json
from collections.abc import AsyncIterator

import pytest

from apps.worker.datasets.writer import SampleWriter
from packages.core.clock import Clock
from packages.core.ids import new_id
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.datasets import SampleMeta, parse_manifest
from packages.storage.keys import dataset_object
from packages.storage.local import LocalDiskStorage

pytestmark = pytest.mark.usefixtures("storage_env")

GROUP_KEY = "prj_00000000000000000000001"


def _meta(sample_id: str) -> SampleMeta:
    """Metadata mẫu hợp lệ cho `sample_id` cho trước."""
    return SampleMeta(
        sample_id=sample_id,
        group_key=GROUP_KEY,
        width_px=800,
        height_px=600,
        mm_per_px=10.0,
        source="approvedFloors",
    )


async def _chunks(*parts: bytes) -> AsyncIterator[bytes]:
    """Async iterable trả lần lượt từng phần byte."""
    for part in parts:
        yield part


async def _read_manifest(storage: LocalDiskStorage, version_id: str) -> bytes:
    """Đọc trọn `manifest.jsonl` của phiên bản từ kho."""
    key = dataset_object(version_id, "manifest.jsonl")
    body = b""
    async for chunk in storage.open_read(key):
        body += chunk
    return body


async def test_add_sample_and_finish__manifest_matches_objects(
    local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Manifest khớp từng object đã ghi (băm, kích thước) và khoá là `dataset_object` của đường mẫu."""
    version_id = new_id("dsv", fake_clock)
    writer = SampleWriter(local_storage, version_id)
    image = b"fake-image-bytes-0001"
    walls = b"fake-walls-bytes-0001"
    objects = json.dumps({"schemaVersion": 1, "detections": []}).encode()

    await writer.add_sample(
        split="train", sample_id="prj1_lvl1", image=image, walls=walls, objects=objects, meta=_meta("prj1_lvl1")
    )
    manifest_sha, split_counts = await writer.finish()

    assert split_counts == {"train": 1, "validation": 0, "test": 0}
    manifest_data = await _read_manifest(local_storage, version_id)
    assert manifest_sha == hashlib.sha256(manifest_data).hexdigest()

    entries = {entry.path: entry for entry in parse_manifest(manifest_data)}
    assert set(entries) == {
        "train/prj1_lvl1/image.png",
        "train/prj1_lvl1/walls.png",
        "train/prj1_lvl1/objects.json",
        "train/prj1_lvl1/meta.json",
    }
    for path in entries:  # NO-263: khoá mẫu là đúng `dataset_object` của đường mẫu
        assert await local_storage.stat(dataset_object(version_id, path)) is not None
    assert entries["train/prj1_lvl1/image.png"].sha256 == hashlib.sha256(image).hexdigest()
    assert entries["train/prj1_lvl1/image.png"].bytes == len(image)
    assert entries["train/prj1_lvl1/walls.png"].sha256 == hashlib.sha256(walls).hexdigest()
    assert entries["train/prj1_lvl1/objects.json"].bytes == len(objects)


async def test_add_sample__walls_and_objects_optional(local_storage: LocalDiskStorage, fake_clock: Clock) -> None:
    """Không có `walls`/`objects` thì chỉ ghi `image` và `meta`."""
    version_id = new_id("dsv", fake_clock)
    writer = SampleWriter(local_storage, version_id)
    await writer.add_sample(
        split="test", sample_id="prj2_lvl1", image=b"img", walls=None, objects=b"{}", meta=_meta("prj2_lvl1")
    )
    _, split_counts = await writer.finish()
    assert split_counts == {"train": 0, "validation": 0, "test": 1}
    manifest_data = await _read_manifest(local_storage, version_id)
    paths = {entry.path for entry in parse_manifest(manifest_data)}
    assert paths == {"test/prj2_lvl1/image.png", "test/prj2_lvl1/objects.json", "test/prj2_lvl1/meta.json"}


async def test_add_sample__async_iterable_image_not_buffered_whole(
    local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Ảnh là async iterable vẫn ghi đủ byte mà không gom hết vào RAM."""
    version_id = new_id("dsv", fake_clock)
    writer = SampleWriter(local_storage, version_id)
    parts = (b"chunk-one-", b"chunk-two-", b"chunk-three")
    await writer.add_sample(
        split="validation",
        sample_id="prj3_lvl1",
        image=_chunks(*parts),
        walls=None,
        objects=None,
        meta=_meta("prj3_lvl1"),
    )
    manifest_sha, split_counts = await writer.finish()
    assert split_counts["validation"] == 1
    manifest_data = await _read_manifest(local_storage, version_id)
    entries = {entry.path: entry for entry in parse_manifest(manifest_data)}
    assert entries["validation/prj3_lvl1/image.png"].sha256 == hashlib.sha256(b"".join(parts)).hexdigest()
    assert manifest_sha == hashlib.sha256(manifest_data).hexdigest()


async def test_add_sample__over_max_bytes_raises_dataset_too_large(
    local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Vượt `max_bytes` cộng dồn thì `PermanentError(DATASET_TOO_LARGE)`."""
    version_id = new_id("dsv", fake_clock)
    writer = SampleWriter(local_storage, version_id, max_bytes=10)
    with pytest.raises(PermanentError) as excinfo:
        await writer.add_sample(
            split="train",
            sample_id="prj4_lvl1",
            image=b"way more than ten bytes",
            walls=None,
            objects=None,
            meta=_meta("prj4_lvl1"),
        )
    assert excinfo.value.code == "DATASET_TOO_LARGE"


async def test_finish__zero_samples_does_not_raise(local_storage: LocalDiskStorage, fake_clock: Clock) -> None:
    """0 mẫu: `finish` không ném lỗi, đếm đủ ba split bằng 0."""
    version_id = new_id("dsv", fake_clock)
    writer = SampleWriter(local_storage, version_id)
    manifest_sha, split_counts = await writer.finish()
    assert split_counts == {"train": 0, "validation": 0, "test": 0}
    manifest_data = await _read_manifest(local_storage, version_id)
    assert manifest_data == b""
    assert manifest_sha == hashlib.sha256(b"").hexdigest()


async def test_add_sample__before_put_called_before_every_put(
    local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Điểm kiểm `before_put` được gọi trước mỗi `put`."""
    version_id = new_id("dsv", fake_clock)
    calls = 0

    async def before_put() -> None:
        """Đếm số lần được gọi."""
        nonlocal calls
        calls += 1

    writer = SampleWriter(local_storage, version_id, before_put=before_put)
    await writer.add_sample(
        split="train", sample_id="prj5_lvl1", image=b"img", walls=b"w", objects=b"{}", meta=_meta("prj5_lvl1")
    )
    assert calls == 4  # image, walls, objects, meta
    await writer.finish()
    assert calls == 5  # + manifest.jsonl


async def test_add_sample__before_put_stop_signal_propagates(
    local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Lỗi mất khoá ném từ `before_put` nổi lên nguyên vẹn."""
    version_id = new_id("dsv", fake_clock)

    class _LockLostError(Exception):
        """Tín hiệu mất khoá của test."""

    async def before_put() -> None:
        """Mô phỏng mất khoá giữa chừng."""
        raise _LockLostError

    writer = SampleWriter(local_storage, version_id, before_put=before_put)
    with pytest.raises(_LockLostError):
        await writer.add_sample(
            split="train", sample_id="prj6_lvl1", image=b"img", walls=None, objects=None, meta=_meta("prj6_lvl1")
        )
