"""Response `#9` (B7-01 [2]).

5 trường `bool | None`, mỗi trường `alias` tường minh bằng đúng khoá FE (khoá chứa
`.`/`-`, không phải định danh Python hợp lệ): `WireModel` bỏ trường `None` (W2), nên
khoá chưa cấu hình vắng mặt thay vì `null` (K01/K02).
"""

from pydantic import Field

from apps.api.core.wire import WireModel


class FeatureFlagsOut(WireModel):
    """`GET /api/feature-flags` — đúng 5 khoá của `flags.FEATURE_FLAG_KEYS`."""

    scene_instanced_walls: bool | None = Field(default=None, alias="scene.instanced-walls")
    scene_soft_shadows: bool | None = Field(default=None, alias="scene.soft-shadows")
    rules_parallel_run: bool | None = Field(default=None, alias="rules.parallel-run")
    export_pdf_vector: bool | None = Field(default=None, alias="export.pdf-vector")
    qc_live_collaboration: bool | None = Field(default=None, alias="qc.live-collaboration")
