"""Test `import_cubicasa` trên Postgres và kho đĩa thật (B6-02b [8]; K23: không mock hai thứ đó).

Dữ liệu nguồn do `fake_cubicasa` dựng, nên đáp án pixel của mỗi mẫu là hằng tính được: tường
dày 8 px, một khe cửa ở tường dưới, một cửa sổ ở tường trên, `Toilet` + `BaseCabinet`.
Tên test không có `__` ([8]: dạng đó dành cho `operationId` và task).
"""

import io
import logging
import os
from collections.abc import AsyncIterable, Mapping
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_datasets.errors import (
    DATASET_BUILD_IN_PROGRESS,
    DATASET_EMPTY,
    DATASET_FAMILY_UNSUPPORTED,
    DATASET_TOO_LARGE,
)
from apps.api.admin_ml_datasets.versions import fail_version, touch_version
from apps.worker.datasets.tasks import UNSUPPORTED_FAMILY, WALL_FAMILY, version_prefix
from apps.worker.datasets_cubicasa import importer
from apps.worker.datasets_cubicasa.archive import read_regular
from apps.worker.datasets_cubicasa.importer import (
    ARCHIVE_UNSAFE,
    DATASET_NOT_FOUND,
    SOURCE_EMPTY,
    SOURCE_INVALID,
    SOURCE_READ_FAILED,
)
from apps.worker.datasets_cubicasa.settings import CubiCasaSettings
from apps.worker.datasets_cubicasa.tests.fake_cubicasa import (
    bounds,
    new_dataset,
    png_header_only,
    read_manifest,
    read_object,
    read_version,
    room,
    room_png,
    room_svg,
    run_import,
    version_keys,
    write_dataset,
    write_room_sample,
    write_sample,
    zip_tree,
)
from packages.core.clock import Clock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, PAYLOAD_TOO_LARGE
from packages.core.errors import AppError
from packages.db.models.admin_ml_datasets import DatasetRow, DatasetVersionRow
from packages.ml_contracts.artifacts import decode_mask, objects_from_json
from packages.ml_contracts.datasets import SampleMeta, split_for
from packages.storage.port import ObjectStorage
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.fixtures.clock import FakeClock

Maker = async_sessionmaker[AsyncSession]
OBJECT_FAMILY = "openingAndFurnitureDetection"
LAYOUT = {"high_quality": ["101", "102"], "colorful": ["7"]}
NO_WALL_SVG = (
    b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="320" height="240" '
    b'viewBox="0 0 320 240"><g class="FixedFurniture Toilet"><rect x="20" y="20" width="40" height="40"/>'
    b"</g></svg>"
)
DOCTYPE_SVG = b'<?xml version="1.0"?>\n<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>'


@pytest.fixture
def cubicasa_settings(tmp_path: Path) -> CubiCasaSettings:
    """Cấu hình của test: thư mục tạm riêng để kiểm "giải nén xong thì không còn gì"."""
    return CubiCasaSettings(cubicasa_work_dir=tmp_path / "work")


@pytest.fixture
def src(tmp_path: Path) -> Path:
    """Thư mục nguồn rỗng, mỗi test tự ghi mẫu vào (`write_dataset`, `write_sample`)."""
    path = tmp_path / "src"
    path.mkdir()
    return path


async def _version_count(maker: Maker, dataset_id: str) -> int:
    """Số bản của một dataset — ca "từ chối" phải không tạo thêm bản nào (đếm riêng dataset
    của test để không phụ thuộc dữ liệu của test khác trong cùng Postgres)."""
    async with maker() as db:
        stmt = select(func.count()).select_from(DatasetVersionRow).where(DatasetVersionRow.dataset_id == dataset_id)
        return (await db.execute(stmt)).scalar_one()


async def test_import_full_flow_wall_family(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Ba mẫu, hai subset, họ tường → bản `ready`, manifest khớp kho, `walls.png` đúng pixel."""
    write_dataset(src, LAYOUT)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.exit_code, report.skipped) == ("ready", 0, {})
    assert report.version_id is not None
    version = await read_version(db_sessionmaker, report.version_id)
    assert (version.status, version.source, version.created_by) == ("ready", "cubicasa5k", "cli:datasets_cubicasa")
    assert sum(report.split_counts.values()) == 3
    assert report.branches == {"identity": 3}
    assert sorted(report.ink_ratios) == ["colorful", "high_quality"]
    assert ("BaseCabinet", 3) in report.unknown_fixtures
    manifest = await read_manifest(local_storage, report.version_id)
    assert len(manifest) == 3 * 3
    for entry in manifest:
        info = await local_storage.stat(f"{version_prefix(report.version_id)}{entry.path}")
        assert info is not None
        assert (info.sha256, info.size) == (entry.sha256, entry.bytes)


async def test_import_full_flow_wall_mask_pixels(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """`walls.png` True giữa tường, False giữa khe cửa và giữa phòng; `meta.json` đúng nhóm."""
    spec = room()
    write_room_sample(src, "high_quality", "101", spec)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.version_id is not None
    split = split_for("cubicasa:101")
    prefix = f"{version_prefix(report.version_id)}{split}/cubicasa-101/"
    walls_png = await read_object(local_storage, f"{prefix}walls.png")
    mask = decode_mask(walls_png, width_px=spec.width, height_px=spec.height)
    wall_x0, wall_y0, wall_x1, wall_y1 = bounds(spec.walls[0])
    door_x0, door_y0, door_x1, door_y1 = bounds(spec.doors[0])
    assert bool(mask[(wall_y0 + wall_y1) // 2, (wall_x0 + wall_x1) // 2]) is True
    assert bool(mask[(door_y0 + door_y1) // 2, (door_x0 + door_x1) // 2]) is False
    assert bool(mask[spec.height // 2, spec.width // 2]) is False
    meta = SampleMeta.model_validate_json(await read_object(local_storage, f"{prefix}meta.json"))
    assert (meta.sample_id, meta.group_key, meta.source) == ("cubicasa-101", "cubicasa:101", "cubicasa5k")
    assert (meta.width_px, meta.height_px, meta.mm_per_px) == (spec.width, spec.height, None)
    assert report.split_counts[split] == 1


async def test_import_full_flow_object_family(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Họ cửa/đồ → `objects.json` có `door`, `window`, `sanitary_fixture` đúng hộp ±1 px."""
    spec = room()
    write_room_sample(src, "high_quality", "101", spec)
    dataset_id = await new_dataset(db_sessionmaker, family=OBJECT_FAMILY)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.outcome == "ready"
    assert report.version_id is not None
    prefix = f"{version_prefix(report.version_id)}{split_for('cubicasa:101')}/cubicasa-101/"
    result = objects_from_json(await read_object(local_storage, f"{prefix}objects.json"))
    assert [item.label for item in result.detections] == ["door", "window", "sanitary_fixture"]
    expected = (bounds(spec.doors[0]), bounds(spec.windows[0]), bounds(spec.fixtures[0][1]))
    for detection, (x0, y0, x1, y1) in zip(result.detections, expected, strict=True):
        box = detection.box
        drift = (abs(box.x_min - x0), abs(box.y_min - y0), abs(box.x_max - x1), abs(box.y_max - y1))
        assert max(drift) <= 1
    assert await local_storage.stat(f"{prefix}walls.png") is None


async def test_import_zip_source_without_extension(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    tmp_path: Path,
) -> None:
    """Zip nhận theo magic `PK\\x03\\x04`, không theo đuôi (K14); thư mục tạm xoá sau lượt."""
    write_dataset(src, {"high_quality": ["101"]})
    archive = zip_tree(src, tmp_path / "bundle.dat")
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=archive, dataset_id=dataset_id
    )
    assert (report.outcome, report.split_counts and sum(report.split_counts.values())) == ("ready", 1)
    assert list(cubicasa_settings.cubicasa_work_dir.iterdir()) == []


async def test_import_directory_named_zip(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    tmp_path: Path,
) -> None:
    """Thư mục tên `x.zip` xử lý như thư mục (đuôi không quyết định gì, K14)."""
    root = tmp_path / "src.zip"
    root.mkdir()
    write_dataset(root, {"high_quality": ["101"]})
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=root, dataset_id=dataset_id
    )
    assert report.outcome == "ready"


async def test_import_unsafe_zip_refused(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    tmp_path: Path,
) -> None:
    """Zip có mục `../evil` → `ARCHIVE_UNSAFE`/`path`, không tệp nào ngoài đích, tạm đã xoá."""
    write_dataset(src, {"high_quality": ["101"]})
    archive = zip_tree(src, tmp_path / "bad.zip", prefix="../evil")
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=archive, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.reason, report.exit_code) == ("refused", ARCHIVE_UNSAFE, "path", 2)
    assert list(cubicasa_settings.cubicasa_work_dir.iterdir()) == []
    assert not (tmp_path / "evil").exists()
    assert await _version_count(db_sessionmaker, dataset_id) == 0


@pytest.mark.parametrize("name", ["plain.txt", "missing"])
async def test_import_bad_source_refused(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    tmp_path: Path,
    name: str,
) -> None:
    """Tệp không phải zip và đường không tồn tại đều → `SOURCE_INVALID` (không tạo bản)."""
    path = tmp_path / name
    if name.endswith(".txt"):
        path.write_bytes(b"khong phai zip")
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=path, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.exit_code) == ("refused", SOURCE_INVALID, 2)
    assert await _version_count(db_sessionmaker, dataset_id) == 0


async def test_import_empty_directory_refused(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Thư mục không có mẫu nào → `SOURCE_EMPTY`, trước khi mở phiên bản."""
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.exit_code) == ("refused", SOURCE_EMPTY, 2)
    assert await _version_count(db_sessionmaker, dataset_id) == 0


@pytest.mark.parametrize("dataset_id", ["dst_x", "dst_01J0000000000000000000000Z"])
async def test_import_unknown_dataset_refused(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    dataset_id: str,
) -> None:
    """Id sai mẫu và id hợp lệ không có dataset đều → `DATASET_NOT_FOUND`, không tạo bản."""
    write_dataset(src, {"high_quality": ["101"]})
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.exit_code) == ("refused", DATASET_NOT_FOUND, 2)
    assert await _version_count(db_sessionmaker, dataset_id) == 0


async def test_import_unsupported_family_refused(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Họ `dimensionReading` không có mẫu ảnh dựng được → `DATASET_FAMILY_UNSUPPORTED`."""
    write_dataset(src, {"high_quality": ["101"]})
    dataset_id = await new_dataset(db_sessionmaker, family=UNSUPPORTED_FAMILY)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.exit_code) == ("refused", DATASET_FAMILY_UNSUPPORTED, 2)
    assert await _version_count(db_sessionmaker, dataset_id) == 0


async def test_import_building_version_refused(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Dataset đã có bản `building` → `DATASET_BUILD_IN_PROGRESS`, không mở bản thứ hai."""
    write_dataset(src, {"high_quality": ["101"]})
    async with db_sessionmaker() as db:
        dataset = await make_dataset(db, family=WALL_FAMILY)
        await make_dataset_version(db, dataset=dataset, status="building")
        dataset_id = dataset.id
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.exit_code) == ("refused", DATASET_BUILD_IN_PROGRESS.code, 2)
    assert await _version_count(db_sessionmaker, dataset_id) == 1


async def test_import_limit_takes_first_samples(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """`limit=2` chỉ nhập hai mẫu đầu theo thứ tự `(subset, id)`."""
    write_dataset(src, LAYOUT)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id, limit=2
    )
    assert (report.outcome, sum(report.split_counts.values())) == ("ready", 2)


async def test_import_storage_unavailable_fails_clean(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kho ném `DEPENDENCY_UNAVAILABLE` ở mẫu thứ hai → bản `failed`, tiền tố rỗng, thoát 1."""
    write_dataset(src, LAYOUT)
    original = local_storage.put
    seen = {"images": 0}

    async def flaky(key: str, data: bytes | AsyncIterable[bytes], **kwargs: Any) -> Any:
        """Chỉ đếm `image.png` (mỗi mẫu đúng một lần) để biết đang ở mẫu thứ mấy."""
        if key.endswith("image.png"):
            seen["images"] += 1
            if seen["images"] == 2:
                raise DEPENDENCY_UNAVAILABLE.error(retry_after=5)
        return await original(key, data, **kwargs)

    monkeypatch.setattr(local_storage, "put", flaky)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.exit_code) == ("failed", DEPENDENCY_UNAVAILABLE.code, 1)
    assert report.version_id is not None
    assert await version_keys(local_storage, report.version_id) == []
    assert (await read_version(db_sessionmaker, report.version_id)).status == "failed"


async def test_import_all_samples_skipped_is_empty(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Mọi mẫu bị bỏ → `DATASET_EMPTY`, bản `failed`, tiền tố rỗng."""
    spec = room()
    write_sample(src, "high_quality", "101", svg=room_svg(spec), scaled=None)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.skipped) == ("failed", DATASET_EMPTY, {"no_image": 1})
    assert report.version_id is not None
    assert await version_keys(local_storage, report.version_id) == []


async def test_import_over_max_samples_fails(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
    src: Path,
) -> None:
    """Trần `cubicasa_max_samples=2` với 3 mẫu → `DATASET_TOO_LARGE`, tiền tố đã dọn."""
    write_dataset(src, LAYOUT)
    settings = CubiCasaSettings(cubicasa_max_samples=2, cubicasa_work_dir=tmp_path / "work")
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(db_sessionmaker, local_storage, fake_clock, settings, src=src, dataset_id=dataset_id)
    assert (report.outcome, report.code, report.exit_code) == ("failed", DATASET_TOO_LARGE, 1)
    assert report.version_id is not None
    assert await version_keys(local_storage, report.version_id) == []


async def test_import_source_read_error_fails(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`OSError` khi đọc tệp nguồn ở mẫu hai → `SOURCE_READ_FAILED` (không phải bỏ một mẫu)."""
    write_dataset(src, {"high_quality": ["101", "102"]})
    original = read_regular
    seen = {"reads": 0}

    def flaky(path: Path, *, max_bytes: int) -> bytes:
        """Lượt đọc thứ ba là `model.svg` của mẫu hai (mỗi mẫu đọc SVG rồi PNG)."""
        seen["reads"] += 1
        if seen["reads"] == 3:
            raise OSError("o dia loi")
        return original(path, max_bytes=max_bytes)

    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer.read_regular", flaky)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.exit_code) == ("failed", SOURCE_READ_FAILED, 1)
    assert report.version_id is not None
    assert await version_keys(local_storage, report.version_id) == []


async def test_import_finish_lost_version_fails(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`finish_version` trả `False` (phiên khác chốt `failed` trước) → tiền tố rỗng, mã đọc lại."""
    write_dataset(src, {"high_quality": ["101"]})

    async def stolen(db: AsyncSession, *, version_id: str, clock: Clock, **kwargs: Any) -> bool:
        """Giả lập một phiên khác vừa chốt bản `failed` ngay trước lượt `finish_version`."""
        await fail_version(db, version_id=version_id, failure_code=DATASET_TOO_LARGE, clock=clock)
        return False

    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer.finish_version", stolen)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.code, report.exit_code) == ("failed", DATASET_TOO_LARGE, 1)
    assert report.version_id is not None
    assert await version_keys(local_storage, report.version_id) == []


async def test_import_skips_image_bomb_without_decoding(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PNG khai 50.000 x 50.000 → `image_invalid` mà **không** giải một pixel nào (K13)."""
    write_sample(src, "high_quality", "101", svg=room_svg(room()), scaled=png_header_only(50_000, 50_000))
    loads: list[str] = []
    original_load = Image.Image.load

    def spy(self: Image.Image) -> Any:
        """Gián điệp: mỗi lượt giải ảnh để lại một vết."""
        loads.append("load")
        return original_load(self)

    monkeypatch.setattr(Image.Image, "load", spy)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.skipped == {"image_invalid": 1}
    assert loads == []


async def test_import_rgba_image_gets_white_background(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """PNG RGBA nền trong suốt → `image.png` ghép lên nền trắng (không phải đen)."""
    spec = room()
    write_sample(src, "high_quality", "101", svg=room_svg(spec), scaled=room_png(spec, rgba=True))
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.outcome == "ready"
    assert report.version_id is not None
    prefix = f"{version_prefix(report.version_id)}{split_for('cubicasa:101')}/cubicasa-101/"
    with Image.open(io.BytesIO(await read_object(local_storage, f"{prefix}image.png"))) as image:
        pixels = np.asarray(image.convert("RGB"))
    assert tuple(int(value) for value in pixels[spec.height // 2, spec.width // 2]) == (255, 255, 255)


@pytest.mark.parametrize(
    ("family", "svg"),
    [(WALL_FAMILY, NO_WALL_SVG), (OBJECT_FAMILY, None)],
)
async def test_import_skips_sample_without_labels_of_family(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    family: str,
    svg: bytes | None,
) -> None:
    """Thiếu nhãn của **họ của mình** → `no_labels`: SVG không tường, hay SVG chỉ có tường."""
    spec = room()
    bare = replace(spec, doors=(), windows=(), fixtures=())
    write_sample(src, "high_quality", "101", svg=svg if svg is not None else room_svg(bare), scaled=room_png(spec))
    dataset_id = await new_dataset(db_sessionmaker, family=family)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.skipped == {"no_labels": 1}


async def test_import_skips_doctype_svg(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """`model.svg` có `<!DOCTYPE` → `svg_rejected` (không bao giờ đưa cho bộ đọc XML)."""
    write_sample(src, "high_quality", "101", svg=DOCTYPE_SVG, scaled=room_png(room()))
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.skipped == {"svg_rejected": 1}


async def test_import_skips_symlink_model_svg(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    tmp_path: Path,
) -> None:
    """`model.svg` là symlink → `unsafe_path`, kể cả khi đích là một SVG hợp lệ."""
    spec = room()
    target = tmp_path / "real.svg"
    target.write_bytes(room_svg(spec))
    sample = write_sample(src, "high_quality", "101", svg=b"", scaled=room_png(spec))
    (sample / "model.svg").unlink()
    os.symlink(target, sample / "model.svg")
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.skipped == {"unsafe_path": 1}


async def test_import_touches_version_on_slow_run(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mỗi mẫu tốn 61 s đồng hồ → `touch_version` ghi nhịp ≥ 2 lần (mốc 60 s, không chỉ mốc 50 mẫu)."""
    write_dataset(src, LAYOUT)
    original_convert = importer._convert_sample
    original_touch = touch_version
    ticks: list[str] = []

    def slow(sample: Any, family: str, settings: CubiCasaSettings) -> Any:
        """Mỗi mẫu đẩy đồng hồ qua mốc 60 s của `_Beat`."""
        fake_clock.advance(timedelta(seconds=61))
        return original_convert(sample, family, settings)

    async def counting(db: AsyncSession, *, version_id: str, clock: Clock) -> bool:
        """Đếm mỗi lượt ghi nhịp thật."""
        ticks.append(version_id)
        return await original_touch(db, version_id=version_id, clock=clock)

    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer._convert_sample", slow)
    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer.touch_version", counting)
    dataset_id = await new_dataset(db_sessionmaker)
    with caplog.at_level(logging.WARNING):
        report = await run_import(
            db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
        )
    assert report.outcome == "ready"
    assert len(ticks) >= 2


async def test_import_counts_duplicate_and_bad_ids(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Bộ đếm của `discover_samples` (`bad_id`, `duplicate_id`) vào thẳng báo cáo."""
    spec = room()
    write_room_sample(src, "high_quality", "101", spec)
    write_room_sample(src, "colorful", "101", spec)
    write_room_sample(src, "colorful", "12a", spec)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, sum(report.split_counts.values())) == ("ready", 1)
    assert report.skipped == {"bad_id": 1, "duplicate_id": 1}


async def test_import_report_fields_are_plain_mappings(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Báo cáo chỉ chứa dữ liệu thường (lệnh in được) và `fit` đo theo subset."""
    write_dataset(src, LAYOUT)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert isinstance(report.split_counts, Mapping)
    assert sorted(report.fits) == ["colorful.x", "colorful.y", "high_quality.x", "high_quality.y"]
    assert all(value == pytest.approx(1.0) for values in report.fits.values() for value in values)
    assert all(0.0 <= value <= 1.0 for values in report.ink_ratios.values() for value in values)


async def test_import_keeps_other_dataset_rows_untouched(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Lượt nhập chỉ ghi `dataset_versions` của dataset được chỉ định (không chạm dataset khác)."""
    write_dataset(src, {"high_quality": ["101"]})
    other = await new_dataset(db_sessionmaker)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.outcome == "ready"
    async with db_sessionmaker() as db:
        stmt = select(func.count()).select_from(DatasetVersionRow).where(DatasetVersionRow.dataset_id == other)
        assert (await db.execute(stmt)).scalar_one() == 0
        assert (await db.execute(select(DatasetRow.family).where(DatasetRow.id == other))).scalar_one() == WALL_FAMILY


async def test_import_skips_oversized_svg(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
    src: Path,
) -> None:
    """`model.svg` dài hơn `CUBICASA_SVG_MAX_BYTES` → `svg_rejected`, không đọc hết tệp."""
    write_dataset(src, {"high_quality": ["101"]})
    settings = CubiCasaSettings(cubicasa_svg_max_bytes=16, cubicasa_work_dir=tmp_path / "work")
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(db_sessionmaker, local_storage, fake_clock, settings, src=src, dataset_id=dataset_id)
    assert report.skipped == {"svg_rejected": 1}


async def test_import_skips_broken_xml(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """XML hỏng cú pháp → `svg_invalid` (khác `svg_rejected` = bị từ chối theo luật)."""
    write_sample(src, "high_quality", "101", svg=b"<svg><g", scaled=room_png(room()))
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.skipped == {"svg_invalid": 1}


async def test_import_skips_oversized_image(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
    src: Path,
) -> None:
    """`F1_scaled.png` dài hơn `CUBICASA_MAX_FILE_BYTES` → `image_invalid`."""
    write_dataset(src, {"high_quality": ["101"]})
    settings = CubiCasaSettings(cubicasa_max_file_bytes=32, cubicasa_work_dir=tmp_path / "work")
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(db_sessionmaker, local_storage, fake_clock, settings, src=src, dataset_id=dataset_id)
    assert report.skipped == {"image_invalid": 1}


async def test_import_skips_image_that_is_not_a_png(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Tệp tên `F1_scaled.png` mà không có IHDR hợp lệ → `image_invalid` (K14, không theo đuôi)."""
    write_sample(src, "high_quality", "101", svg=room_svg(room()), scaled=b"khong phai PNG")
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.skipped == {"image_invalid": 1}


async def test_import_measures_no_ink_when_wall_mask_is_empty(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Họ cửa/đồ với SVG không tường → vẫn ghi mẫu, nhưng không có `ink_ratio` nào để báo."""
    write_sample(src, "high_quality", "101", svg=NO_WALL_SVG, scaled=room_png(room()))
    dataset_id = await new_dataset(db_sessionmaker, family=OBJECT_FAMILY)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.ink_ratios) == ("ready", {})
    assert report.fits["high_quality.x"] == pytest.approx((1.0,))
    assert report.fits["high_quality.y"] == pytest.approx((1.0,))


async def test_import_reraises_an_unrelated_storage_error(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AppError` khác `DEPENDENCY_UNAVAILABLE` không được âm thầm thành bản `failed` (R-16)."""
    write_dataset(src, {"high_quality": ["101"]})

    async def broken(key: str, data: bytes | AsyncIterable[bytes], **kwargs: Any) -> Any:
        """Lỗi lập trình của kho: mã không thuộc nhóm hạ tầng tạm thời."""
        raise PAYLOAD_TOO_LARGE.error()

    monkeypatch.setattr(local_storage, "put", broken)
    dataset_id = await new_dataset(db_sessionmaker)
    with pytest.raises(AppError) as caught:
        await run_import(db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id)

    assert caught.value.code is PAYLOAD_TOO_LARGE


async def test_import_still_reports_failed_when_cleanup_fails(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dọn tiền tố hỏng chỉ ghi log: kết cục vẫn `failed` (lịch B6-02 dọn lại sau một giờ)."""
    write_dataset(src, {"high_quality": ["101"]})

    async def no_prefix_delete(prefix: str) -> None:
        """Kho không xoá được (đĩa chỉ đọc chẳng hạn)."""
        raise OSError("read-only")

    def skip_everything(sample: Any, family: str, settings: CubiCasaSettings) -> str:
        """Mọi mẫu bị bỏ → lượt đi vào đường `DATASET_EMPTY` rồi mới dọn tiền tố."""
        return "no_image"

    monkeypatch.setattr(local_storage, "delete_prefix", no_prefix_delete)
    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer._convert_sample", skip_everything)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert (report.outcome, report.code) == ("failed", DATASET_EMPTY)


async def test_import_refuses_when_extraction_hits_an_os_error(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`OSError` giữa lúc giải nén → `SOURCE_INVALID` (nguồn không dùng được, chưa mở bản)."""
    write_dataset(src, {"high_quality": ["101"]})
    archive = zip_tree(src, tmp_path / "bundle.zip")

    def broken(zip_path: Path, dest: Path, **kwargs: int) -> int:
        """Đĩa đầy giữa lượt giải nén."""
        raise OSError("het cho")

    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer.safe_extract", broken)
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=archive, dataset_id=dataset_id
    )
    assert (report.outcome, report.code) == ("refused", SOURCE_INVALID)
    assert list(cubicasa_settings.cubicasa_work_dir.iterdir()) == []


async def test_import_warns_when_the_version_is_no_longer_building(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`touch_version` trả `False` → cảnh báo rồi chạy tiếp; `finish_version` mới chốt kết cục."""
    write_dataset(src, {"high_quality": ["101"]})

    async def dead(db: AsyncSession, *, version_id: str, clock: Clock) -> bool:
        """Bản đã bị lịch quét đóng giữa lượt."""
        return False

    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer.touch_version", dead)
    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer.TOUCH_EVERY_SAMPLES", 1)
    dataset_id = await new_dataset(db_sessionmaker)
    with caplog.at_level(logging.WARNING, logger="apps.worker.datasets_cubicasa.importer"):
        report = await run_import(
            db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
        )
    assert report.outcome == "ready"
    assert "cubicasa_touch_skipped" in caplog.text


async def test_import_skips_symlinked_image(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    tmp_path: Path,
) -> None:
    """`F1_scaled.png` là symlink → `unsafe_path` (A2: chỉ tệp thường được đọc, `O_NOFOLLOW`)."""
    spec = room()
    target = tmp_path / "real.png"
    target.write_bytes(room_png(spec))
    sample = write_sample(src, "high_quality", "101", svg=room_svg(spec), scaled=None)
    os.symlink(target, sample / "F1_scaled.png")
    dataset_id = await new_dataset(db_sessionmaker)
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert report.skipped == {"unsafe_path": 1}


async def test_import_reports_failed_when_fail_version_cannot_write(
    db_sessionmaker: Maker,
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """DB chết ngay lúc chốt `failed` → log `error`, vẫn trả `failed` (không ném traceback ra lệnh).

    Bản khi đó còn `building`; lịch quét của B6-02 sẽ đóng nó `DATASET_BUILD_TIMEOUT` sau một giờ.
    """
    write_dataset(src, {"high_quality": ["101"]})

    async def dead_db(db: AsyncSession, *, version_id: str, failure_code: str, clock: Clock) -> bool:
        """Kết nối DB rụng giữa lượt chốt bản hỏng."""
        raise DBAPIError("UPDATE dataset_versions", None, OSError("connection reset"))

    def skip_everything(sample: Any, family: str, settings: CubiCasaSettings) -> str:
        """Mọi mẫu bị bỏ → lượt đi vào đường `DATASET_EMPTY`, tức là đường `_fail`."""
        return "no_image"

    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer.fail_version", dead_db)
    monkeypatch.setattr("apps.worker.datasets_cubicasa.importer._convert_sample", skip_everything)
    dataset_id = await new_dataset(db_sessionmaker)
    with caplog.at_level(logging.ERROR, logger="apps.worker.datasets_cubicasa.importer"):
        report = await run_import(
            db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
        )
    assert (report.outcome, report.code, report.exit_code) == ("failed", DATASET_EMPTY, 1)
    assert "cubicasa_fail_version_failed" in caplog.text
    assert report.version_id is not None
    assert await version_keys(local_storage, report.version_id) == []
