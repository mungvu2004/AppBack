"""Factory dataset và phiên bản ML cho test (B6-02), theo mẫu `packages/testing/factories/admin_ml_registry.py`.

Ghi thẳng `datasets`/`dataset_versions`, không qua N29/`start_version`: test cần dựng nhiều
tổ hợp (`failed` có `failure_code`, `ready` có `manifestSha256`/`splitCounts`, `building`
trần) mà một lượt gọi API thật không dựng được trong một dòng. Mọi CHECK của bảng được tôn
trọng: `manifest_sha256`/`split_counts` chỉ có ở bản `ready`, `failure_code` chỉ ở bản
`failed`, `split_counts` luôn đủ ba khoá.

Có `commit` như `make_model_version`: route/worker đọc bằng session khác nên chỉ `flush`
thì không thấy. `created_at`/`updated_at` đặt tường minh để test phân trang xếp được thứ tự.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.errors import SYSTEM_PIPELINE
from packages.core.ids import new_id
from packages.core.text import nfc
from packages.db.models.admin_ml_datasets import DatasetRow, DatasetVersionRow

_DEFAULT_SPLIT_COUNTS: Mapping[str, int] = {"train": 8, "validation": 1, "test": 1}


async def make_dataset(
    db: AsyncSession,
    *,
    family: str,
    name: str | None = None,
    created_by: str | None = None,
    created_at: datetime | None = None,
) -> DatasetRow:
    """Một dòng `datasets` đã `commit`; `name` mặc định là một cái tên duy nhất (ULID)."""
    clock = SystemClock()
    at = created_at if created_at is not None else clock.now()
    dataset_id = new_id("dst", clock)
    clean_name = nfc(name) if name is not None else f"bo du lieu {dataset_id}"
    row = DatasetRow(
        id=dataset_id,
        name=clean_name,
        name_key=clean_name.casefold(),
        family=family,
        created_by=created_by if created_by is not None else SYSTEM_PIPELINE,
        created_at=at,
        updated_at=at,
    )
    db.add(row)
    await db.commit()
    return row


async def make_dataset_version(
    db: AsyncSession,
    *,
    dataset: DatasetRow,
    status: str = "ready",
    source: str = "approvedFloors",
    sequence: int | None = None,
    project_ids: Sequence[str] | None = None,
    manifest_sha256: str | None = None,
    split_counts: Mapping[str, int] | None = None,
    failure_code: str | None = None,
    created_by: str | None = None,
    created_at: datetime | None = None,
) -> DatasetVersionRow:
    """Một dòng `dataset_versions` đã `commit`, tôn trọng CHECK theo `status`.

    `sequence` mặc định 1 — gọi lặp trên cùng `dataset` cho `sequence` khác nhau tường minh
    (unique `(dataset_id, sequence)` chặn hai bản cùng số). `status="ready"` (mặc định) tự
    điền `manifest_sha256`/`split_counts` giả nếu không truyền; `status="failed"` tự điền
    `failure_code` giả; `status="building"` giữ cả hai `None`.
    """
    clock = SystemClock()
    at = created_at if created_at is not None else clock.now()
    version_id = new_id("dsv", clock)
    manifest = None
    counts = None
    code = None
    if status == "ready":
        manifest = manifest_sha256 if manifest_sha256 is not None else sha256(version_id.encode()).hexdigest()
        counts = dict(split_counts) if split_counts is not None else dict(_DEFAULT_SPLIT_COUNTS)
    elif status == "failed":
        code = failure_code if failure_code is not None else "DATASET_EMPTY"
    row = DatasetVersionRow(
        id=version_id,
        dataset_id=dataset.id,
        sequence=sequence if sequence is not None else 1,
        status=status,
        source=source,
        project_ids=list(project_ids) if project_ids is not None else None,
        manifest_sha256=manifest,
        split_counts=counts,
        failure_code=code,
        created_by=created_by if created_by is not None else SYSTEM_PIPELINE,
        created_at=at,
        updated_at=at,
    )
    db.add(row)
    await db.commit()
    return row
