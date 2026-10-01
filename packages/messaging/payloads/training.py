"""Hợp đồng chung của job huấn luyện: khoá Redis, id bản model, tên trọng số, mẫu log (B6-03a [2]).

**Chỉ thư viện chuẩn + `packages.core`.** Đây là hợp đồng với runner B6-03b (cùng đợt W11,
tự khai cùng mẫu vì chưa nhập được nhau): không đổi mẫu khoá, mẫu tên, cách dựng id.
`LOG_TEMPLATES`/`render_log` dựng câu tiếng Việt cho `training_logs` từ khoá + tham số
(BE-00 §9 "Mẫu log huấn luyện"); cầu nối không bao giờ ghi văn bản do runner gửi thẳng.
"""

import re
from typing import Final, NamedTuple

from packages.core.ids import check_id

WEIGHTS_NAME_RE: Final = re.compile(r"^weights-[0-9a-f]{32}\.onnx$")
"""Tên object trọng số dưới `model_artifact(trained_version_id(job), …)`; token 32 hex do runner sinh."""


def trained_version_id(job_id: str) -> str:
    """Id bản model mà job sinh ra: `mdl_` + ULID của `job_id` (một job ↔ một bản, J06).

    `job_id` sai mẫu `job_<ULID>` → `ValueError` (lỗi lập trình: id luôn đọc từ DB).
    """
    return "mdl_" + check_id("job", job_id).removeprefix("job_")


def cancel_key(job_id: str) -> str:
    """Khoá Redis báo huỷ: có mặt thì runner dừng, launcher không khởi chạy (BE-00 §7)."""
    return f"training:cancel:{job_id}"


def claim_key(job_id: str) -> str:
    """Khoá Redis runner giữ khi chạy job (token 32 hex, B6-03b); lịch của cầu nối chỉ đọc."""
    return f"training:claim:{job_id}"


class LogTemplate(NamedTuple):
    """Một mẫu câu log: câu tiếng Việt viết thường có chỗ `{tham_số}`, và tập tham số bắt buộc."""

    text: str
    params: frozenset[str]
