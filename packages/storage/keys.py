"""Khoá object (BE-00 §8) và kiểm khoá an toàn (K13).

Mọi hàm nhận khoá của gói này gọi `check_key`/`check_prefix` trước khi chạm kho:
khoá không bao giờ được nối thẳng từ chuỗi người dùng. Luật khoá nằm ở
`packages.core.object_keys` (một nguồn với `ml_contracts`, NO-060); ở đây xuất lại tên cũ
cho `local.py`, `s3.py`. Hàm dựng khoá kiểm id theo đúng mẫu của `packages.core.ids`, nên
khoá sinh ra luôn nằm trong cây đã khai.
"""

import re
from typing import Final

from packages.core.ids import IdPrefix, is_id, is_spatial_id
from packages.core.object_keys import META_SUFFIX as META_SUFFIX
from packages.core.object_keys import check_key as check_key
from packages.core.object_keys import check_prefix as check_prefix
from packages.core.object_keys import is_segment
from packages.core.pipeline import PIPELINE_STEPS
from packages.storage.sniff import ImageKind

MAX_ITEM_LEN: Final = 64

_ITEM_RE: Final = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_EXT_RE: Final = re.compile(r"[a-z0-9]{1,8}")
# Thân ULID của `packages.core.ids` (Crockford base32 HOA, 26 ký tự).
_ULID_RE: Final = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")
_STEP_IDS: Final = frozenset(step for step, _ in PIPELINE_STEPS)
_EXT_KIND: Final[dict[str, ImageKind]] = {"png": "png", "jpg": "jpeg"}


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
    if not is_segment(value):
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


def server_chosen_kind(key: str) -> ImageKind | None:
    """Loại ảnh suy từ đuôi khoá do server đặt tên (ảnh đại diện, `…/pages/{i}.png`); khoá khác → `None`.

    Chỉ khoá mà server chọn đuôi sau khi đã kiểm magic bytes mới được ký URL với `kind` truyền
    sẵn (W23, K15); `original.<đuôi>` mang đuôi người dùng khai nên không bao giờ khớp (NO-011).
    "Do server đặt" ⇔ chính `avatar`/`upload_page` dựng lại được đúng khoá đó, nên luật id
    (`packages.core.ids`) và bố cục chỉ có một nguồn với hàm dựng (NO-073). Hàm dựng ném
    `ValueError` nghĩa là khoá không do server đặt — kết quả `None`, không phải lỗi.
    """
    try:
        match key.split("/"):
            case ["users", user, "avatar", name]:
                ulid, _, ext = name.partition(".")
                avatar(user, ulid, ext)  # dựng được thì khoá dựng lại trùng từng byte với `key`
                return _EXT_KIND[ext]
            case ["projects", project, "floors", floor, "uploads", upload, "pages", name]:
                index = name.removesuffix(".png")
                # `int` chuẩn hoá `007`, chữ số Unicode: khoá đó server không bao giờ sinh ra.
                if index.isdecimal() and upload_page(project, floor, upload, int(index)) == key:
                    return "png"
    except ValueError:
        return None
    return None
