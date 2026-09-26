"""Nơi **duy nhất** đổi cột `floor_documents.document` (jsonb) ↔ mô hình `packages.domain.spatial`.

Một luật đọc, một luật ghi, một lỗi: mọi module khác nhận `FloorDocument` đã giải mã
(`documents.py`) và không bao giờ tự chạm vào dict dây. Nhờ vậy nâng lược đồ chỉ phải
sửa ở đây (FIX.md luật 7).

Ghi bằng `model_dump(mode="json", by_alias=True, exclude_none=True)`: khoá camelCase, mm
là số nguyên JSON, trường tuỳ chọn **vắng khoá** chứ không `null` (W2, K02). Đọc bằng
`model_validate` của B3-01 với `extra="forbid"`: khoá lạ, mm thập phân, id sai mẫu W4 đều
là tài liệu hỏng. Đọc **không bao giờ tự sửa** — một tài liệu hỏng là lỗi phải thấy, không
phải dữ liệu cần đoán lại.

`axes` là `[]` ở v1 (hợp đồng [2]) dù mẫu A14 có bốn trục: FE chưa vẽ trục nào, và ghi
trục vào jsonb bây giờ sẽ thành dữ liệu không ai đọc mà phải migrate về sau.
"""

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

from packages.domain.spatial import Axis, Dimension, SpatialLayer


class DocumentCorruptError(Exception):
    """Cột `document` (hay `schema_version`) của một tầng không giải mã được.

    Không phải `AppError`: người dùng không sửa được gì, nên handler cuối trả 500 và
    log `floor_pk` để người vận hành chạy `check-documents` tìm hết các dòng cùng cảnh.
    """


class _Envelope(BaseModel):
    """Khung của cột `document`; `extra="forbid"` nên khoá lạ ở **mức ngoài** cũng là hỏng."""

    model_config = ConfigDict(extra="forbid")

    layer: SpatialLayer
    axes: tuple[Axis, ...]
    dimensions: tuple[Dimension, ...]


def document_to_json(layer: SpatialLayer, axes: Sequence[Axis], dimensions: Sequence[Dimension]) -> dict[str, object]:
    """Dạng dây của một tài liệu. `axes` được nhận để chữ ký ổn định nhưng v1 luôn ghi `[]`."""
    return {
        "layer": layer.model_dump(mode="json", by_alias=True, exclude_none=True),
        "axes": [],
        "dimensions": [dimension.model_dump(mode="json", by_alias=True, exclude_none=True) for dimension in dimensions],
    }


def document_from_json(raw: Mapping[str, object]) -> tuple[SpatialLayer, tuple[Axis, ...], tuple[Dimension, ...]]:
    """Giải một cột `document`; bất kỳ lệch nào so với mô hình B3-01 → `DocumentCorruptError`."""
    try:
        envelope = _Envelope.model_validate(raw)
    except ValidationError as error:
        raise DocumentCorruptError(str(error)) from error
    return envelope.layer, envelope.axes, envelope.dimensions


def entity_ids(layer: SpatialLayer) -> frozenset[str]:
    """Id của mọi tường, ô mở, phòng, đồ đạc — đúng tập `floor_entity_ids` giữ cho tầng ấy (W4).

    **Không** gồm kích thước: `Dimension` là chú thích đo vẽ, B3-03 thêm bớt tự do và
    không tranh id với tầng khác. Toà mẫu A14 vì thế ra 48 + 16 + 21 + 14 = 99 id.
    """
    return frozenset(entity.id for entity in layer.entities())
