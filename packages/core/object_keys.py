"""Luật khoá object (BE-00 §8, K13) — nguồn duy nhất cho `packages.storage` và `packages.ml_contracts`.

Khoá là chuỗi ASCII `[A-Za-z0-9._-]` chia đoạn bằng `/`, không đoạn rỗng, `.` hay `..`,
tối đa `MAX_KEY_BYTES` byte, không trùng đuôi metadata của kho đĩa. Nằm ở lõi vì
`ml_contracts` không được nhập `storage` ([9] B5-01) mà vẫn phải kiểm khoá trong payload
không tin (NO-060). Sai luật → `ValueError`; người gọi đổi thành lỗi của tầng mình.
"""

import re
from typing import Final

MAX_KEY_BYTES: Final = 1024
META_SUFFIX: Final = ".meta.json"
"""Đuôi file metadata của `LocalDiskStorage`; khoá object không được trùng."""

_DOT_SEGMENTS: Final = frozenset({"", ".", ".."})
_SEGMENT_RE: Final = re.compile(r"[A-Za-z0-9._-]+")


def is_segment(value: str) -> bool:
    """`value` là đúng một đoạn khoá: `[A-Za-z0-9._-]+`, không phải `.` hay `..`, không chứa `/`."""
    return value not in _DOT_SEGMENTS and _SEGMENT_RE.fullmatch(value) is not None


def check_key(key: str) -> str:
    """Khoá hợp lệ → trả lại chính nó; sai → `ValueError` (không bao giờ ra ngoài kho).

    Đo độ dài theo byte UTF-8 (trần của S3), không theo ký tự.
    """
    if not key:
        raise ValueError("khoá rỗng")
    if len(key.encode("utf-8")) > MAX_KEY_BYTES:
        raise ValueError(f"khoá dài hơn {MAX_KEY_BYTES} byte")
    if key.endswith(META_SUFFIX):
        raise ValueError(f"khoá không được kết thúc bằng {META_SUFFIX}")
    for segment in key.split("/"):
        if is_segment(segment):
            continue
        if segment in _DOT_SEGMENTS:
            raise ValueError(f"khoá có đoạn rỗng, '.' hay '..': {key!r}")
        raise ValueError(f"đoạn khoá chỉ nhận [A-Za-z0-9._-]: {key!r}")
    return key


def check_prefix(prefix: str) -> str:
    """Tiền tố luôn kết thúc bằng `/` — nhờ vậy `projects/prj_A/` không chạm `projects/prj_AB/`."""
    if not prefix.endswith("/"):
        raise ValueError(f"tiền tố phải kết thúc bằng '/': {prefix!r}")
    check_key(prefix[:-1])
    return prefix
