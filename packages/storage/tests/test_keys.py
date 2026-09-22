from collections.abc import Callable

import pytest

from packages.core import object_keys
from packages.storage import keys

PROJECT = "prj_01ARZ3NDEKTSV4RRFFQ69G5FAV"
FLOOR = "L-ABCDEFGHIJ"
UPLOAD = "upl_01ARZ3NDEKTSV4RRFFQ69G5FBW"
RUN = "run_01ARZ3NDEKTSV4RRFFQ69G5FCX"
USER = "usr_01ARZ3NDEKTSV4RRFFQ69G5FDY"
ULID = "01ARZ3NDEKTSV4RRFFQ69G5FEZ"
MODEL = "mdl_01ARZ3NDEKTSV4RRFFQ69G5FGA"
DATASET_VERSION = "dsv_01ARZ3NDEKTSV4RRFFQ69G5FHB"


def test_keys_follow_charter_layout() -> None:
    upload = f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}"
    assert keys.upload_original(PROJECT, FLOOR, UPLOAD, "png") == f"{upload}/original.png"
    assert keys.upload_page(PROJECT, FLOOR, UPLOAD, 0) == f"{upload}/pages/0.png"
    assert keys.run_artifact(PROJECT, FLOOR, UPLOAD, RUN, "preprocess", "mask.png") == (
        f"{upload}/runs/{RUN}/preprocess/mask.png"
    )
    assert keys.library_object("sofa-2-cho", "preview.png") == "library/sofa-2-cho/preview.png"
    assert keys.model_artifact(MODEL, "weights.safetensors") == f"ml/models/{MODEL}/weights.safetensors"
    assert keys.dataset_object(DATASET_VERSION, "manifest.json") == f"ml/datasets/{DATASET_VERSION}/manifest.json"
    assert keys.avatar(USER, ULID, "png") == f"users/{USER}/avatar/{ULID}.png"


def test_prefixes_end_with_slash() -> None:
    assert keys.project_prefix(PROJECT) == f"projects/{PROJECT}/"
    assert keys.upload_prefix(PROJECT, FLOOR, UPLOAD) == f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/"


def test_key_rules_come_from_core() -> None:
    """NO-060: `storage` dùng đúng luật khoá của `packages.core.object_keys`, không giữ bản riêng.

    Mẫu biên của luật nằm ở `packages/core/tests/test_object_keys.py`.
    """
    assert keys.check_key is object_keys.check_key
    assert keys.check_prefix is object_keys.check_prefix


@pytest.mark.parametrize(
    ("build", "match"),
    [
        (lambda: keys.project_prefix("prj_lowercase"), "prj_"),
        (lambda: keys.upload_prefix(PROJECT, "W-ABCDEFGHIJ", UPLOAD), "id tầng"),
        (lambda: keys.upload_prefix(PROJECT, FLOOR, PROJECT), "upl_"),
        (lambda: keys.upload_original(PROJECT, FLOOR, UPLOAD, "PNG"), "đuôi tệp"),
        (lambda: keys.upload_original(PROJECT, FLOOR, UPLOAD, "a" * 9), "đuôi tệp"),
        (lambda: keys.upload_page(PROJECT, FLOOR, UPLOAD, -1), "số trang"),
        (lambda: keys.run_artifact(PROJECT, FLOOR, UPLOAD, RUN, "sniff", "x.png"), "bước pipeline"),
        (lambda: keys.run_artifact(PROJECT, FLOOR, UPLOAD, UPLOAD, "preprocess", "x.png"), "run_"),
        (lambda: keys.run_artifact(PROJECT, FLOOR, UPLOAD, RUN, "preprocess", "a/b.png"), "tên object"),
        (lambda: keys.run_artifact(PROJECT, FLOOR, UPLOAD, RUN, "preprocess", ".."), "tên object"),
        (lambda: keys.library_object("Sofa", "x.png"), "id thư viện"),
        (lambda: keys.library_object("a" * 65, "x.png"), "id thư viện"),
        (lambda: keys.model_artifact(DATASET_VERSION, "w.bin"), "mdl_"),
        (lambda: keys.dataset_object(MODEL, "w.bin"), "dsv_"),
        (lambda: keys.avatar(USER, "khong-phai-ulid", "png"), "ULID"),
        (lambda: keys.avatar(USER, ULID, "gif"), "ảnh đại diện"),
    ],
)
def test_builders_reject_wrong_ids(build: Callable[[], str], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        build()


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (f"users/{USER}/avatar/{ULID}.png", "png"),
        (f"users/{USER}/avatar/{ULID}.jpg", "jpeg"),
        (f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/pages/0.png", "png"),
        (f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/pages/12.png", "png"),
        (f"users/{USER}/avatar/{ULID}.pdf", None),
        (f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/original.png", None),
        (f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/pages/0.jpg", None),
        (f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/pages/sub/0.png", None),
        (f"users/{USER}/avatar/sub/{ULID}.png", None),
        (f"users/{USER}/avatar/{ULID}", None),
        (f"users/{USER}/avatar/{ULID}.png.png", None),
        (f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/pages/0", None),
        (f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/pages/007.png", None),
        (f"projects/prj_lowercase/floors/{FLOOR}/uploads/{UPLOAD}/pages/0.png", None),
        ("library/sofa/preview.png", None),
    ],
)
def test_server_chosen_kind_only_for_keys_the_server_names(key: str, expected: str | None) -> None:
    """NO-011: ảnh đại diện và ảnh trang do server đặt đuôi sau khi đã kiểm magic bytes; `original.*` thì không."""
    assert keys.server_chosen_kind(key) == expected


@pytest.mark.parametrize(
    ("floor", "expected"),
    [("L-" + "A" * 10, "png"), ("L-" + "Z9" * 32, "png"), ("L-" + "A" * 9, None), ("L-" + "A" * 65, None)],
)
def test_server_chosen_kind_follows_level_id_length(floor: str, expected: str | None) -> None:
    """NO-073: id tầng dài 10 và 64 là khoá trang do server đặt; 9 và 65 thì không (biên `is_spatial_id`)."""
    page = f"projects/{PROJECT}/floors/{floor}/uploads/{UPLOAD}/pages/0.png"
    assert keys.server_chosen_kind(page) == expected


@pytest.mark.parametrize(
    ("rule", "key"),
    [
        ("is_spatial_id", f"projects/{PROJECT}/floors/{FLOOR}/uploads/{UPLOAD}/pages/0.png"),
        ("is_id", f"users/{USER}/avatar/{ULID}.png"),
    ],
)
def test_server_chosen_kind_reads_id_rules_of_core(monkeypatch: pytest.MonkeyPatch, rule: str, key: str) -> None:
    """NO-073: đột biến luật id mà hàm dựng khoá dùng thì khoá đó thôi là khoá server đặt.

    Chốt một nguồn: `server_chosen_kind` hỏi đúng `is_id`/`is_spatial_id` của `packages.core.ids`
    như hàm dựng, không hỏi regex chép tay.
    """
    assert keys.server_chosen_kind(key) is not None
    monkeypatch.setattr(keys, rule, lambda *_: False)
    assert keys.server_chosen_kind(key) is None
