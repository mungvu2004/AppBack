"""K36 (không giữ kết nối khi ghi kho), bất biến nhập lại, hiệu năng, ranh giới nhập (B6-02b [8], C2).

K36 dùng engine riêng trần nhỏ (`db_pool_size=1`) để lượt chặn `put` lộ ra ngay nếu
`import_cubicasa` giữ session qua lượt ghi kho — pool 1 kết nối thì giữ sai sẽ treo cả lượt test
chứ không chỉ chậm. Perf: `write_dataset` 50 mẫu 1500x1000 (đo trước, không tính vào ngân sách),
đo một lượt nhập; log bằng `logging`, không `print` (BE-00 §12).
"""

import asyncio
import logging
import subprocess
import sys
import time
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool

from apps.worker.datasets.tasks import version_prefix
from apps.worker.datasets_cubicasa.settings import CubiCasaSettings
from apps.worker.datasets_cubicasa.tests.fake_cubicasa import (
    new_dataset,
    read_manifest,
    read_version,
    run_import,
    write_dataset,
)
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.settings import DatabaseSettings
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectInfo
from packages.testing.boundary import WORKER_BLOCKED
from packages.testing.fixtures.clock import FakeClock

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
IMPORT_TIMEOUT_S: Final = 120.0
BLOCK_WAIT_S: Final = 30.0
PERF_SAMPLE_COUNT: Final = 50
PERF_BUDGET_S_PER_SAMPLE: Final = 0.5

Maker = async_sessionmaker[AsyncSession]
_logger = logging.getLogger(__name__)


@pytest.fixture
def src(tmp_path: Path) -> Path:
    """Thư mục nguồn rỗng, mỗi test tự ghi mẫu vào bằng `write_dataset`."""
    path = tmp_path / "src"
    path.mkdir()
    return path


@pytest.fixture
def cubicasa_settings(tmp_path: Path) -> CubiCasaSettings:
    """Cấu hình nhập của test, thư mục giải nén riêng."""
    return CubiCasaSettings(cubicasa_work_dir=tmp_path / "work")


def _single_connection_engine(db_url: str) -> AsyncEngine:
    """Engine pool **một** kết nối, không tràn (K36): giữ sai một session là lộ ra ngay bằng bộ đếm."""
    return create_engine(
        DatabaseSettings(
            database_url=db_url,
            db_pool_size=1,
            db_max_overflow=0,
            db_pool_timeout_s=1,
            db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S),
        )
    )


async def test_import_cubicasa_holds_no_connection_while_putting(
    db_url: str,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Lượt `put` đang bị chặn → `pool.checkedout() == 0` (K22, K36): không session nào bị giữ qua I/O kho."""
    write_dataset(src, {"high_quality": ["101"]})
    original_put = local_storage.put
    engine = _single_connection_engine(db_url)
    maker = create_sessionmaker(engine)
    try:
        dataset_id = await new_dataset(maker)
        entered, released = asyncio.Event(), asyncio.Event()

        async def blocking_put(
            key: str, data: bytes | AsyncIterable[bytes], *, content_type: str, max_bytes: int
        ) -> ObjectInfo:
            """Lượt `put` đầu báo đã vào rồi đứng chờ; các lượt sau đi thẳng (K36 chỉ cần chặn một lần)."""
            if not entered.is_set():
                entered.set()
                await released.wait()
            return await original_put(key, data, content_type=content_type, max_bytes=max_bytes)

        local_storage.put = blocking_put  # type: ignore[method-assign]  # giả tầng I/O chậm, kho thật bên dưới
        pool = engine.pool
        assert isinstance(pool, QueuePool)

        task = asyncio.create_task(
            run_import(maker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id)
        )
        try:
            await asyncio.wait_for(entered.wait(), timeout=BLOCK_WAIT_S)
            assert pool.checkedout() == 0
        finally:
            released.set()
            report = await task

        assert pool.checkedout() == 0
        assert report.outcome == "ready"
    finally:
        local_storage.put = original_put  # type: ignore[method-assign]  # trả lại `put` thật sau khi test xong
        await engine.dispose()


async def test_import_cubicasa_reimport_is_idempotent(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """Nhập cùng nguồn hai lần tuần tự vào cùng dataset → hai bản `ready` khác id, cùng manifest,
    cùng split mỗi mẫu; các object của bản đầu không bị đổi sau lượt hai (M06, bất biến)."""
    write_dataset(src, {"high_quality": ["101", "102"], "colorful": ["7"]})
    dataset_id = await new_dataset(db_sessionmaker)

    first = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert first.outcome == "ready"
    assert first.version_id is not None
    first_prefix = version_prefix(first.version_id)
    first_keys = sorted([info.key async for info in local_storage.list_prefix(first_prefix)])
    first_stats = {key: await local_storage.stat(key) for key in first_keys}
    first_manifest = await read_manifest(local_storage, first.version_id)

    second = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    assert second.outcome == "ready"
    assert second.version_id is not None
    assert second.version_id != first.version_id
    second_manifest = await read_manifest(local_storage, second.version_id)

    # M06: cùng nguồn → cùng manifest *byte cho byte* (cùng đường, cùng sha mỗi object), nên
    # `manifest_sha256` của hai bản phải trùng; chỉ so tập đường thì một artifact đổi nội dung
    # vẫn lọt.
    assert {(entry.path, entry.sha256) for entry in first_manifest} == {
        (entry.path, entry.sha256) for entry in second_manifest
    }
    assert first.split_counts == second.split_counts
    first_row = await read_version(db_sessionmaker, first.version_id)
    second_row = await read_version(db_sessionmaker, second.version_id)
    assert first_row.manifest_sha256 is not None
    assert first_row.manifest_sha256 == second_row.manifest_sha256

    for key in first_keys:
        after = await local_storage.stat(key)
        before = first_stats[key]
        assert after is not None
        assert before is not None
        assert after.sha256 == before.sha256


@pytest.mark.perf
async def test_import_cubicasa_performance(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    cubicasa_settings: CubiCasaSettings,
    src: Path,
) -> None:
    """50 mẫu 1500x1000, họ tường → trung bình dưới `PERF_BUDGET_S_PER_SAMPLE` giây mỗi mẫu.

    Dựng dữ liệu (`write_dataset`, ~1,1 s đo riêng) không tính vào thời gian đo; chỉ bấm giờ lượt
    `import_cubicasa`. Cả file không gắn `perf` toàn cục — mọi dòng `importer.py` mà test này đi qua
    đã có test không-`perf` khác gánh độ phủ (bước 5 ở lớp gộp).
    """
    sample_ids = [str(i) for i in range(1, PERF_SAMPLE_COUNT + 1)]
    write_dataset(src, {"high_quality": sample_ids}, width=1500, height=1000)
    dataset_id = await new_dataset(db_sessionmaker)

    started = time.monotonic()
    report = await run_import(
        db_sessionmaker, local_storage, fake_clock, cubicasa_settings, src=src, dataset_id=dataset_id
    )
    elapsed = time.monotonic() - started

    assert report.outcome == "ready"
    assert sum(report.split_counts.values()) == PERF_SAMPLE_COUNT
    per_sample = elapsed / PERF_SAMPLE_COUNT
    _logger.info("import_cubicasa: %d mẫu trong %.3fs (%.4fs/mẫu)", PERF_SAMPLE_COUNT, elapsed, per_sample)
    assert per_sample < PERF_BUDGET_S_PER_SAMPLE, f"{per_sample:.4f}s/mẫu, trần {PERF_BUDGET_S_PER_SAMPLE}s"


@pytest.mark.parametrize(
    "module",
    [
        "apps.worker.datasets_cubicasa.cli",
        "apps.worker.datasets_cubicasa.importer",
        "apps.worker.datasets_cubicasa.archive",
        "apps.worker.datasets_cubicasa.svg",
        "apps.worker.datasets_cubicasa.convert",
        "apps.worker.datasets_cubicasa.settings",
    ],
)
def test_imports_without_web_or_crypto_packages(module: str) -> None:
    """Nhập được khi `fastapi`, `starlette`, `uvicorn`, `jwt`, `argon2` bị chặn (ảnh `worker` không cài chúng)."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", f"import sys; {blocked}; import {module}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=IMPORT_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stderr


def test_cli_does_not_import_torch_or_onnxruntime() -> None:
    """Nhập `cli` không kéo theo `torch`/`onnxruntime` (ảnh nhập dữ liệu không cần suy luận model)."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import apps.worker.datasets_cubicasa.cli; "
            "import sys; print('torch' in sys.modules or 'onnxruntime' in sys.modules)",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=IMPORT_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
