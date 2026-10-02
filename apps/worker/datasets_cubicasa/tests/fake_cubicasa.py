"""Bộ CubiCasa5K giả cho test (B6-02b [8]): SVG viết tay, PNG bằng `encode_rgb_png`, kèm helper lượt nhập.

Bốn file test đều dựng dataset, chạy `import_cubicasa` rồi đọc manifest/khoá kho, nên các bước đó
sống ở đây một bản (`new_dataset`, `run_import`, `read_object`, `version_keys`, `read_manifest`) —
R-07: cùng một việc không viết hai lần ở hai file test.

"Phòng chuẩn" theo pixel ảnh (luật toạ độ phương án 1: toạ độ SVG = pixel `F1_scaled.png` 1:1):
bốn tường dày `WALL_PX`, một cửa nằm trong tường dưới (khe cửa), một cửa sổ trong tường trên, một
`Toilet` (nhóm `BoundaryPolygon` dời bằng `matrix`) và một `BaseCabinet` (tên đồ lạ, chỉ có `rect`).
Cấu trúc nhóm chép theo `model.svg` thật: `<g class="Wall">` chứa đa giác tường rồi nhóm
`Door`/`Window` lồng bên trong; nhóm con `PanelArea`/`Glass` của cửa **không** phải đa giác cửa
(`PanelArea` cố ý tràn vào phòng để bộ đọc lấy nhầm thì hộp cửa sai thấy ngay).
"""

import io
import struct
import zipfile
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.worker.datasets.tasks import WALL_FAMILY, version_prefix
from apps.worker.datasets_cubicasa.importer import ImportReport, import_cubicasa
from apps.worker.datasets_cubicasa.settings import CubiCasaSettings
from apps.worker.datasets_cubicasa.svg import Point, Polygon
from packages.core.clock import Clock
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.ml_contracts.artifacts import encode_rgb_png
from packages.ml_contracts.datasets import MANIFEST_NAME, ManifestEntry, parse_manifest
from packages.storage.port import ObjectStorage
from packages.testing.factories.admin_ml_datasets import make_dataset

WALL_PX: Final = 8
SUBSETS: Final = ("high_quality", "high_quality_architectural", "colorful")
ZIP_DATE: Final = (2020, 1, 1, 0, 0, 0)
PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
ORIGIN: Final[Point] = (0.0, 0.0)


def rect(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    """Hình chữ nhật thẳng trục theo chiều kim đồng hồ, như đa giác tường của CubiCasa."""
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def bounds(polygon: Polygon) -> tuple[int, int, int, int]:
    """`(x0, y0, x1, y1)` nguyên của hộp bao một đa giác (đáp án hộp của test)."""
    xs = [x for x, _ in polygon]
    ys = [y for _, y in polygon]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


@dataclass(frozen=True, slots=True)
class Room:
    """Nhãn chuẩn của một mẫu theo pixel ảnh `width x height` — đáp án để test so."""

    width: int
    height: int
    walls: tuple[Polygon, ...]
    doors: tuple[Polygon, ...]
    windows: tuple[Polygon, ...]
    fixtures: tuple[tuple[str, Polygon], ...]


def room(width: int = 320, height: int = 240) -> Room:
    """Phòng chuẩn co theo khổ ảnh: lề 1/16, tường `WALL_PX`, toạ độ nguyên để đáp án pixel chính xác.

    Cửa nằm giữa tường dưới (`walls[1]`), cửa sổ ở tường trên (`walls[0]`); `Toilet` có tên trong
    bảng đồ, `BaseCabinet` thì không (đếm vào tên đồ lạ).
    """
    x0, y0, x1, y1 = width // 16, height // 16, width - width // 16, height - height // 16
    w = WALL_PX
    cx, half_door = width // 2, width // 16
    walls = (rect(x0, y0, x1, y0 + w), rect(x0, y1 - w, x1, y1), rect(x0, y0, x0 + w, y1), rect(x1 - w, y0, x1, y1))
    door = rect(cx - half_door, y1 - w, cx + half_door, y1)
    window = rect(x0 + width // 8, y0, x0 + width // 4, y0 + w)
    toilet = rect(x0 + 3 * w, y0 + 3 * w, x0 + 3 * w + width // 10, y0 + 3 * w + height // 6)
    cabinet = rect(x1 - 3 * w - width // 5, y0 + 3 * w, x1 - 3 * w, y0 + 3 * w + height // 12)
    return Room(width, height, walls, (door,), (window,), (("Toilet", toilet), ("BaseCabinet", cabinet)))


def _points(polygon: Polygon, origin: Point) -> str:
    """Thuộc tính `points` kiểu CubiCasa (`x,y x,y …`), dời theo `origin`."""
    return " ".join(f"{x + origin[0]:g},{y + origin[1]:g}" for x, y in polygon)


def _door_group(door: Polygon, origin: Point) -> str:
    """Nhóm `Door` thật: đa giác ô cửa là con trực tiếp; `PanelArea` (vùng cánh mở) tràn vào phòng."""
    x0, y0, x1, _ = bounds(door)
    swing = rect(x0, y0 - (x1 - x0), x1, y0)
    return (
        f'<g class="Door Swing Beside"><polygon points="{_points(door, origin)}"/>'
        f'<g class="PanelArea"><polygon points="{_points(swing, origin)}"/></g></g>'
    )


def _window_group(window: Polygon, origin: Point) -> str:
    """Nhóm `Window` thật: đa giác ô cửa sổ, nhóm con `Glass` trùng hình, `Panel` chỉ có `line`."""
    x0, y0, x1, y1 = (v + origin[i % 2] for i, v in enumerate(bounds(window)))
    return (
        f'<g class="Window Regular"><polygon points="{_points(window, origin)}"/>'
        f'<g class="Glass"><polygon points="{_points(window, origin)}"/></g>'
        f'<g class="Panel"><line x1="{x0:g}" x2="{x1:g}" y1="{(y0 + y1) / 2:g}" y2="{(y0 + y1) / 2:g}"/></g></g>'
    )


def _fixture_group(name: str, box: Polygon, origin: Point, *, boundary: bool) -> str:
    """Nhóm `FixedFurniture <tên>`: `boundary` → `matrix` + `BoundaryPolygon` toạ độ cục bộ, kèm
    `InnerPolygon` nhỏ hơn; không thì một `rect` toạ độ tuyệt đối (như tủ bếp thật)."""
    x0, y0, x1, y1 = bounds(box)
    if not boundary:
        return (
            f'<g class="FixedFurniture {name}"><rect x="{x0 + origin[0]:g}" y="{y0 + origin[1]:g}" '
            f'width="{x1 - x0}" height="{y1 - y0}"/></g>'
        )
    local = rect(0, 0, x1 - x0, y1 - y0)
    inner = rect(2, 2, x1 - x0 - 2, (y1 - y0) // 2)
    return (
        f'<g class="FixedFurniture {name}" transform="matrix(1,0,0,1,{x0 + origin[0]:g},{y0 + origin[1]:g})">'
        f'<g class="BoundaryPolygon"><polygon points="{_points(local, ORIGIN)}"/></g>'
        f'<g class="InnerPolygon"><polygon points="{_points(inner, ORIGIN)}"/></g></g>'
    )


def room_svg(spec: Room, *, origin: Point = ORIGIN) -> bytes:
    """`model.svg` của phòng; `origin` dời mọi toạ độ **và** gốc `viewBox` cùng một lượng (đáp án không đổi).

    Có thêm nhóm `Space` phủ cả phòng và `Railing` — bộ đọc phải bỏ qua cả hai.
    """
    first, second, *rest = spec.walls
    walls = [
        f'<g class="Wall"><polygon points="{_points(first, origin)}"/>'
        + "".join(_window_group(window, origin) for window in spec.windows)
        + "</g>",
        f'<g class="Wall External"><polygon points="{_points(second, origin)}"/>'
        + "".join(_door_group(door, origin) for door in spec.doors)
        + "</g>",
        *(f'<g class="Wall"><polygon points="{_points(wall, origin)}"/></g>' for wall in rest),
    ]
    fixtures = [
        _fixture_group(name, box, origin, boundary=index == 0) for index, (name, box) in enumerate(spec.fixtures)
    ]
    space = rect(0, 0, spec.width, spec.height)
    body = (
        f'<g class="Space Kitchen"><polygon points="{_points(space, origin)}"/></g>'
        f'<g class="Railing"><polygon points="{_points(rect(0, 0, 4, 4), origin)}"/></g>'
        + "".join(walls)
        + "".join(fixtures)
    )
    ox, oy = origin
    return (
        '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'version="1.1" width="{spec.width}" height="{spec.height}" viewBox="{ox:g} {oy:g} {spec.width} {spec.height}">'
        '<defs/><g id="Model" class="Model v1-1"><g class="Floor"><g class="Floorplan Floor-1">'
        f"{body}</g></g></g></svg>"
    ).encode()


def room_pixels(spec: Room) -> NDArray[np.uint8]:
    """Ảnh `F1_scaled` của phòng: nền trắng, tường đen, khe cửa trắng (nhãn đúng thì `ink_ratio` ~ 1)."""
    pixels = np.full((spec.height, spec.width, 3), 255, dtype=np.uint8)
    for wall in spec.walls:
        x0, y0, x1, y1 = bounds(wall)
        pixels[y0:y1, x0:x1] = 0
    for door in spec.doors:
        x0, y0, x1, y1 = bounds(door)
        pixels[y0:y1, x0:x1] = 255
    return pixels


def room_png(spec: Room, *, rgba: bool = False) -> bytes:
    """PNG RGB của `room_pixels`; `rgba=True` → nền **đen** trong suốt, tường đen đục.

    Nền đen trong suốt bắt bộ nạp ghép sai nền: ghép lên trắng (đúng) thì nền trắng, bỏ alpha
    (sai) thì cả ảnh đen.
    """
    pixels = room_pixels(spec)
    if not rgba:
        return encode_rgb_png(pixels)
    rgba_pixels = np.zeros((spec.height, spec.width, 4), dtype=np.uint8)
    rgba_pixels[..., 3] = np.where((pixels == 0).all(axis=2), 255, 0)
    buffer = io.BytesIO()
    Image.fromarray(rgba_pixels).save(buffer, format="PNG")
    return buffer.getvalue()


def _chunk(kind: bytes, data: bytes) -> bytes:
    """Một chunk PNG: độ dài, loại, dữ liệu, CRC-32 của loại + dữ liệu."""
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png_header_only(width: int, height: int) -> bytes:
    """PNG RGB khai `width x height` mà IDAT chỉ vài byte: ảnh "bom" để kiểm trần điểm ảnh trước khi giải (K13)."""
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return PNG_SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(bytes(16))) + _chunk(b"IEND", b"")


def write_sample(
    root: Path, subset: str, sample_id: str, *, svg: bytes | None, scaled: bytes | None, original: bytes | None = None
) -> Path:
    """Thư mục `root/subset/sample_id/` với đúng các tệp được truyền (`None` = không ghi tệp đó)."""
    sample_dir = root / subset / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (("model.svg", svg), ("F1_scaled.png", scaled), ("F1_original.png", original)):
        if data is not None:
            (sample_dir / name).write_bytes(data)
    return sample_dir


def write_room_sample(
    root: Path, subset: str, sample_id: str, spec: Room | None = None, *, origin: Point = ORIGIN
) -> Path:
    """Một mẫu chuẩn đủ ba tệp: `model.svg`, `F1_scaled.png` khổ phòng, `F1_original.png` nửa khổ (không dùng)."""
    spec = spec if spec is not None else room()
    original = room_pixels(spec)[::2, ::2]
    return write_sample(
        root,
        subset,
        sample_id,
        svg=room_svg(spec, origin=origin),
        scaled=room_png(spec),
        original=encode_rgb_png(np.ascontiguousarray(original)),
    )


def write_dataset(root: Path, layout: Mapping[str, Sequence[str]], *, width: int = 320, height: int = 240) -> Path:
    """Cây CubiCasa giả `root/<subset>/<id>/` gồm các mẫu chuẩn khổ `width x height`; trả `root`."""
    spec = room(width, height)
    for subset, sample_ids in layout.items():
        for sample_id in sample_ids:
            write_room_sample(root, subset, sample_id, spec)
    return root


def zip_tree(src: Path, dest: Path, *, prefix: str = "cubicasa5k") -> Path:
    """Nén `src` thành zip tất định (thứ tự tên, mốc giờ cố định) dưới thư mục gốc `prefix/`, như zip thật."""
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in src.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(f"{prefix}/{path.relative_to(src).as_posix()}", date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return dest


async def new_dataset(maker: async_sessionmaker[AsyncSession], *, family: str = WALL_FAMILY) -> str:
    """Một dòng `datasets` mới của họ `family`, đã commit; trả id (dùng chung bốn file test, R-07)."""
    async with maker() as db:
        return (await make_dataset(db, family=family)).id


async def run_import(
    maker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    settings: CubiCasaSettings,
    *,
    src: Path,
    dataset_id: str,
    limit: int | None = None,
) -> ImportReport:
    """Một lượt `import_cubicasa` với tài nguyên của test — gọn hơn lặp tám đối số ở mỗi ca."""
    return await import_cubicasa(maker, storage, clock, src=src, dataset_id=dataset_id, limit=limit, settings=settings)


async def read_object(storage: ObjectStorage, key: str) -> bytes:
    """Toàn bộ byte của một object nhỏ của test (artifact mẫu, manifest)."""
    return b"".join([chunk async for chunk in storage.open_read(key)])


async def version_keys(storage: ObjectStorage, version_id: str) -> list[str]:
    """Khoá dưới tiền tố của một phiên bản, sắp tăng — `[]` nghĩa là lượt đã dọn sạch."""
    return sorted([info.key async for info in storage.list_prefix(version_prefix(version_id))])


async def read_manifest(storage: ObjectStorage, version_id: str) -> tuple[ManifestEntry, ...]:
    """`manifest.jsonl` của một phiên bản, đã qua `parse_manifest` (kiểm luôn luật manifest)."""
    return parse_manifest(await read_object(storage, f"{version_prefix(version_id)}{MANIFEST_NAME}"))


async def read_version(maker: async_sessionmaker[AsyncSession], version_id: str) -> DatasetVersionRow:
    """Dòng `dataset_versions` đọc lại bằng **session khác** — lệnh đã commit, session cũ đã đóng.

    Dùng chung cho mọi tệp test của module (trạng thái, `failure_code`, `manifest_sha256` của M06).
    """
    async with maker() as db:
        stmt = select(DatasetVersionRow).where(DatasetVersionRow.id == version_id)
        return (await db.execute(stmt)).scalar_one()
