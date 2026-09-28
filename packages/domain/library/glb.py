"""Dựng tệp glTF 2.0 nhị phân (.glb) từ các khối hộp của một mục danh mục, chỉ thư viện chuẩn.

Bất biến: cùng `CatalogueItem` → cùng byte (JSON `sort_keys`, không thời gian, không ngẫu
nhiên) nên `sha256` là khoá so sánh cho lịch phát hành. Mỗi màu một primitive (một
material); mỗi khối 24 đỉnh để pháp tuyến không bị nội suy qua cạnh. Tam giác quay ngược
chiều kim đồng hồ nhìn từ ngoài (mặt trước theo glTF). Không Draco, không extension:
`GLTFLoader` của three.js đọc thẳng.
"""

import hashlib
import json
import struct
from dataclasses import dataclass

from packages.domain.library.catalogue import CatalogueItem, Part, part_bounds

_MM_PER_M = 1000.0
_JSON_CHUNK = 0x4E4F534A
_BIN_CHUNK = 0x004E4942
_FLOAT = 5126
_USHORT = 5123
_UINT = 5125
_ARRAY_BUFFER = 34962
_ELEMENT_ARRAY_BUFFER = 34963
_MAX_USHORT_VERTICES = 65535  # chỉ số 65535 là mốc restart, nên tối đa 65535 đỉnh (chỉ số 0..65534)

# Sáu mặt của hộp: (pháp tuyến, bốn góc (x, y, z) ∈ {0: min, 1: max}) theo chiều ngược kim đồng hồ
# nhìn từ ngoài. Hai tam giác của mặt là (0, 1, 2) và (0, 2, 3).
_FACES: tuple[tuple[tuple[int, int, int], tuple[tuple[int, int, int], ...]], ...] = (
    ((1, 0, 0), ((1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1))),
    ((-1, 0, 0), ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0))),
    ((0, 1, 0), ((0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0))),
    ((0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
    ((0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
    ((0, 0, -1), ((1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0))),
)
_QUAD_TRIANGLES = (0, 1, 2, 0, 2, 3)


@dataclass(frozen=True)
class GlbAsset:
    """Kết quả dựng: byte tệp, `sha256` hex thường 64 ký tự và các số đo lấy từ chính tệp."""

    data: bytes
    sha256: str
    size_bytes: int
    triangle_count: int
    width_mm: int
    depth_mm: int
    height_mm: int


def _f32(value: float) -> float:
    """Làm tròn về float32 để `min`/`max` trong JSON đúng như đỉnh thật trong BIN."""
    return float(struct.unpack("<f", struct.pack("<f", value))[0])


def _box_geometry(part: Part) -> tuple[list[float], list[float]]:
    """24 đỉnh (`POSITION`) và 24 pháp tuyến phẳng của một khối, đơn vị mét, phẳng x,y,z,x,y,z…"""
    lo = (part.x_mm, part.y_mm, part.z_mm)
    hi = (part.x_mm + part.width_mm, part.y_mm + part.height_mm, part.z_mm + part.depth_mm)
    positions: list[float] = []
    normals: list[float] = []
    for normal, corners in _FACES:
        for corner in corners:
            positions.extend((hi[a] if corner[a] else lo[a]) / _MM_PER_M for a in range(3))
            normals.extend(float(n) for n in normal)
    return positions, normals


def _quad_indices(box_count: int) -> list[int]:
    """Chỉ số 36 mỗi khối: mỗi mặt hai tam giác trên bốn đỉnh liên tiếp."""
    return [box * 24 + face * 4 + k for box in range(box_count) for face in range(6) for k in _QUAD_TRIANGLES]


def _group_by_colour(parts: tuple[Part, ...]) -> dict[tuple[int, int, int], list[Part]]:
    """Gom khối theo màu, giữ thứ tự xuất hiện đầu tiên để material ổn định giữa các lần dựng."""
    groups: dict[tuple[int, int, int], list[Part]] = {}
    for part in parts:
        groups.setdefault(part.rgb, []).append(part)
    return groups


class _Buffer:
    """BIN đang dựng cùng bufferView/accessor; mỗi khối dữ liệu bắt đầu ở offset chia hết 4."""

    def __init__(self) -> None:
        self.data = bytearray()
        self.views: list[dict[str, int]] = []
        self.accessors: list[dict[str, object]] = []

    def add(self, payload: bytes, target: int, accessor: dict[str, object]) -> int:
        """Thêm bufferView + accessor cho `payload`; trả chỉ số accessor. `byteLength` không tính đệm."""
        self.data += b"\x00" * (-len(self.data) % 4)
        self.views.append({"buffer": 0, "byteLength": len(payload), "byteOffset": len(self.data), "target": target})
        self.data += payload
        self.accessors.append({"bufferView": len(self.views) - 1, **accessor})
        return len(self.accessors) - 1


def _add_primitive(buf: _Buffer, parts: list[Part], material: int) -> dict[str, object]:
    """Ghi `POSITION`, `NORMAL`, chỉ số của một nhóm màu vào BIN; trả mô tả primitive."""
    positions: list[float] = []
    normals: list[float] = []
    for part in parts:
        pos, nrm = _box_geometry(part)
        positions += pos
        normals += nrm
    rounded = [_f32(v) for v in positions]
    vertex_count = len(rounded) // 3
    axes = [rounded[a::3] for a in range(3)]
    pos_acc = buf.add(
        struct.pack(f"<{len(rounded)}f", *rounded),
        _ARRAY_BUFFER,
        {
            "componentType": _FLOAT,
            "count": vertex_count,
            "max": [max(v) for v in axes],
            "min": [min(v) for v in axes],
            "type": "VEC3",
        },
    )
    nrm_acc = buf.add(
        struct.pack(f"<{len(normals)}f", *normals),
        _ARRAY_BUFFER,
        {"componentType": _FLOAT, "count": vertex_count, "type": "VEC3"},
    )
    indices = _quad_indices(len(parts))
    wide = vertex_count > _MAX_USHORT_VERTICES
    idx_acc = buf.add(
        struct.pack(f"<{len(indices)}{'I' if wide else 'H'}", *indices),
        _ELEMENT_ARRAY_BUFFER,
        {"componentType": _UINT if wide else _USHORT, "count": len(indices), "type": "SCALAR"},
    )
    return {"attributes": {"NORMAL": nrm_acc, "POSITION": pos_acc}, "indices": idx_acc, "material": material, "mode": 4}


def _material(rgb: tuple[int, int, int]) -> dict[str, object]:
    """Vật liệu PBR không kim loại, nhám 0.8; hệ số nằm trong `pbrMetallicRoughness` (đặc tả glTF)."""
    r, g, b = rgb
    return {
        "pbrMetallicRoughness": {
            "baseColorFactor": [r / 255, g / 255, b / 255, 1.0],
            "metallicFactor": 0,
            "roughnessFactor": 0.8,
        }
    }


def _chunk(kind: int, payload: bytes, pad: bytes) -> bytes:
    """Chunk GLB: độ dài + loại + dữ liệu đệm cho chia hết 4 (JSON đệm 0x20, BIN đệm 0x00)."""
    payload += pad * (-len(payload) % 4)
    return struct.pack("<II", len(payload), kind) + payload


def build_glb(item: CatalogueItem) -> GlbAsset:
    """Dựng `.glb` của `item`; số đo (hộp bao, tam giác) lấy từ khối, không chép từ bảng.

    Ném `ValueError` khi mục không có khối. Primitive vượt 65 535 đỉnh dùng chỉ số
    `UNSIGNED_INT` thay `UNSIGNED_SHORT`.
    """
    (min_x, min_y, min_z), (max_x, max_y, max_z) = part_bounds(item)
    buf = _Buffer()
    groups = _group_by_colour(item.parts)
    primitives = [_add_primitive(buf, parts, index) for index, parts in enumerate(groups.values())]
    document = {
        "accessors": buf.accessors,
        "asset": {"generator": "appback", "version": "2.0"},
        "bufferViews": buf.views,
        "buffers": [{"byteLength": len(buf.data) + (-len(buf.data) % 4)}],
        "materials": [_material(rgb) for rgb in groups],
        "meshes": [{"primitives": primitives}],
        "nodes": [{"mesh": 0}],
        "scene": 0,
        "scenes": [{"nodes": [0]}],
    }
    json_bytes = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    body = _chunk(_JSON_CHUNK, json_bytes, b" ") + _chunk(_BIN_CHUNK, bytes(buf.data), b"\x00")
    data = struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body
    return GlbAsset(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        triangle_count=12 * len(item.parts),
        width_mm=max_x - min_x,
        depth_mm=max_z - min_z,
        height_mm=max_y - min_y,
    )
