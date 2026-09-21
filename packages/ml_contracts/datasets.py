"""Bố cục một phiên bản dataset dưới `ml/datasets/{dsv}/` (B6-02 dựng, B6-04a/b đọc).

`manifest.jsonl` liệt kê **mọi** tệp mẫu với SHA-256 và số byte, sắp theo đường dẫn:
trainer so từng tệp trước khi đọc, và `TrainJobPayload.manifest_sha256` ghim chính
manifest. Chia `train/validation/test` theo **nhóm** (dự án, `cubicasa:<id>`), không
theo mẫu, để hai trang cùng một dự án không rơi vào hai tập (M06).
"""

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Annotated, Final, Literal, Self, cast

from pydantic import Field, ValidationError, model_validator

from packages.ml_contracts.artifacts import MASK_MAX_PIXELS, FrozenModel

Split = Literal["train", "validation", "test"]
SampleSource = Literal["approvedFloors", "cubicasa5k", "synthetic"]

SPLITS: Final[tuple[Split, ...]] = ("train", "validation", "test")
SAMPLE_FILES: Final = ("image.png", "walls.png", "objects.json", "meta.json")
MANIFEST_NAME: Final = "manifest.jsonl"
MANIFEST_MAX_LINES: Final = 200_000
DATASET_MAX_BYTES: Final = 8_589_934_592
_SAMPLE_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_SPLIT_BUCKETS: Final = 100


def sample_path(split: Split, sample_id: str, filename: str) -> str:
    """Đường tương đối `{split}/{sample_id}/{filename}` của một tệp mẫu; sai luật → `ValueError`."""
    if split not in SPLITS:
        raise ValueError(f"split lạ: {split!r}")
    if not _SAMPLE_ID_RE.fullmatch(sample_id):
        raise ValueError(f"sample_id sai mẫu: {sample_id!r}")
    if filename not in SAMPLE_FILES:
        raise ValueError(f"tên tệp mẫu lạ: {filename!r}")
    return f"{split}/{sample_id}/{filename}"


def _is_sample_path(path: str) -> bool:
    """Đường đúng dạng `sample_path` (dùng để từ chối đường lạ trong manifest)."""
    parts = path.split("/")
    if len(parts) != 3:
        return False
    try:
        return sample_path(cast("Split", parts[0]), parts[1], parts[2]) == path
    except ValueError:
        return False


class SampleMeta(FrozenModel):
    """`meta.json` của một mẫu. `mm_per_px = None` khi tầng nguồn chưa có tỉ lệ người đặt."""

    sample_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")]
    group_key: Annotated[str, Field(min_length=1, max_length=128)]
    width_px: Annotated[int, Field(ge=1)]
    height_px: Annotated[int, Field(ge=1)]
    mm_per_px: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None
    source: SampleSource

    @model_validator(mode="after")
    def _within_mask_cap(self) -> Self:
        """Khổ mẫu không quá trần mặt nạ: `walls.png` phải giải được bằng `decode_mask`."""
        if self.width_px * self.height_px > MASK_MAX_PIXELS:
            raise ValueError(f"khổ mẫu vượt {MASK_MAX_PIXELS} điểm")
        return self


class ManifestEntry(FrozenModel):
    """Một dòng manifest: đường mẫu, SHA-256, số byte."""

    path: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    bytes: Annotated[int, Field(ge=0)]


def build_manifest(entries: Iterable[ManifestEntry]) -> bytes:
    """Dòng JSON gọn, sắp theo `path`; qua lại `parse_manifest` được (kiểm cùng luật)."""
    ordered = sorted(entries, key=lambda entry: entry.path)
    data = b"".join(
        json.dumps(entry.model_dump(), separators=(",", ":"), sort_keys=True).encode() + b"\n" for entry in ordered
    )
    parse_manifest(data)
    return data


def parse_manifest(data: bytes) -> tuple[ManifestEntry, ...]:
    """Giải manifest; trùng, sai thứ tự, đường lạ, quá dòng hay tổng byte vượt trần → `ValueError`."""
    lines = data.split(b"\n")
    if lines[-1] != b"":
        raise ValueError("manifest phải kết thúc bằng xuống dòng")
    if len(lines) - 1 > MANIFEST_MAX_LINES:
        raise ValueError(f"manifest quá {MANIFEST_MAX_LINES} dòng")
    entries: list[ManifestEntry] = []
    total = 0
    for line in lines[:-1]:
        try:
            entry = ManifestEntry.model_validate_json(line)
        except ValidationError as exc:
            raise ValueError("dòng manifest sai schema") from exc
        if not _is_sample_path(entry.path):
            raise ValueError(f"đường lạ trong manifest: {entry.path!r}")
        if entries and entry.path <= entries[-1].path:
            raise ValueError(f"manifest trùng hay sai thứ tự ở {entry.path!r}")
        total += entry.bytes
        if total > DATASET_MAX_BYTES:
            raise ValueError(f"tổng byte vượt {DATASET_MAX_BYTES}")
        entries.append(entry)
    return tuple(entries)


def manifest_sha256(data: bytes) -> str:
    """SHA-256 của đúng các byte manifest đã lưu (giá trị ghim trong `TrainJobPayload`)."""
    return hashlib.sha256(data).hexdigest()


def split_for(key: str) -> Split:
    """Tập của một **nhóm**: băm SHA-256 tất định, 80/10/10 `train/validation/test` (M06)."""
    if not key:
        raise ValueError("khoá nhóm rỗng")
    bucket = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big") % _SPLIT_BUCKETS
    if bucket < 80:
        return "train"
    return "validation" if bucket < 90 else "test"
