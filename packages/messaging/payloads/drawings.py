"""Payload task của module bản vẽ (B2-04 [2], BE-00 §7).

Chỉ hai id: worker tự tra `pipeline_runs`, `uploads` dưới khoá dòng rồi mới làm việc
(BE-00 §7 "Không tin `apps/ml`"). Chép trạng thái vào thông điệp là cho worker một bản
sao cũ để tin; `run_id` thì luôn kiểm lại được.
"""

from typing import Annotated

from pydantic import AfterValidator

from packages.core.ids import check_id
from packages.messaging.tasks import TaskPayload

RunId = Annotated[str, AfterValidator(lambda value: check_id("run", value))]
UploadId = Annotated[str, AfterValidator(lambda value: check_id("upl", value))]


class PipelineStartPayload(TaskPayload):
    """`pipeline.orchestrate.start`: bắt đầu một lượt chạy cho một lượt tải đã `complete`."""

    schema_version: int = 1
    run_id: RunId
    upload_id: UploadId
