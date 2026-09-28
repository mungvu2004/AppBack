"""Model dây của #36, N17-N20 (B3-04 [2]); tên khớp zod của FE (`src/api/schemas/versions.ts`).

OpenAPI gộp model theo **tên lớp** toàn app (B3-03 vấp `ScaleMmPerPx` trùng), nên mọi lớp ở
đây mang tiền tố `Version…`/`FloorVersion…`. Trường tuỳ chọn (`note`, `label`) là `None` →
**vắng khoá** nhờ `WireModel` (W2, C17); `creatorId` giữ nguyên literal `system:pipeline`.

Thân request đặt `strict` cho số: `baseVersion: "3"` hay `label: 5` là 422 có `field`, không
được ép kiểu ngầm. Luật độ dài/ký tự của nhãn **không** nằm ở đây mà ở `service.normalize_label`
vì phải chuẩn hoá NFC + `strip` rồi mới đo, và Pydantic đo trước khi chuẩn hoá.
"""

from typing import Annotated

from pydantic import Field

from apps.api.core.wire import WireDatetime, WireModel, WireRequest
from apps.api.spatial_read.wire import DimensionOut, SpatialLayerOut


class VersionOut(WireModel):
    """#36: `Version` cũ của FE — đúng sáu trường, `note` vắng khi không có."""

    id: str
    project_id: str
    sequence: Annotated[int, Field(gt=0)]
    created_at: WireDatetime
    creator_id: str
    note: str | None = None


class FloorVersionSummaryOut(WireModel):
    """N17/N19/N20: một dòng lịch sử phiên bản theo tầng (`FloorVersionSummarySchema`)."""

    id: str
    sequence: Annotated[int, Field(gt=0)]
    floor_revision: Annotated[int, Field(ge=0)]
    created_at: WireDatetime
    creator_id: str
    creator_name: str
    note: str | None = None
    label: str | None = None
    has_snapshot: bool


class FloorVersionSnapshotOut(WireModel):
    """N18: nội dung một ảnh chụp — chỉ `layer` và `dimensions` (tỉ lệ, trục giữ hiện trạng)."""

    version_id: str
    layer: SpatialLayerOut
    dimensions: list[DimensionOut]


class VersionRestoreTargetIn(WireRequest):
    """`body` của N19: tầng người dùng tin là chủ của phiên bản; lệch → `VERSION_FLOOR_MISMATCH`."""

    floor_id: Annotated[str, Field(min_length=1)]


class VersionRestoreIn(WireRequest):
    """Thân N19 `{baseVersion, body: {floorId}}`; thiếu `baseVersion` bị guard 428 chặn trước."""

    base_version: Annotated[int, Field(strict=True, ge=0)]
    body: VersionRestoreTargetIn


class VersionLabelIn(WireRequest):
    """Thân N20 `{label}`: chuỗi thật (không ép số); rỗng nghĩa là gỡ nhãn."""

    label: Annotated[str, Field(strict=True)]
