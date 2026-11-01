"""Payload task của module bake ánh sáng (LB-01, BE-00 §7).

Chỉ một id: worker tự tra `lighting_bakes` rồi mới làm việc (BE-00 §7 "Không tin `apps/ml`"),
giống `BuildDatasetVersionPayload` của B6-02.
"""

from typing import Annotated, Final

from pydantic import AfterValidator

from packages.core.ids import check_id
from packages.messaging.tasks import TaskPayload

LIGHTING_BAKE_TASK: Final = "bake.lighting.run"
"""Tên task bake — khai ở đây vì cả `apps.api` (N42 gửi) và `apps.worker` (đăng ký thân task)
đều nhập module này; hai bên không nhập nhau (`.importlinter`), tự khai chuỗi thì đổi tên sẽ lệch âm thầm.
Tiền tố `bake.` đưa task lên hàng `bake` (`packages.messaging.celery_app`).
"""

LIGHTING_BAKE_INPUT: Final = "input.glb"
"""Tên object GLB đầu vào API ghi dưới `lighting_bake_prefix(project_id, bake_id)`."""

LIGHTING_BAKE_FILES: Final = ("baked.glb", "lightmap.png", "manifest.json")
"""Tên object đầu ra worker ghi; N44 chỉ phục vụ đúng các tên này."""

LightingBakeId = Annotated[str, AfterValidator(lambda value: check_id("bak", value))]


class LightingBakePayload(TaskPayload):
    """`bake.lighting.run`: bake ánh sáng cho một lượt `queued`."""

    schema_version: int = 1
    bake_id: LightingBakeId
