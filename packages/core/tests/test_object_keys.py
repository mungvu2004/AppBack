"""Luật khoá object của lõi (NO-060) và bố cục tiền tố lượt tải lên (NO-077): mẫu biên chung của `storage`
và `ml_contracts`, kèm thông báo."""

from collections.abc import Callable

import pytest

from packages.core import ids, object_keys
from packages.core.object_keys import MAX_KEY_BYTES, check_key, check_prefix, is_segment

DOTS = "đoạn rỗng, '.' hay '..'"
CHARS = r"chỉ nhận \[A-Za-z0-9._-\]"
PROJECT = "prj_01ARZ3NDEKTSV4RRFFQ69G5FAV"
FLOOR = "L-ABCDEFGHIJ"
UPLOAD = "upl_01ARZ3NDEKTSV4RRFFQ69G5FBW"
UPLOAD_PREFIX = f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/"
NOT_UNDER = "không nằm dưới một lượt tải lên"


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        ("", "khoá rỗng"),
        ("a/../b", DOTS),
        ("../secret", DOTS),
        ("a/./b", DOTS),
        ("./a", DOTS),
        ("a//b", DOTS),
        ("/a", DOTS),
        ("a/b/", DOTS),
        ("a\x00b", CHARS),
        ("a\x7fb", CHARS),
        ("a\\b", CHARS),
        ("a b", CHARS),
        ("khóa", CHARS),
        ("khóa", CHARS),
        ("tệp.png", CHARS),
        ("a" * (MAX_KEY_BYTES + 1), f"dài hơn {MAX_KEY_BYTES} byte"),
        ("é" * (MAX_KEY_BYTES // 2 + 1), f"dài hơn {MAX_KEY_BYTES} byte"),
        ("x.meta.json", r"kết thúc bằng \.meta\.json"),
        ("a/x.meta.json", r"kết thúc bằng \.meta\.json"),
    ],
)
def test_check_key_rejects_unsafe(bad: str, match: str) -> None:
    """Rỗng, đoạn chấm, ký tự ngoài ASCII an toàn (cả NFC lẫn NFD), quá trần byte, đuôi metadata."""
    with pytest.raises(ValueError, match=match):
        check_key(bad)


@pytest.mark.parametrize(
    "good", ["a", "ml/models/x/model.onnx", "projects/prj_A/x.png", "a/.../b", "a" * MAX_KEY_BYTES]
)
def test_check_key_accepts_safe(good: str) -> None:
    """Chạm trần đúng `MAX_KEY_BYTES` vẫn đạt; chỉ `.`/`..` là đoạn chấm, `...` là tên thường."""
    assert check_key(good) == good


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        ("projects/prj_A", "tiền tố"),
        ("", "tiền tố"),
        ("/", "khoá rỗng"),
        ("projects/prj_A//", DOTS),
    ],
)
def test_check_prefix_requires_trailing_slash_and_valid_key(bad: str, match: str) -> None:
    """Tiền tố thiếu `/` cuối, hoặc phần trước `/` không phải khoá hợp lệ → `ValueError`."""
    with pytest.raises(ValueError, match=match):
        check_prefix(bad)


def test_check_prefix_accepts_valid_prefix() -> None:
    assert check_prefix("projects/prj_A/") == "projects/prj_A/"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("a", True), ("...", True), ("x.png", True), ("", False), (".", False), ("..", False), ("a/b", False)],
)
def test_is_segment(value: str, expected: bool) -> None:
    """Một đoạn không chứa `/` và không là đoạn chấm."""
    assert is_segment(value) is expected


def test_upload_prefix_layout() -> None:
    """BE-00 §8: lượt tải lên nằm dưới tiền tố dự án, nên dọn rác dự án phủ mọi lượt tải lên."""
    assert object_keys.project_prefix(PROJECT) == f"projects/{PROJECT}/"
    assert object_keys.upload_prefix(PROJECT, FLOOR, UPLOAD) == UPLOAD_PREFIX


@pytest.mark.parametrize(
    ("build", "match"),
    [
        (lambda: object_keys.project_prefix("prj_lowercase"), "prj_"),
        (lambda: object_keys.upload_prefix(UPLOAD, FLOOR, UPLOAD), "prj_"),
        (lambda: object_keys.upload_prefix(PROJECT, "W-ABCDEFGHIJ", UPLOAD), "id tầng"),
        (lambda: object_keys.upload_prefix(PROJECT, "L-" + "A" * 9, UPLOAD), "id tầng"),
        (lambda: object_keys.upload_prefix(PROJECT, FLOOR, PROJECT), "upl_"),
    ],
)
def test_upload_prefix_rejects_wrong_ids(build: Callable[[], str], match: str) -> None:
    """Id sai mẫu → `ValueError` nêu đúng trường, trước khi thành khoá."""
    with pytest.raises(ValueError, match=match):
        build()


@pytest.mark.parametrize(
    ("module", "rule", "match"), [(object_keys, "is_spatial_id", "id tầng"), (ids, "is_id", "prj_")]
)
def test_upload_prefix_reads_id_rules_of_core_ids(
    monkeypatch: pytest.MonkeyPatch, module: object, rule: str, match: str
) -> None:
    """Đột biến luật id của `packages.core.ids` thì bố cục từ chối theo — không regex id chép tay."""
    monkeypatch.setattr(module, rule, lambda *_: False)
    with pytest.raises(ValueError, match=match):
        object_keys.upload_prefix(PROJECT, FLOOR, UPLOAD)


@pytest.mark.parametrize("key", [f"{UPLOAD_PREFIX}pages/0.png", f"{UPLOAD_PREFIX}runs/x/y/z.json"])
def test_upload_prefix_of_accepts(key: str) -> None:
    """Khoá hợp lệ dưới một lượt tải lên → đúng tiền tố của lượt đó."""
    assert object_keys.upload_prefix_of(key) == UPLOAD_PREFIX


@pytest.mark.parametrize(
    ("key", "match"),
    [
        ("", "khoá rỗng"),
        ("library/x/pages/0.png", NOT_UNDER),
        (UPLOAD_PREFIX[:-1], NOT_UNDER),
        (UPLOAD_PREFIX, DOTS),
        (f"{UPLOAD_PREFIX}../x", DOTS),
        (f"{UPLOAD_PREFIX}../../../../x", DOTS),
        (f"{UPLOAD_PREFIX}pages//0.png", DOTS),
        (f"{UPLOAD_PREFIX}pages/./0.png", DOTS),
        (f"{UPLOAD_PREFIX}pages/0 .png", CHARS),
        (f"{UPLOAD_PREFIX}x.meta.json", r"kết thúc bằng \.meta\.json"),
        (f"project/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/pages/0.png", NOT_UNDER),
        (f"projects/{PROJECT}/levels/{FLOOR}/uploads/{UPLOAD}/pages/0.png", NOT_UNDER),
        (f"projects/{PROJECT}/floors/{FLOOR}/upload/{UPLOAD}/pages/0.png", NOT_UNDER),
        (f"projects/{PROJECT}/floors/bad/uploads/{UPLOAD}/pages/0.png", "id tầng"),
        (f"projects/{UPLOAD}/floors/{FLOOR}/uploads/{UPLOAD}/pages/0.png", "prj_"),
        (f"projects/{PROJECT}/floors/{FLOOR}/uploads/{PROJECT}/pages/0.png", "upl_"),
    ],
)
def test_upload_prefix_of_rejects(key: str, match: str) -> None:
    """Sai chữ của bố cục, thiếu đoạn, id sai mẫu ở vị trí id, hay khoá không an toàn (NO-088) → `ValueError`.

    Tiền tố trần (`/` cuối) không phải khoá nên cũng bị từ chối: đầu vào là khoá object, không phải tiền tố.
    """
    with pytest.raises(ValueError, match=match):
        object_keys.upload_prefix_of(key)


def test_upload_prefix_of_rebuilds_with_upload_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-077: bộ tách hỏi đúng hàm dựng — đột biến `upload_prefix` thì `upload_prefix_of` đổi theo."""
    monkeypatch.setattr(object_keys, "upload_prefix", lambda *_: "khac/")
    with pytest.raises(ValueError, match=NOT_UNDER):
        object_keys.upload_prefix_of(f"{UPLOAD_PREFIX}pages/0.png")
