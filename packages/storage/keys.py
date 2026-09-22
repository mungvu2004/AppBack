"""Khoá object (BE-00 §8) và kiểm khoá an toàn (K13).

Mọi hàm nhận khoá của gói này gọi `check_key`/`check_prefix` trước khi chạm kho:
khoá không bao giờ được nối thẳng từ chuỗi người dùng. Hàm dựng khoá kiểm id theo
đúng mẫu của `packages.core.ids`, nên khoá sinh ra luôn nằm trong cây đã khai.
"""

import re
from typing import Final

from packages.core.ids import IdPrefix, is_id, is_spatial_id
from packages.core.pipeline import PIPELINE_STEPS
from packages.storage.sniff import ImageKind

MAX_KEY_BYTES: Final = 1024
MAX_ITEM_LEN: Final = 64
META_SUFFIX: Final = ".meta.json"
"""Đuôi file metadata của `LocalDiskStorage`; khoá object không được trùng."""

_SEGMENT_RE: Final = re.compile(r"[A-Za-z0-9._-]+")
_ITEM_RE: Final = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_EXT_RE: Final = re.compile(r"[a-z0-9]{1,8}")
# Thân ULID của `packages.core.ids` (Crockford base32 HOA, 26 ký tự).
_ULID_RE: Final = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")
_STEP_IDS: Final = frozenset(step for step, _ in PIPELINE_STEPS)

# Khoá mà **server** chọn đuôi sau khi đã kiểm magic bytes (ảnh đại diện, ảnh trang đã tách)
# là nơi duy nhất được ký URL với `kind` truyền sẵn (W23, K15). `original.<đuôi>` mang đuôi
# người dùng khai nên không bao giờ khớp (NO-011).
_ULID: Final = _ULID_RE.pattern
_SERVER_NAMED_RE: Final = re.compile(
    rf"users/usr_{_ULID}/avatar/{_ULID}\.(?P<avatar>png|jpg)"
    rf"|projects/prj_{_ULID}/floors/L-[0-9A-Z]{{10,64}}/uploads/upl_{_ULID}/pages/[0-9]+\.png"
)
_EXT_KIND: Final[dict[str, ImageKind]] = {"png": "png", "jpg": "jpeg"}


def check_key(key: str) -> str:
    """Khoá hợp lệ → trả lại chính nó; sai → `ValueError` (không bao giờ ra ngoài kho)."""
    if not key:
        raise ValueError("khoá rỗng")
    if len(key.encode("utf-8")) > MAX_KEY_BYTES:
        raise ValueError(f"khoá dài hơn {MAX_KEY_BYTES} byte")
    if key.endswith(META_SUFFIX):
        raise ValueError(f"khoá không được kết thúc bằng {META_SUFFIX}")
    for segment in key.split("/"):
        if segment in ("", ".", ".."):
            raise ValueError(f"khoá có đoạn rỗng, '.' hay '..': {key!r}")
        if not _SEGMENT_RE.fullmatch(segment):
            raise ValueError(f"đoạn khoá chỉ nhận [A-Za-z0-9._-]: {key!r}")
    return key


def check_prefix(prefix: str) -> str:
    """Tiền tố luôn kết thúc bằng `/` — nhờ vậy `projects/prj_A/` không chạm `projects/prj_AB/`."""
    if not prefix.endswith("/"):
        raise ValueError(f"tiền tố phải kết thúc bằng '/': {prefix!r}")
    check_key(prefix[:-1])
    return prefix


def server_chosen_kind(key: str) -> ImageKind | None:
    """Loại ảnh suy từ đuôi khoá do server đặt tên (ảnh đại diện, `…/pages/{i}.png`); khoá khác → `None`."""
    matched = _SERVER_NAMED_RE.fullmatch(key)
    if matched is None:
        return None
    return _EXT_KIND[matched.group("avatar") or "png"]


def _entity_id(prefix: IdPrefix, value: str) -> str:
    """Id tài nguyên đúng tiền tố; sai → `ValueError` trước khi chạm kho."""
    if not is_id(prefix, value):
        raise ValueError(f"id phải có dạng {prefix}_<ULID>: {value!r}")
    return value


def _level_id(value: str) -> str:
    """Id tầng do client sinh, đúng mẫu `L-<base36 HOA>` (W4)."""
    if not is_spatial_id("level", value):
        raise ValueError(f"id tầng sai mẫu L-<base36 HOA>: {value!r}")
    return value


def _name(value: str) -> str:
    """Tên object là **một** đoạn khoá — chặn tên lồng đường dẫn."""
    if value in (".", "..") or not _SEGMENT_RE.fullmatch(value):
        raise ValueError(f"tên object phải là một đoạn [A-Za-z0-9._-]: {value!r}")
    return value


def _extension(value: str) -> str:
    """Đuôi tệp do server chọn: 1-8 ký tự thường, không dấu chấm."""
    if not _EXT_RE.fullmatch(value):
        raise ValueError(f"đuôi tệp phải là 1-8 ký tự [a-z0-9]: {value!r}")
    return value


def project_prefix(project: str) -> str:
    """Tiền tố mọi object của một dự án — dùng khi dọn rác dự án xoá mềm."""
    return check_prefix(f"projects/{_entity_id('prj', project)}/")


def upload_prefix(project: str, floor: str, upload: str) -> str:
    """Tiền tố mọi object của một lượt tải lên (bản gốc, trang, artifact)."""
    return check_prefix(f"{project_prefix(project)}floors/{_level_id(floor)}/uploads/{_entity_id('upl', upload)}/")


def upload_original(project: str, floor: str, upload: str, ext: str) -> str:
    """Khoá tệp gốc người dùng tải lên."""
    return check_key(f"{upload_prefix(project, floor, upload)}original.{_extension(ext)}")


def upload_page(project: str, floor: str, upload: str, index: int) -> str:
    """Khoá ảnh PNG của một trang đã tách từ tệp gốc."""
    if index < 0:
        raise ValueError(f"số trang không âm: {index}")
    return check_key(f"{upload_prefix(project, floor, upload)}pages/{index}.png")


def run_artifact(project: str, floor: str, upload: str, run: str, step: str, name: str) -> str:
    """Khoá artifact của một bước pipeline trong một lượt chạy."""
    if step not in _STEP_IDS:
        raise ValueError(f"bước pipeline lạ: {step!r}")
    prefix = upload_prefix(project, floor, upload)
    return check_key(f"{prefix}runs/{_entity_id('run', run)}/{step}/{_name(name)}")


def library_object(item: str, name: str) -> str:
    """Khoá object của một mục thư viện (`.glb`, ảnh xem trước)."""
    if not _ITEM_RE.fullmatch(item) or len(item) > MAX_ITEM_LEN:
        raise ValueError(f"id thư viện phải khớp ^[a-z0-9]+(-[a-z0-9]+)*$ và ≤ {MAX_ITEM_LEN} ký tự: {item!r}")
    return check_key(f"library/{item}/{_name(name)}")


def model_artifact(model: str, name: str) -> str:
    """Khoá artifact của một phiên bản mô hình ML."""
    return check_key(f"ml/models/{_entity_id('mdl', model)}/{_name(name)}")


def dataset_object(dataset_version: str, name: str) -> str:
    """Khoá object của một phiên bản tập dữ liệu ML."""
    return check_key(f"ml/datasets/{_entity_id('dsv', dataset_version)}/{_name(name)}")


def avatar(user: str, ulid: str, ext: str) -> str:
    """Khoá ảnh đại diện; đuôi do server chọn sau khi đã kiểm magic bytes (K14)."""
    if not _ULID_RE.fullmatch(ulid):
        raise ValueError(f"tên ảnh đại diện phải là ULID: {ulid!r}")
    if ext not in _EXT_KIND:
        raise ValueError(f"ảnh đại diện chỉ nhận đuôi {sorted(_EXT_KIND)}: {ext!r}")
    return check_key(f"users/{_entity_id('usr', user)}/avatar/{ulid}.{ext}")
