from collections.abc import Callable

import pytest

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


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "a/../b",
        "../secret",
        "a/./b",
        "a\x00b",
        "a\x7fb",
        "a//b",
        "/a",
        "a\\b",
        "x.meta.json",
        "a" * 1025,
        "tệp.png",
    ],
)
def test_check_key_rejects_unsafe(bad: str) -> None:
    with pytest.raises(ValueError, match=r"khoá|đoạn"):
        keys.check_key(bad)


@pytest.mark.parametrize("good", ["a", "projects/prj_A/x.png", "a" * 1024])
def test_check_key_accepts_safe(good: str) -> None:
    assert keys.check_key(good) == good


@pytest.mark.parametrize("bad", ["projects/prj_A", "", "projects/prj_A//"])
def test_check_prefix_requires_trailing_slash(bad: str) -> None:
    with pytest.raises(ValueError, match=r"tiền tố|khoá|đoạn"):
        keys.check_prefix(bad)


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
    ],
)
def test_server_chosen_kind_only_for_keys_the_server_names(key: str, expected: str | None) -> None:
    """NO-011: ảnh đại diện và ảnh trang do server đặt đuôi sau khi đã kiểm magic bytes; `original.*` thì không."""
    assert keys.server_chosen_kind(key) == expected
