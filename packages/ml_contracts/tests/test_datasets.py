"""Bố cục dataset: đường mẫu, manifest (trần, thứ tự, đường lạ), chia theo nhóm (M06)."""

import hashlib
from collections import Counter

import pytest
from pydantic import ValidationError

from packages.ml_contracts import datasets
from packages.ml_contracts.datasets import (
    ManifestEntry,
    SampleMeta,
    build_manifest,
    manifest_sha256,
    parse_manifest,
    sample_path,
    split_for,
)

SHA = "b" * 64


def entry(path: str, size: int = 10) -> ManifestEntry:
    return ManifestEntry(path=path, sha256=SHA, bytes=size)


def test_sample_path_rules() -> None:
    assert sample_path("train", "prj_1-a", "walls.png") == "train/prj_1-a/walls.png"
    assert sample_path("test", "A" * 128, "meta.json").endswith("/meta.json")
    for split, sample_id, name in (
        ("dev", "a", "image.png"),
        ("train", "_a", "image.png"),
        ("train", "a" * 129, "image.png"),
        ("train", "a/b", "image.png"),
        ("train", "a", "other.png"),
    ):
        with pytest.raises(ValueError, match=r"lạ|sai mẫu"):
            sample_path(split, sample_id, name)  # type: ignore[arg-type]  # split chuỗi tuỳ ý


def test_sample_meta_rules() -> None:
    SampleMeta(sample_id="a", group_key="cubicasa:1", width_px=10, height_px=10, mm_per_px=None, source="synthetic")
    SampleMeta(sample_id="a", group_key="g", width_px=8000, height_px=5000, mm_per_px=8.0, source="cubicasa5k")
    for changes in (
        {"width_px": 8001, "height_px": 5000},
        {"mm_per_px": 0.0},
        {"mm_per_px": float("inf")},
        {"source": "web"},
        {"group_key": ""},
        {"sample_id": "-a"},
    ):
        base: dict[str, object] = {"sample_id": "a", "group_key": "g", "width_px": 1, "height_px": 1}
        fields = base | {"mm_per_px": None, "source": "approvedFloors"} | changes
        with pytest.raises(ValidationError):
            SampleMeta(**fields)


def test_manifest_roundtrip_is_sorted_and_compact() -> None:
    entries = [entry("validation/b/meta.json"), entry("train/a/image.png", 0)]
    data = build_manifest(entries)
    assert data.splitlines()[0] == b'{"bytes":0,"path":"train/a/image.png","sha256":"' + SHA.encode() + b'"}'
    assert [item.path for item in parse_manifest(data)] == ["train/a/image.png", "validation/b/meta.json"]
    assert manifest_sha256(data) == hashlib.sha256(data).hexdigest()
    assert parse_manifest(b"") == ()


@pytest.mark.parametrize(
    ("data", "match"),
    [
        (b'{"path":"train/a/image.png","sha256":"' + SHA.encode() + b'","bytes":1}', "xuống dòng"),
        (b"{}\n", "schema"),
        (b'{"path":"../x","sha256":"' + SHA.encode() + b'","bytes":1}\n', "đường lạ"),
        (b'{"path":"train/a/x.bin","sha256":"' + SHA.encode() + b'","bytes":1}\n', "đường lạ"),
        (b'{"path":"train/a/b/image.png","sha256":"' + SHA.encode() + b'","bytes":1}\n', "đường lạ"),
    ],
)
def test_parse_manifest_rejects(data: bytes, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse_manifest(data)


def test_parse_manifest_rejects_duplicates_and_order() -> None:
    first = entry("train/a/image.png").model_dump_json().encode() + b"\n"
    second = entry("train/b/image.png").model_dump_json().encode() + b"\n"
    with pytest.raises(ValueError, match="thứ tự"):
        parse_manifest(first + first)
    with pytest.raises(ValueError, match="thứ tự"):
        parse_manifest(second + first)
    with pytest.raises(ValueError, match="thứ tự"):
        build_manifest([entry("train/a/image.png"), entry("train/a/image.png")])


def test_parse_manifest_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [entry(f"train/s{index:03d}/image.png", 5).model_dump_json().encode() + b"\n" for index in range(4)]
    monkeypatch.setattr(datasets, "MANIFEST_MAX_LINES", 3)
    with pytest.raises(ValueError, match="dòng"):
        parse_manifest(b"".join(lines))
    monkeypatch.setattr(datasets, "MANIFEST_MAX_LINES", 10)
    monkeypatch.setattr(datasets, "DATASET_MAX_BYTES", 19)
    with pytest.raises(ValueError, match="tổng byte"):
        parse_manifest(b"".join(lines))
    monkeypatch.setattr(datasets, "DATASET_MAX_BYTES", 20)
    assert len(parse_manifest(b"".join(lines))) == 4


def test_split_for_m06() -> None:
    """Tất định theo **nhóm**, gần 80/10/10 trên nhiều nhóm; mọi mẫu một nhóm chung một tập."""
    assert split_for("cubicasa:42") == split_for("cubicasa:42")
    counts = Counter(split_for(f"prj_{index}") for index in range(10_000))
    assert 7_800 <= counts["train"] <= 8_200
    assert 900 <= counts["validation"] <= 1_100
    assert 900 <= counts["test"] <= 1_100
    assert {split_for("prj_X") for _page in range(5)} == {split_for("prj_X")}
    with pytest.raises(ValueError, match="rỗng"):
        split_for("")
