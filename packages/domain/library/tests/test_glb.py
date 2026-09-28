"""`build_glb`: bộ đọc GLB tự viết bằng thư viện chuẩn kiểm cấu trúc, hình học và tính tất định."""

import hashlib
import json
import math
import struct
from typing import Any

import pytest

from packages.domain.library import CATALOGUE, CatalogueItem, GlbAsset, Part, build_glb

# Bảng [5] chép tay, không đọc từ CATALOGUE: id -> (W, D, H) mm.
EXPECTED_BOX = {
    "table-dining-6": (1800, 900, 750),
    "table-desk": (1400, 700, 750),
    "chair-dining": (450, 520, 880),
    "chair-stool": (400, 400, 450),
    "bed-double-1600": (1600, 2000, 450),
    "bed-single-1000": (1000, 2000, 450),
    "sofa-three-seat": (2100, 900, 850),
    "sofa-armchair": (850, 850, 850),
    "storage-wardrobe": (1000, 600, 2000),
    "storage-bookshelf": (800, 300, 1800),
    "sanitary-toilet": (400, 700, 780),
    "sanitary-basin": (600, 450, 850),
    "kitchen-base-cabinet": (1200, 600, 850),
    "kitchen-fridge": (700, 700, 1800),
    "technical-panel": (600, 250, 800),
    "technical-water-purifier": (300, 400, 1000),
}
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
FLOAT, USHORT, UINT = 5126, 5123, 5125
ITEMS = pytest.mark.parametrize("item", CATALOGUE, ids=lambda i: i.id)


def read_chunks(data: bytes) -> list[tuple[int, bytes]]:
    """Đọc header 12 byte rồi các chunk; kiểm độ dài tổng và chia hết 4 ngay khi đọc."""
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert (magic, version, length) == (b"glTF", 2, len(data))
    chunks, offset = [], 12
    while offset < len(data):
        chunk_len, kind = struct.unpack_from("<II", data, offset)
        assert chunk_len % 4 == 0
        chunks.append((kind, data[offset + 8 : offset + 8 + chunk_len]))
        offset += 8 + chunk_len
    assert offset == len(data)
    return chunks


def read_glb(data: bytes) -> tuple[dict[str, Any], bytes]:
    """Trả `(json, bin)`; đúng hai chunk theo thứ tự JSON rồi BIN."""
    chunks = read_chunks(data)
    assert [k for k, _ in chunks] == [JSON_CHUNK, BIN_CHUNK]
    return json.loads(chunks[0][1]), chunks[1][1]


def read_accessor(doc: dict[str, Any], blob: bytes, index: int) -> list[Any]:
    """Giải accessor thành danh sách bộ ba float hoặc số nguyên, kiểm nằm trong BIN và căn hàng."""
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    assert view["byteOffset"] + view["byteLength"] <= len(blob)
    if acc["componentType"] == FLOAT:
        assert view["byteOffset"] % 4 == 0
        assert view["byteLength"] == acc["count"] * 12
        flat = struct.unpack_from(f"<{acc['count'] * 3}f", blob, view["byteOffset"])
        return [flat[i : i + 3] for i in range(0, len(flat), 3)]
    fmt = "H" if acc["componentType"] == USHORT else "I"
    assert view["byteLength"] == acc["count"] * struct.calcsize(fmt)
    return list(struct.unpack_from(f"<{acc['count']}{fmt}", blob, view["byteOffset"]))


def sub(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    """Hiệu hai vectơ."""
    return tuple(x - y for x, y in zip(a, b, strict=True))


def cross(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    """Tích có hướng ba chiều."""
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def all_positions(doc: dict[str, Any], blob: bytes) -> list[tuple[float, ...]]:
    """Mọi đỉnh `POSITION` của mọi primitive."""
    return [
        v for prim in doc["meshes"][0]["primitives"] for v in read_accessor(doc, blob, prim["attributes"]["POSITION"])
    ]


@ITEMS
def test_glb_container_layout(item: CatalogueItem) -> None:
    """Header, tổng độ dài, chunk chia hết 4, JSON đệm 0x20, BIN đệm 0x00."""
    asset = build_glb(item)
    chunks = read_chunks(asset.data)
    json_payload, bin_payload = chunks[0][1], chunks[1][1]
    assert json_payload.rstrip(b" ").endswith(b"}")
    assert json.loads(json_payload)["buffers"][0]["byteLength"] <= len(bin_payload)
    assert len(bin_payload) - json.loads(json_payload)["buffers"][0]["byteLength"] < 4
    assert asset.size_bytes == len(asset.data)


@ITEMS
def test_glb_json_top_level(item: CatalogueItem) -> None:
    """`asset`, `scene`, `scenes`, `nodes`, material trong `pbrMetallicRoughness`, không extension."""
    doc, _ = read_glb(build_glb(item).data)
    assert doc["asset"] == {"generator": "appback", "version": "2.0"}
    assert doc["scene"] == 0
    assert doc["scenes"] == [{"nodes": [0]}]
    assert doc["nodes"] == [{"mesh": 0}]
    assert "extensionsUsed" not in doc
    assert "extensionsRequired" not in doc
    for material in doc["materials"]:
        assert set(material) == {"pbrMetallicRoughness"}
        pbr = material["pbrMetallicRoughness"]
        assert pbr["metallicFactor"] == 0
        assert pbr["roughnessFactor"] == 0.8
        assert len(pbr["baseColorFactor"]) == 4
        assert pbr["baseColorFactor"][3] == 1.0
        assert all(0 <= c <= 1 for c in pbr["baseColorFactor"])


@ITEMS
def test_glb_one_primitive_per_colour(item: CatalogueItem) -> None:
    """Mỗi màu một primitive, một material; hệ số đúng `rgb/255`."""
    doc, _ = read_glb(build_glb(item).data)
    colours = list(dict.fromkeys(p.rgb for p in item.parts))
    assert 2 <= len(colours) <= 4
    assert len(doc["meshes"][0]["primitives"]) == len(colours)
    assert [m["pbrMetallicRoughness"]["baseColorFactor"] for m in doc["materials"]] == [
        [r / 255, g / 255, b / 255, 1.0] for r, g, b in colours
    ]
    assert [p["material"] for p in doc["meshes"][0]["primitives"]] == list(range(len(colours)))


@ITEMS
def test_glb_buffers_targets_and_alignment(item: CatalogueItem) -> None:
    """Mọi bufferView có `target` đúng loại; offset `FLOAT` chia hết 4; view nằm trong BIN."""
    doc, blob = read_glb(build_glb(item).data)
    for acc in doc["accessors"]:
        view = doc["bufferViews"][acc["bufferView"]]
        assert view["buffer"] == 0
        assert view["target"] == (34962 if acc["componentType"] == FLOAT else 34963)
        assert view["byteOffset"] + view["byteLength"] <= len(blob)
        if acc["componentType"] == FLOAT:
            assert view["byteOffset"] % 4 == 0
    for prim in doc["meshes"][0]["primitives"]:
        assert doc["accessors"][prim["indices"]]["componentType"] == USHORT


@ITEMS
def test_glb_indices_min_max_and_winding(item: CatalogueItem) -> None:
    """Chỉ số < số đỉnh; `min`/`max` khớp đỉnh float32 thật; tam giác CCW theo pháp tuyến."""
    doc, blob = read_glb(build_glb(item).data)
    for prim in doc["meshes"][0]["primitives"]:
        pos_acc = doc["accessors"][prim["attributes"]["POSITION"]]
        positions = read_accessor(doc, blob, prim["attributes"]["POSITION"])
        normals = read_accessor(doc, blob, prim["attributes"]["NORMAL"])
        indices = read_accessor(doc, blob, prim["indices"])
        assert len(positions) == len(normals) == pos_acc["count"]
        assert max(indices) < len(positions)
        assert pos_acc["min"] == [min(v[a] for v in positions) for a in range(3)]
        assert pos_acc["max"] == [max(v[a] for v in positions) for a in range(3)]
        assert len(indices) % 36 == 0
        for i in range(0, len(indices), 3):
            a, b, c = (positions[j] for j in indices[i : i + 3])
            n = cross(sub(b, a), sub(c, a))
            length = math.sqrt(sum(x * x for x in n))
            unit = tuple(x / length for x in n)
            assert unit == pytest.approx(normals[indices[i]], abs=1e-6)


@ITEMS
def test_glb_bounding_box_matches_table(item: CatalogueItem) -> None:
    """Hộp bao từ đỉnh thật = bảng [5], đối xứng X/Z quanh 0, đáy Y = 0; số đo GlbAsset khớp."""
    asset = build_glb(item)
    doc, blob = read_glb(asset.data)
    width, depth, height = EXPECTED_BOX[item.id]
    pts = all_positions(doc, blob)
    lo = [min(p[a] for p in pts) * 1000 for a in range(3)]
    hi = [max(p[a] for p in pts) * 1000 for a in range(3)]
    assert (hi[0] - lo[0], hi[2] - lo[2], hi[1] - lo[1]) == pytest.approx((width, depth, height), abs=1e-3)
    assert lo[0] == pytest.approx(-width / 2, abs=1e-3)
    assert hi[0] == pytest.approx(width / 2, abs=1e-3)
    assert lo[2] == pytest.approx(-depth / 2, abs=1e-3)
    assert hi[2] == pytest.approx(depth / 2, abs=1e-3)
    assert lo[1] == 0
    assert (asset.width_mm, asset.depth_mm, asset.height_mm) == (width, depth, height)


@ITEMS
def test_glb_triangle_count_and_digest(item: CatalogueItem) -> None:
    """`triangle_count` = tổng chỉ số / 3; `sha256` là hex thường 64 ký tự của đúng byte tệp."""
    asset = build_glb(item)
    doc, _ = read_glb(asset.data)
    total = sum(doc["accessors"][p["indices"]]["count"] for p in doc["meshes"][0]["primitives"])
    assert asset.triangle_count == total // 3 == 12 * len(item.parts)
    assert asset.sha256 == hashlib.sha256(asset.data).hexdigest()
    assert len(asset.sha256) == 64
    assert asset.sha256 == asset.sha256.lower()


@ITEMS
def test_glb_is_deterministic(item: CatalogueItem) -> None:
    """Dựng hai lần cho cùng byte và cùng sha256 (lịch phát hành so sha để bỏ qua)."""
    assert build_glb(item) == build_glb(item)


def test_glb_distinct_items_distinct_digest() -> None:
    """16 mục cho 16 sha khác nhau: sha đủ phân biệt mục."""
    assert len({build_glb(i).sha256 for i in CATALOGUE}) == len(CATALOGUE)


def synthetic(box_count: int) -> CatalogueItem:
    """Mục tổng hợp một màu, các khối xếp dọc trục X để hộp bao dễ tính."""
    parts = tuple(Part(i * 10, 0, 0, 10, 10, 10, (1, 2, 3)) for i in range(box_count))
    return CatalogueItem("synthetic", "tổng hợp", "table", parts)


def test_glb_ushort_up_to_65535_vertices() -> None:
    """2730 khối = 65 520 đỉnh ≤ 65 535 vẫn `UNSIGNED_SHORT`."""
    doc, blob = read_glb(build_glb(synthetic(2730)).data)
    prim = doc["meshes"][0]["primitives"][0]
    assert doc["accessors"][prim["attributes"]["POSITION"]]["count"] == 65520
    assert doc["accessors"][prim["indices"]]["componentType"] == USHORT
    assert max(read_accessor(doc, blob, prim["indices"])) == 65519


def test_glb_uint_beyond_65535_vertices() -> None:
    """2731 khối = 65 544 đỉnh → chỉ số `UNSIGNED_INT`, đọc lại đủ và trỏ tới đỉnh cuối."""
    asset = build_glb(synthetic(2731))
    doc, blob = read_glb(asset.data)
    prim = doc["meshes"][0]["primitives"][0]
    index_acc = doc["accessors"][prim["indices"]]
    assert doc["accessors"][prim["attributes"]["POSITION"]]["count"] == 65544
    assert index_acc["componentType"] == UINT
    assert index_acc["count"] == 36 * 2731
    indices = read_accessor(doc, blob, prim["indices"])
    assert max(indices) == 65543
    assert doc["bufferViews"][index_acc["bufferView"]]["byteOffset"] % 4 == 0
    assert asset.triangle_count == 12 * 2731
    assert asset.width_mm == 2731 * 10


def test_glb_rejects_item_without_parts() -> None:
    """Mục không khối không có hộp bao → `ValueError`, không ghi tệp rỗng."""
    with pytest.raises(ValueError, match="không có khối"):
        build_glb(CatalogueItem("empty", "rỗng", "table", ()))


def test_glb_returns_frozen_asset() -> None:
    """`GlbAsset` bất biến để kết quả dựng dùng lại an toàn giữa các lượt lịch."""
    asset = build_glb(CATALOGUE[0])
    assert isinstance(asset, GlbAsset)
    with pytest.raises(AttributeError):
        asset.sha256 = "x"  # type: ignore[misc]
