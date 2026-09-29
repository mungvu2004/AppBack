"""Mã lỗi riêng của registry model ML (B6-01 [2]); mã lõi ở `packages.core.error_codes`.

Cả bốn đều 422 vì lỗi nằm ở **dữ liệu yêu cầu trỏ tới**, không phải ở quyền hay định dạng
thân: bản thuộc họ khác, bản chưa đánh giá, checksum lệch, định dạng trọng số không nhận.
FE hiện thông báo riêng cho từng mã (`adminMl.ts`, HOP-DONG-MOI §8).

Hai hàm `not_found` ở đây để N23-N27 không chép chuỗi `resource` — `"modelFamily"` và
`"modelVersion"` là hai giá trị hợp lệ của `packages.core.errors.RESOURCES`.
"""

from typing import Final

from packages.core.error_codes import NOT_FOUND
from packages.core.errors import ERRORS, AppError

MODEL_VERSION_FAMILY_MISMATCH = ERRORS.define("MODEL_VERSION_FAMILY_MISMATCH", 422)
"""Bản trỏ tới thuộc họ khác, hay `versionId: null` gửi cho họ không phải `wallSegmentation`."""

MODEL_VERSION_NOT_EVALUATED = ERRORS.define("MODEL_VERSION_NOT_EVALUATED", 422)
"""Kích hoạt một bản chưa `completed`: chưa ai biết nó đo được bao nhiêu."""

MODEL_CHECKSUM_MISMATCH = ERRORS.define("MODEL_CHECKSUM_MISMATCH", 422)
"""SHA-256 đo trong lúc nhận tệp khác `checksumSha256` khai ở `metadata` (M03)."""

MODEL_FORMAT_UNSUPPORTED = ERRORS.define("MODEL_FORMAT_UNSUPPORTED", 422)
"""Byte đầu không khớp định dạng khai, hay định dạng không kích hoạt được (K12, K14)."""

MODEL_FAMILY_RESOURCE: Final = "modelFamily"
MODEL_VERSION_RESOURCE: Final = "modelVersion"


def family_not_found() -> AppError:
    """404 `NOT_FOUND` `resource:"modelFamily"` — `{family}` ngoài ba họ của ống xử lý."""
    return NOT_FOUND.error(resource=MODEL_FAMILY_RESOURCE)


def version_not_found() -> AppError:
    """404 `NOT_FOUND` `resource:"modelVersion"` — id sai mẫu cũng trả 404, không 422 (K)."""
    return NOT_FOUND.error(resource=MODEL_VERSION_RESOURCE)
