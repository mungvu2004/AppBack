"""Payload task của AI chọn phong cách nội thất (AID-01, BE-00 §7).

Chỉ một id: worker tự tra `design_concepts` (qua `apps.api.design_director.state.claim`) rồi mới làm việc.
"""

from typing import Annotated, Final

from pydantic import AfterValidator

from packages.core.ids import check_id
from packages.messaging.tasks import TaskPayload

DESIGN_DIRECTOR_TASK: Final = "design.director.run"
"""Tên task — khai ở đây vì cả `apps.api` (N48, `enqueue_auto`, lịch quét gửi) và `apps.worker` (thân task)
đều nhập module này. Tiền tố `design.` không có trong bảng định tuyến nên đi hàng `default`.
"""

DesignConceptId = Annotated[str, AfterValidator(lambda value: check_id("dcn", value))]


class DesignConceptPayload(TaskPayload):
    """`design.director.run`: sinh concept cho một lượt `queued`."""

    schema_version: int = 1
    concept_id: DesignConceptId
