"""Response `#9` (B7-01 [2]).

10 trường `bool | None`, mỗi trường `alias` tường minh bằng đúng khoá FE (khoá chứa
`.`/`-`, không phải định danh Python hợp lệ): `WireModel` bỏ trường `None` (W2), nên
khoá chưa cấu hình vắng mặt thay vì `null` (K01/K02).
"""

from pydantic import Field

from apps.api.core.wire import WireModel


class FeatureFlagsOut(WireModel):
    """`GET /api/feature-flags` — đúng 10 khoá của `flags.FEATURE_FLAG_KEYS`."""

    scene_instanced_walls: bool | None = Field(default=None, alias="scene.instanced-walls")
    scene_soft_shadows: bool | None = Field(default=None, alias="scene.soft-shadows")
    rules_parallel_run: bool | None = Field(default=None, alias="rules.parallel-run")
    export_pdf_vector: bool | None = Field(default=None, alias="export.pdf-vector")
    qc_live_collaboration: bool | None = Field(default=None, alias="qc.live-collaboration")
    viewer_realism_idle: bool | None = Field(default=None, alias="viewer.realism-idle")
    viewer_realism_traa: bool | None = Field(default=None, alias="viewer.realism-traa")
    viewer_realism_hdri: bool | None = Field(default=None, alias="viewer.realism-hdri")
    viewer_realism_materials: bool | None = Field(default=None, alias="viewer.realism-materials")
    viewer_realism_details: bool | None = Field(default=None, alias="viewer.realism-details")
