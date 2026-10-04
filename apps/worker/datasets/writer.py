"""Ghi mẫu dataset vào storage và dựng manifest cuối lượt (K22, K36: không giữ session/mảng dataset trong RAM).

`SampleWriter` chỉ biết `ObjectStorage` và khoá `dataset_object`/`sample_path`; nó không quyết
định tầng nào đạt hay khi nào dừng lượt — `apps/worker/datasets/tasks.py` gọi `add_sample` mỗi
mẫu rồi `finish` cuối lượt. 0 mẫu **không** bị `finish()` ném lỗi: quyết định `DATASET_EMPTY`
thuộc về task (đã đọc trạng thái phiên bản, biết còn `building` hay không), không phải writer.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Awaitable, Callable

from apps.api.admin_ml_datasets.errors import DATASET_TOO_LARGE
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.datasets import (
    DATASET_MAX_BYTES,
    ManifestEntry,
    SampleMeta,
    Split,
    build_manifest,
    manifest_sha256,
    sample_path,
)
from packages.storage.keys import dataset_object
from packages.storage.port import ObjectStorage

_MANIFEST_NAME = "manifest.jsonl"

BeforePut = Callable[[], Awaitable[None]]


class SampleWriter:
    """Gom object của một lượt dựng phiên bản; cộng dồn byte thật, chặn khi vượt `max_bytes`."""

    def __init__(
        self,
        storage: ObjectStorage,
        version_id: str,
        *,
        max_bytes: int = DATASET_MAX_BYTES,
        before_put: BeforePut | None = None,
    ) -> None:
        """`before_put`: điểm kiểm khoá — task truyền `lock.check` để gọi trước **mỗi** `put`
        (kể cả `put` của `manifest.jsonl` trong `finish`), thay cho bọc `LockLost` quanh writer
        (lệch khỏi chữ ký prompt khối [2], không có ở đó)."""
        self._storage = storage
        self._version_id = version_id
        self._max_bytes = max_bytes
        self._before_put = before_put
        self._entries: list[ManifestEntry] = []
        self._total_bytes = 0
        self._split_counts: dict[str, int] = dict.fromkeys(("train", "validation", "test"), 0)

    async def add_sample(
        self,
        *,
        split: Split,
        sample_id: str,
        image: bytes | AsyncIterable[bytes],
        walls: bytes | None,
        objects: bytes | None,
        meta: SampleMeta,
    ) -> None:
        """Ghi `image.png`, `walls.png`?, `objects.json`?, `meta.json`; đếm mẫu vào `split`.

        Ảnh không được đọc hết vào RAM ở đây: `image` đi thẳng vào `ObjectStorage.put`, kể cả
        khi là `AsyncIterable[bytes]` (K22, K36).
        """
        files: list[tuple[str, bytes | AsyncIterable[bytes], str]] = [("image.png", image, "image/png")]
        if walls is not None:
            files.append(("walls.png", walls, "image/png"))
        if objects is not None:
            files.append(("objects.json", objects, "application/json"))
        files.append(("meta.json", meta.model_dump_json().encode(), "application/json"))
        for filename, data, content_type in files:
            await self._put(split, sample_id, filename, data, content_type)
        self._split_counts[split] += 1

    async def _put(
        self, split: Split, sample_id: str, filename: str, data: bytes | AsyncIterable[bytes], content_type: str
    ) -> None:
        """Một `put` qua `dataset_object` (NO-263); cộng `ObjectInfo.size` thật (không băm lại, prompt khối [2])."""
        if self._before_put is not None:
            await self._before_put()
        rel_path = sample_path(split, sample_id, filename)
        key = dataset_object(self._version_id, rel_path)
        # `max_bytes` của `put` là trần MỘT object (413 `PAYLOAD_TOO_LARGE`, mã lỗi khác hợp đồng
        # module này); trần dataset là việc của `self._max_bytes` cộng dồn ngay dưới đây, nên
        # truyền trần tuyệt đối của gói cho `put` để nó không tự chặn trước khi ta kịp cộng dồn.
        info = await self._storage.put(key, data, content_type=content_type, max_bytes=DATASET_MAX_BYTES)
        self._total_bytes += info.size
        if self._total_bytes > self._max_bytes:
            raise PermanentError(DATASET_TOO_LARGE)
        self._entries.append(ManifestEntry(path=rel_path, sha256=info.sha256, bytes=info.size))

    async def finish(self) -> tuple[str, dict[str, int]]:
        """`build_manifest` các `ManifestEntry` đã gom → `put` `manifest.jsonl` → `(manifest_sha256, split_counts)`.

        `split_counts` luôn đủ `train`/`validation`/`test` (0 khi rỗng); không ném `DATASET_EMPTY`
        (xem docstring module).
        """
        if self._before_put is not None:
            await self._before_put()
        data = build_manifest(self._entries)
        key = dataset_object(self._version_id, _MANIFEST_NAME)
        await self._storage.put(key, data, content_type="application/x-ndjson", max_bytes=DATASET_MAX_BYTES)
        return manifest_sha256(data), dict(self._split_counts)
