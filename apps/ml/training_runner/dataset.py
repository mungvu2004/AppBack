"""Đọc kế hoạch dataset từ manifest và tải mẫu lên đĩa cục bộ (B6-03b [2], [6], [7]).

Mọi hàm `async`; runner (A) gọi qua `asyncio.Runner` riêng của lượt. Hai chốt chống
manifest/object hỏng: SHA-256 đọc được phải khớp `payload.manifest_sha256` trước khi
`parse_manifest` giải, và mỗi đường đích tải về phải nằm dưới `data_dir` dù
`parse_manifest` đã từ chối đường lạ ([7], chốt thứ hai).
"""

import asyncio
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from shutil import disk_usage as _disk_usage
from typing import Final, Protocol

from apps.ml.training_runner.errors import (
    DATASET_MANIFEST_MISMATCH,
    DATASET_OBJECT_MISMATCH,
    DATASET_SPLIT_EMPTY,
    TRAINING_DISK_FULL,
)
from apps.ml.training_runner.keys import sample_key
from packages.core.errors import AppError
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.datasets import ManifestEntry, parse_manifest
from packages.ml_contracts.payloads import TrainJobPayload
from packages.storage.keys import dataset_object
from packages.storage.port import ObjectStorage

_log: Final = logging.getLogger(__name__)

MANIFEST_NAME: Final = "manifest.jsonl"
MANIFEST_MAX_BYTES: Final = 64 * 1024 * 1024
DISK_HEADROOM_NUM: Final = 6
DISK_HEADROOM_DEN: Final = 5
"""`free x DISK_HEADROOM_DEN < total x DISK_HEADROOM_NUM` ⇔ `free < 1.2 x total` bằng số nguyên."""

__all__ = ["DatasetPlan", "DiskUsage", "check_disk", "download", "load_plan"]


class DiskUsage(Protocol):
    """Phần dùng tới của `shutil.disk_usage`'s namedtuple: chỉ `free`, chỉ đọc."""

    @property
    def free(self) -> int:
        """Byte còn trống."""
        ...


@dataclass(frozen=True, slots=True)
class DatasetPlan:
    """Mục `train` + `validation` của manifest (bỏ `test`), đã sắp theo `path`, và tổng byte."""

    entries: tuple[ManifestEntry, ...]
    total_bytes: int


async def _read_manifest(storage: ObjectStorage, key: str) -> bytes:
    """Đọc manifest theo khúc, chặn tại `MANIFEST_MAX_BYTES`; object vắng hay quá cỡ → mã manifest lệch."""
    chunks: list[bytes] = []
    total = 0
    try:
        async for chunk in storage.open_read(key):
            total += len(chunk)
            if total > MANIFEST_MAX_BYTES:
                raise PermanentError(DATASET_MANIFEST_MISMATCH)
            chunks.append(chunk)
    except AppError as exc:
        raise PermanentError(DATASET_MANIFEST_MISMATCH) from exc
    return b"".join(chunks)


async def load_plan(storage: ObjectStorage, payload: TrainJobPayload) -> DatasetPlan:
    """Đọc, băm và giải manifest của `payload.dataset_version_id`; giữ mục `train`/`validation`.

    SHA-256 lệch, manifest vắng, hay `parse_manifest` không giải được (kể cả vượt
    `DATASET_MAX_BYTES`) → `PermanentError(DATASET_MANIFEST_MISMATCH)`. Một trong hai tập
    giữ lại rỗng → `PermanentError(DATASET_SPLIT_EMPTY)`.
    """
    key = dataset_object(payload.dataset_version_id, MANIFEST_NAME)
    data = await _read_manifest(storage, key)
    if hashlib.sha256(data).hexdigest() != payload.manifest_sha256:
        raise PermanentError(DATASET_MANIFEST_MISMATCH)
    try:
        entries = parse_manifest(data)
    except ValueError as exc:
        raise PermanentError(DATASET_MANIFEST_MISMATCH) from exc
    kept = tuple(entry for entry in entries if entry.path.split("/", 1)[0] in ("train", "validation"))
    has_train = any(entry.path.startswith("train/") for entry in kept)
    has_validation = any(entry.path.startswith("validation/") for entry in kept)
    if not has_train or not has_validation:
        raise PermanentError(DATASET_SPLIT_EMPTY)
    return DatasetPlan(entries=kept, total_bytes=sum(entry.bytes for entry in kept))


def check_disk(directory: Path, total_bytes: int, *, disk_usage: Callable[[Path], DiskUsage] = _disk_usage) -> None:
    """Đĩa còn trống < 1.2 x `total_bytes` → `PermanentError(TRAINING_DISK_FULL)` (so bằng số nguyên)."""
    free = disk_usage(directory).free
    if free * DISK_HEADROOM_DEN < total_bytes * DISK_HEADROOM_NUM:
        raise PermanentError(TRAINING_DISK_FULL)


async def _download_one(storage: ObjectStorage, dataset_version_id: str, entry: ManifestEntry, dest: Path) -> None:
    """Tải một mục manifest về `dest`, băm + đếm byte khi ghi; lệch hay vắng → xoá tệp dở, mã object lệch.

    `Path.open`/`write`/`unlink` là lệnh chặn (ASYNC240): chạy qua `asyncio.to_thread`. Dùng
    `sample_key` (không `dataset_object`, chỉ nhận tên một đoạn — NO-263): `entry.path` ba đoạn.
    """
    key = sample_key(dataset_version_id, entry.path)
    hasher = hashlib.sha256()
    written = 0
    handle = await asyncio.to_thread(dest.open, "wb")
    try:
        async for chunk in storage.open_read(key):
            hasher.update(chunk)
            written += len(chunk)
            await asyncio.to_thread(handle.write, chunk)
    except AppError as exc:
        await asyncio.to_thread(handle.close)
        await asyncio.to_thread(dest.unlink, missing_ok=True)
        raise PermanentError(DATASET_OBJECT_MISMATCH) from exc
    else:
        await asyncio.to_thread(handle.close)
    if written != entry.bytes or hasher.hexdigest() != entry.sha256:
        await asyncio.to_thread(dest.unlink, missing_ok=True)
        raise PermanentError(DATASET_OBJECT_MISMATCH)


async def download(storage: ObjectStorage, payload: TrainJobPayload, plan: DatasetPlan, data_dir: Path) -> None:
    """Tải mọi mục của `plan` xuống `data_dir / entry.path`.

    Chốt thứ hai chống đường lạ ([7]): đường đích giải xong phải nằm dưới `data_dir` dù
    `parse_manifest` đã từ chối đường lạ ở tầng manifest.
    """
    root = await asyncio.to_thread(data_dir.resolve)
    for entry in plan.entries:
        dest = await asyncio.to_thread((data_dir / entry.path).resolve)
        if not dest.is_relative_to(root):
            raise PermanentError(DATASET_OBJECT_MISMATCH)
        await asyncio.to_thread(dest.parent.mkdir, parents=True, exist_ok=True)
        await _download_one(storage, payload.dataset_version_id, entry, dest)
