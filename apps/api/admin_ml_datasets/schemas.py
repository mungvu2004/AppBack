"""Model dây của N28-N31 (B6-02 [2]) — gương `src/api/schemas/adminMl.ts`, HOP-DONG-MOI §8.

Ba luật của FE mà lớp này giữ thay cho `service.py`:

- **K01**: dây không bao giờ mang `projectIds`, `requeueCount`, `createdBy`,
  `buildStartedAt` — bốn cột ấy là chuyện nội bộ của lượt dựng;
- **K02/W2**: `manifestSha256`/`splitCounts` chỉ khi `ready`, `failureCode` chỉ khi
  `failed`; `WireModel` bỏ trường `None` nên chúng tự rơi ra ở hai trạng thái khác;
- `name` NFC(strip), 1-`NAME_MAX`, cấm `Cc` và ký tự đảo chiều — cùng cổng
  `clean_text` của `apps.api.projects.schemas` (không chép lại luật bidi, R-07).
"""

from typing import Annotated, cast

from pydantic import BeforeValidator, Field, StringConstraints

from apps.api.core.pagination import CursorPage
from apps.api.core.wire import WireDatetime, WireModel, WireRequest
from apps.api.projects.schemas import clean_text
from packages.db.models.admin_ml_datasets import NAME_MAX, DatasetRow, DatasetVersionRow
from packages.ml_contracts.families import ModelFamily

CleanName = Annotated[str, BeforeValidator(clean_text), StringConstraints(min_length=1, max_length=NAME_MAX)]
"""`name` người nhập (N29): trim + NFC + cấm Cc/bidi (`clean_text`), rồi 1-80 ký tự."""


class DatasetOut(WireModel):
    """`DatasetSchema`: một dataset đặt tên, không cột nội bộ (`createdBy`)."""

    created_at: WireDatetime
    family: ModelFamily
    id: str
    name: str


class SplitCountsOut(WireModel):
    """`{train, validation, test}` — luôn đủ ba khoá khi có mặt (K02)."""

    train: int
    validation: int
    test: int


class DatasetVersionOut(WireModel):
    """`DatasetVersionSchema`: `manifestSha256`/`splitCounts` ⇔ `ready`, `failureCode` ⇔ `failed`."""

    created_at: WireDatetime
    dataset_id: str
    failure_code: str | None = None
    id: str
    manifest_sha256: str | None = None
    sequence: int
    source: str
    split_counts: SplitCountsOut | None = None
    status: str


DatasetPage = CursorPage[DatasetOut]
"""N28 — mới nhất trước, `family` gắn vào cursor."""

DatasetVersionPage = CursorPage[DatasetVersionOut]
"""N30 — `sequence` giảm dần."""


class CreateDatasetIn(WireRequest):
    """Thân N29; khoá lạ → 422 `VALIDATION` (C03)."""

    name: CleanName
    family: ModelFamily


class BuildDatasetVersionIn(WireRequest):
    """Thân N31; `projectIds` vắng = mọi dự án, có thì ít nhất một id (C02 `[]`).

    Không kiểm mẫu `prj_…` ở đây: id sai mẫu và id không có/dự án xoá mềm phải ra
    **cùng** 422 `field:"projectIds"` (không máy dò) — `service._checked_project_ids`
    kiểm cả ba bằng `is_id` để lỗi luôn ở đúng khoá `projectIds`, không `projectIds.0`.
    """

    project_ids: Annotated[list[str], Field(min_length=1)] | None = None


def dataset_out(row: DatasetRow) -> DatasetOut:
    """Dòng `datasets` → `DatasetOut`; bỏ `created_by`, `name_key` (K01)."""
    return DatasetOut(created_at=row.created_at, family=cast("ModelFamily", row.family), id=row.id, name=row.name)


def dataset_version_out(row: DatasetVersionRow) -> DatasetVersionOut:
    """Dòng `dataset_versions` → `DatasetVersionOut`; bỏ `project_ids`, `requeue_count`,
    `build_started_at`, `created_by` (K01)."""
    split_counts = SplitCountsOut(**row.split_counts) if row.split_counts is not None else None
    return DatasetVersionOut(
        created_at=row.created_at,
        dataset_id=row.dataset_id,
        failure_code=row.failure_code,
        id=row.id,
        manifest_sha256=row.manifest_sha256,
        sequence=row.sequence,
        source=row.source,
        split_counts=split_counts,
        status=row.status,
    )
