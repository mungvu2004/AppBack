"""Factory bản trọng số model ML cho test (B6-01), theo mẫu `packages/testing/factories/library.py`.

Ghi thẳng `model_versions`, không qua N26 hay `register_trained_version`: test cần dựng bản đã
`completed`, bản của job huấn luyện, bản `safetensors` — những thứ một lượt tải lên thật không
dựng được trong một dòng. Mọi CHECK của bảng được tôn trọng: `metrics` chỉ có ở bản `completed`
và mang **đúng** khoá `FAMILY_METRIC[family]`, `training_job_id` ⇔ `dataset_version_id`, và đúng
một trong `weights_key`/`pinned_name` có giá trị (ở đây luôn là `weights_key`).

Có `commit` như `make_library_item`: route đọc bằng session khác nên chỉ `flush` thì không thấy.
`created_at`/`updated_at` đặt tường minh để dòng đọc lại được sau commit mà không cần `refresh`,
và để test phân trang xếp được thứ tự (`created_at` truyền vào).

Đưa `storage` vào thì object trọng số **thật** được ghi dưới `model_artifact(id, "weights.<đuôi>")`:
byte đầu đúng định dạng (K12, K14) và `checksum_sha256` là SHA-256 của chính bytes ấy, nên
`storage.stat(...).sha256` khớp cột.
"""

import struct
from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.errors import SYSTEM_PIPELINE
from packages.core.ids import new_id
from packages.core.text import nfc
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.ml_contracts.families import FAMILY_METRIC
from packages.storage.keys import model_artifact
from packages.storage.port import ObjectStorage

_ONNX_BYTES: Final = b"\x08\x01\x12\x06kiem\x00"
"""ONNX tí hon: byte 0 `0x08` (trường 1, wire type 0 — `ir_version` của protobuf)."""

_SAFETENSORS_HEADER: Final = b'{"__metadata__":{}}'
_SAFETENSORS_BYTES: Final = struct.pack("<Q", len(_SAFETENSORS_HEADER)) + _SAFETENSORS_HEADER
"""safetensors tí hon: 8 byte LE độ dài header rồi `{` (M02)."""

_WEIGHTS: Final[dict[str, bytes]] = {"onnx": _ONNX_BYTES, "safetensors": _SAFETENSORS_BYTES}
_METRIC_VALUE: Final[dict[str, float]] = {"iou": 0.82, "map50": 0.74, "cer": 0.05}
_FAMILY_METRIC: Final[Mapping[str, str]] = {str(family): metric for family, metric in FAMILY_METRIC.items()}
"""Bảng của `ml_contracts` với khoá nới về `str`: `family` của test là chuỗi, không `Literal`."""


async def make_model_version(
    db: AsyncSession,
    storage: ObjectStorage | None = None,
    *,
    family: str,
    status: str = "completed",
    weights_format: str = "onnx",
    training: bool = False,
    label: str = "bản kiểm",
    creator_id: str | None = None,
    created_at: datetime | None = None,
) -> ModelVersionRow:
    """Một dòng `model_versions` đã `commit`; trả chính `ModelVersionRow` ấy.

    `status="completed"` → `metrics` đúng khoá của họ; `training=True` → có `training_job_id` và
    `dataset_version_id` (bản do job huấn luyện sinh). `storage` khác `None` → object trọng số
    thật trong kho, khớp `checksum_sha256`.
    """
    clock = SystemClock()
    at = created_at if created_at is not None else clock.now()
    version_id = new_id("mdl", clock)
    weights = _WEIGHTS[weights_format]
    key = model_artifact(version_id, f"weights.{weights_format}")
    if storage is not None:
        await storage.put(key, weights, content_type="application/octet-stream", max_bytes=len(weights))
    metric = _FAMILY_METRIC[family]  # KeyError nếu họ lạ — lỗi của test, không của factory
    row = ModelVersionRow(
        id=version_id,
        family=family,
        label=nfc(label),
        weights_format=weights_format,
        checksum_sha256=sha256(weights).hexdigest(),
        weights_key=key,
        training_job_id=new_id("job", clock) if training else None,
        dataset_version_id=new_id("dsv", clock) if training else None,
        evaluation_status=status,
        metrics={metric: _METRIC_VALUE[metric]} if status == "completed" else None,
        evaluation_attempts=0,
        creator_id=creator_id if creator_id is not None else SYSTEM_PIPELINE,
        created_at=at,
        updated_at=at,
    )
    db.add(row)
    await db.commit()
    return row
