"""Hợp đồng chung của job huấn luyện: khoá Redis, id bản model, tên trọng số, mẫu log (B6-03a [2]).

**Chỉ thư viện chuẩn + `packages.core`.** Đây là hợp đồng với runner B6-03b (cùng đợt W11,
tự khai cùng mẫu vì chưa nhập được nhau): không đổi mẫu khoá, mẫu tên, cách dựng id.
`LOG_TEMPLATES`/`render_log` dựng câu tiếng Việt cho `training_logs` từ khoá + tham số
(BE-00 §9 "Mẫu log huấn luyện"); cầu nối không bao giờ ghi văn bản do runner gửi thẳng.
"""

import re
from collections.abc import Mapping
from types import MappingProxyType
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


LOG_TEMPLATES: Final[Mapping[str, LogTemplate]] = MappingProxyType(
    {
        "training_gpu_waiting": LogTemplate("đang chờ khoá gpu để huấn luyện", frozenset()),
        "training_started": LogTemplate(
            "bắt đầu huấn luyện {base_model} trên {device}, {train} ảnh luyện, "
            "{validation} ảnh kiểm, cỡ lô {batch_size}",
            frozenset({"base_model", "device", "train", "validation", "batch_size"}),
        ),
        "training_dataset_ready": LogTemplate(
            "dữ liệu sẵn sàng: {train_tiles} mảnh luyện, {validation_tiles} mảnh kiểm, bỏ {skipped_boxes} hộp",
            frozenset({"train_tiles", "validation_tiles", "skipped_boxes"}),
        ),
        "training_epoch_finished": LogTemplate(
            "epoch {epoch} xong: loss {loss}, {metric} {value}",
            frozenset({"epoch", "loss", "metric", "value"}),
        ),
        "training_metric_skipped": LogTemplate(
            "bỏ qua số đo {metric} ở epoch {epoch}",
            frozenset({"epoch", "metric"}),
        ),
        "training_exported": LogTemplate(
            "đã xuất trọng số, {size_mib} mib",
            frozenset({"size_mib"}),
        ),
        "training_parity": LogTemplate(
            "đối chiếu độ khớp: {agreement}",
            frozenset({"agreement"}),
        ),
        "training_cancelled": LogTemplate(
            "đã huỷ ở epoch {epoch}",
            frozenset({"epoch"}),
        ),
        "training_failed": LogTemplate(
            "huấn luyện lỗi: {code}",
            frozenset({"code"}),
        ),
        "training_warning": LogTemplate(
            "cảnh báo: {code}",
            frozenset({"code"}),
        ),
    }
)
"""Bảng BE-00 §9 "Mẫu log huấn luyện": khoá khớp `^[a-z][a-z0-9_]{0,63}$`, câu viết thường."""

_LOG_PARAM_MAX_CHARS: Final = 2000

_ENV_ASSIGN_RE: Final = re.compile(r"\b[A-Z][A-Z0-9_]*=\S+")
"""`KHOÁ=giá trị` (vd `DATABASE_URL=postgres://…`): che trước URL nên cả cụm thành một."""

_ENV_VAR_RE: Final = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%")
"""`$VAR`, `${VAR}`, `%VAR%`."""

_URL_RE: Final = re.compile(r"https?://\S+")
"""URL kể cả query (`\\S+` ăn hết phần không khoảng trắng)."""

_WINDOWS_PATH_RE: Final = re.compile(r"[A-Za-z]:\\\S*")
"""Đường tuyệt đối Windows, vd `C:\\Users\\x`."""

_POSIX_PATH_RE: Final = re.compile(r"(?<![\w./])/(?:[\w.\-]+/)*[\w.\-]+")
"""Đường tuyệt đối POSIX, vd `/etc/passwd` (lookbehind tránh ăn phần đã che)."""

_HOME_PATH_RE: Final = re.compile(r"~(?:/[\w.\-]+)*")
"""`~` hay `~/dir`."""

_UPPER_SNAKE_RE: Final = re.compile(r"^[A-Z][A-Z0-9_]*$")
"""Mẫu mã lỗi hợp lệ cho tham số `code` (`MODEL_CHECKSUM_MISMATCH`, …)."""


def _mask_value(value: str) -> str:
    """Che URL, đường tuyệt đối, biến môi trường trong một giá trị tham số chuỗi (HOP-DONG-MOI "Log").

    Thứ tự bắt buộc: `KHOÁ=giá trị` trước URL để cả cụm (kể cả phần URL sau `=`) thành một
    `[biến môi trường]`, không bị URL cắt riêng phần đuôi.
    """
    value = _ENV_ASSIGN_RE.sub("[biến môi trường]", value)
    value = _ENV_VAR_RE.sub("[biến môi trường]", value)
    value = _URL_RE.sub("[url]", value)
    value = _WINDOWS_PATH_RE.sub("[đường dẫn]", value)
    value = _POSIX_PATH_RE.sub("[đường dẫn]", value)
    value = _HOME_PATH_RE.sub("[đường dẫn]", value)
    return value


def _format_param(key: str, value: str | int | float | bool) -> str:
    """Định dạng một tham số: `bool`→có/không, số thực dấu phẩy, `code` sai mẫu→`[mã]`, chuỗi bị che."""
    if isinstance(value, bool):
        return "có" if value else "không"
    if key == "code" and isinstance(value, str):
        return value if _UPPER_SNAKE_RE.fullmatch(value) else "[mã]"
    if isinstance(value, float):
        return str(value).replace(".", ",")
    if isinstance(value, int):
        return str(value)
    return _mask_value(value)


def render_log(template: str, params: Mapping[str, str | int | float | bool]) -> str | None:
    """Dựng câu log từ `LOG_TEMPLATES[template]` + `params`, che dữ liệu nhạy cảm, cắt ≤ 2000 ký tự.

    Khoá lạ (kể cả dạng chấm `training.started`), thiếu tham số bắt buộc, hay thừa tham số
    ngoài `line` → `None` (cầu nối bỏ dòng, BE-00 §9).
    """
    tmpl = LOG_TEMPLATES.get(template)
    if tmpl is None:
        return None
    provided = set(params)
    if tmpl.params - provided or (provided - tmpl.params - {"line"}):
        return None
    formatted = {key: _format_param(key, value) for key, value in params.items()}
    text = tmpl.text.format(**formatted)
    return text[:_LOG_PARAM_MAX_CHARS]
