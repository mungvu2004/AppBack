"""Luật khoá object (BE-00 §8, K13) — nguồn duy nhất cho `packages.storage` và `packages.ml_contracts`.

Khoá là chuỗi ASCII `[A-Za-z0-9._-]` chia đoạn bằng `/`, không đoạn rỗng, `.` hay `..`,
tối đa `MAX_KEY_BYTES` byte, không trùng đuôi metadata của kho đĩa. Nằm ở lõi vì
`ml_contracts` không được nhập `storage` ([9] B5-01) mà vẫn phải kiểm khoá trong payload
không tin (NO-060). Cùng lý do, bố cục tiền tố dự án và lượt tải lên cũng ở đây (NO-077);
các hàm dựng khoá khác vẫn ở `packages.storage.keys`. Sai luật → `ValueError`; người gọi
đổi thành lỗi của tầng mình.
"""

import re
from typing import Final

from packages.core.ids import check_id, is_spatial_id

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


def project_prefix(project: str) -> str:
    """Tiền tố mọi object của một dự án — dùng khi dọn rác dự án xoá mềm."""
    return check_prefix(f"projects/{check_id('prj', project)}/")


def upload_prefix(project: str, floor: str, upload: str) -> str:
    """Tiền tố mọi object của một lượt tải lên (bản gốc, trang, artifact).

    Bố cục `projects/{prj}/floors/{L-…}/uploads/{upl}/` — nguồn duy nhất cho `storage` (dựng khoá)
    và `ml_contracts` (kiểm payload), NO-077. Nằm dưới `project_prefix` nên dọn rác dự án phủ mọi
    lượt tải lên. Id sai → `ValueError` nêu đúng trường.
    """
    if not is_spatial_id("level", floor):
        raise ValueError(f"id tầng sai mẫu L-<base36 HOA>: {floor!r}")
    return check_prefix(f"{project_prefix(project)}floors/{floor}/uploads/{check_id('upl', upload)}/")


def upload_prefix_of(key: str) -> str:
    """Tiền tố lượt tải lên đứng đầu `key` (khoá không tin trong payload ML); sai → `ValueError`.

    Kiểm cả khoá bằng `check_key` trước (fail-closed, NO-088): đuôi `../x` hay `//` không được ra
    tiền tố. Đọc id ở vị trí đoạn của bố cục rồi dựng lại bằng `upload_prefix`: chỉ nhận khi bản
    dựng lại là đầu của `key` từng byte, nên bố cục không có bản tách thứ hai (NO-077).
    """
    parts = check_key(key).split("/", 6)
    if len(parts) == 7:
        prefix = upload_prefix(parts[1], parts[3], parts[5])
        if key.startswith(prefix):
            return prefix
    raise ValueError(f"khoá không nằm dưới một lượt tải lên: {key!r}")
