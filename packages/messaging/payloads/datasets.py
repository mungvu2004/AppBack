"""Payload task của module dataset (B6-02 [2], BE-00 §7).

Chỉ một id: worker tự tra `dataset_versions` dưới khoá dòng (`SafeLock`) rồi mới làm việc
(BE-00 §7 "Không tin `apps/ml`"), giống `PipelineStartPayload` của B2-04.
"""

from typing import Annotated, Final

from pydantic import AfterValidator

from packages.core.ids import check_id
from packages.messaging.tasks import TaskPayload

BUILD_VERSION_TASK: Final = "default.datasets.build_version"
"""Tên task dựng phiên bản — khai ở đây vì cả hai phía đều nhập module này.

`apps.api` (N31 gửi) và `apps.worker` (đăng ký thân task) không được nhập nhau
(`.importlinter`), nên nếu mỗi bên tự khai chuỗi thì một lần đổi tên sẽ lệch âm thầm: route
gửi lên hàng mà không worker nào nghe.
"""

DatasetVersionId = Annotated[str, AfterValidator(lambda value: check_id("dsv", value))]


class BuildDatasetVersionPayload(TaskPayload):
    """`default.datasets.build_version`: dựng mẫu cho một phiên bản `building`."""

    schema_version: int = 1
    dataset_version_id: DatasetVersionId
