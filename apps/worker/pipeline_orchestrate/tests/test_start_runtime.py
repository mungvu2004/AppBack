"""K36 (pool nhỏ), trần bộ nhớ 40 MP, ranh giới nhập của `pipeline_orchestrate` (B5-06a việc D).

K36: `prepare_page` ([6] bước 3) phải chạy **ngoài** session DB, không thì một trang PDF to
giữ khoá kết nối cả lúc dựng ảnh — với `db_pool_size` nhỏ (ENV.md), vài lượt chạy song song đủ
cạn pool. Bộ nhớ: tiền xử lý ảnh 40 MP (trần `DEFAULT_MAX_PIXELS`) không được vượt 1,5 GiB RSS
của tiến trình con — con `spawn` tự đo `RUSAGE_SELF` rồi gửi về cha; `RUSAGE_CHILDREN` của cha
là đỉnh của **mọi** con đã kết thúc trong tiến trình pytest nên lẫn con của test khác (NO-339).
Ranh giới: `pipeline_orchestrate` là hàm worker nhập (BE-00 §7) — không được nhập `apps.ml`,
`torch`, `onnxruntime`, `fastapi` (khối [9]).
"""

import ast
import asyncio
import logging
import multiprocessing
import resource
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.messaging.payloads.drawings import PipelineStartPayload
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectStorage
from packages.testing.fixtures.clock import FakeClock

type Maker = async_sessionmaker[AsyncSession]

_log = logging.getLogger(__name__)

MEMORY_CEILING_KIB: Final = int(1.5 * 1024 * 1024)
"""1,5 GiB tính bằng KiB — `ru_maxrss` của Linux vốn đã tính theo KiB."""

FORBIDDEN_MODULES: Final = frozenset({"torch", "onnxruntime", "fastapi"})
"""Mô-đun cấm nhập tuyệt đối của một hàm worker (khối [9]); `apps.ml` xét riêng vì cùng gốc `apps`."""

_PACKAGE_ROOT: Final = Path(__file__).resolve().parents[1]


def _epoch() -> datetime:
    """Mốc giờ cố định cho `FakeClock` của các test trong file này."""
    return datetime(2026, 1, 1, tzinfo=UTC)


async def _seed_pdf_run(maker: Maker, storage: ObjectStorage, data: bytes) -> PipelineStartPayload:
    """Sân khấu + lượt tải PDF `complete` + lượt chạy `pending` — payload sẵn sàng cho `run_pipeline_start`."""
    from apps.api.drawings.runs import start_run
    from apps.api.drawings.tests._helpers import make_scene
    from packages.testing.factories.drawings import make_complete_upload

    async with maker() as db:
        scene = await make_scene(db)
        upload = await make_complete_upload(
            db, storage, project=scene.project, floor=scene.floor, data=data, file_name="huge.pdf"
        )
        await db.commit()
    async with maker() as db:
        run = await start_run(db, upload_id=upload.id, clock=FakeClock(start=_epoch()))
        await db.commit()
    return PipelineStartPayload(run_id=run.id, upload_id=upload.id)


@pytest.mark.perf
@pytest.mark.asyncio(loop_scope="function")
async def test_run_pipeline_start_releases_pool_before_rendering(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """K36: trong lúc `render_pdf_page` bị chặn, không session nào của `run_pipeline_start` còn checkout.

    `prepare_page` ([6] bước 3, KHUNG của B) không nhận tham số session (chữ ký chung B5-06a) —
    bất biến K36 chỉ giữ được nếu `run_pipeline_start` đóng session GD1 **trước** khi gọi nó.
    `render_pdf_page` (nhập ở `apps.worker.pipeline_orchestrate.preprocess`) bị vá bằng một
    `threading.Event` chặn cho tới khi test tự mở, rồi đọc `engine.pool.checkedout()` từ chính
    engine của `db_sessionmaker` trong lúc đó. Chạy `run_pipeline_start` bằng `asyncio.create_task`
    trên **cùng** vòng sự kiện của test, không luồng riêng: kết nối asyncpg của engine gắn với
    vòng sự kiện tạo ra nó, một `asyncio.run` khác vòng sẽ ném "attached to a different loop".
    `render_pdf_page` chặn ở `asyncio.to_thread` (executor riêng) nên vòng chính vẫn rảnh để
    `checkedout()` chạy đồng thời.
    """
    from apps.worker.pipeline_orchestrate import preprocess as preprocess_module
    from apps.worker.pipeline_orchestrate.start import run_pipeline_start
    from packages.vision.preprocess.tests.synthetic import make_pdf

    entered = threading.Event()
    release = threading.Event()
    original = preprocess_module.render_pdf_page  # type: ignore[attr-defined]  # không khai `__all__`

    def _blocking(*args: object, **kwargs: object) -> object:
        """Vào chỗ dừng, báo `entered`, chờ test mở `release` rồi chạy hàm thật."""
        entered.set()
        release.wait(timeout=5.0)
        return original(*args, **kwargs)  # type: ignore[arg-type]  # chữ ký thật, không `object`

    monkeypatch.setattr(preprocess_module, "render_pdf_page", _blocking)

    async with db_sessionmaker() as probe:
        engine = probe.bind
    assert isinstance(engine, AsyncEngine)

    payload = await _seed_pdf_run(db_sessionmaker, local_storage, make_pdf(1))

    task = asyncio.create_task(
        run_pipeline_start(payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    )
    try:
        await asyncio.to_thread(entered.wait, 5.0)
        assert entered.is_set(), "render_pdf_page không được gọi"
        assert engine.pool.checkedout() == 0  # type: ignore[attr-defined]  # pool asyncpg có `checkedout()`
    finally:
        release.set()
        await asyncio.wait_for(task, timeout=10.0)


def _child_prepare_40mp(queue: "multiprocessing.Queue[int]") -> None:
    """Tiến trình con: tiền xử lý một ảnh 40 MP rồi gửi `ru_maxrss` (KiB) của **chính nó** về cha."""
    from PIL import Image

    from apps.worker.pipeline_orchestrate.preprocess import PagePlan, PageSource, prepare_page
    from apps.worker.pipeline_orchestrate.settings import get_orchestrate_settings
    from apps.worker.pipeline_orchestrate.tests._helpers import LEVEL_ID
    from packages.core.clock import SystemClock
    from packages.core.ids import new_id
    from packages.vision.preprocess.tests.synthetic import encode

    width, height = 8000, 5000  # 40 000 000 px == DEFAULT_MAX_PIXELS
    image = Image.new("RGB", (width, height), (10, 20, 30))
    data = encode(image, "PNG")

    async def _go() -> None:
        """Ghi ảnh gốc vào kho tạm rồi chạy `prepare_page` đường `auto`."""
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskStorage(Path(tmp), FakeClock(start=_epoch()), "https://x.test")
            source = PageSource(
                run_id=new_id("run", SystemClock()),
                project_id=new_id("prj", SystemClock()),
                level_id=LEVEL_ID,
                upload_id=new_id("upl", SystemClock()),
                page_index=0,
                original_key="original.png",
                kind="png",
            )
            assert source.original_key is not None
            await storage.put(source.original_key, data, content_type="image/png", max_bytes=len(data) + 1)
            plan = PagePlan(source=source, kind="auto")
            await prepare_page(
                plan, storage=storage, settings=get_orchestrate_settings(), clock=FakeClock(start=_epoch())
            )

    asyncio.run(_go())
    queue.put(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


@pytest.mark.perf
def test_prepare_page_40mp_stays_under_memory_ceiling() -> None:
    """Ảnh 40 MP trong tiến trình con `spawn`; `ru_maxrss` của con ≤ 1,5 GiB (khối [11] mục 3).

    Đọc hàng **trước** `join` (khuôn `multiprocessing`: con chưa thoát khi còn dữ liệu chưa xả).
    """
    ctx = multiprocessing.get_context("spawn")
    queue: multiprocessing.Queue[int] = ctx.Queue()
    process = ctx.Process(target=_child_prepare_40mp, args=(queue,))
    process.start()
    peak_kib = queue.get(timeout=60.0)
    process.join(timeout=10.0)
    assert process.exitcode == 0
    _log.info("prepare_page_40mp_ru_maxrss_kib=%d", peak_kib)
    assert peak_kib <= MEMORY_CEILING_KIB, f"ru_maxrss {peak_kib} KiB > trần {MEMORY_CEILING_KIB} KiB"


def _imports_of(path: Path) -> set[str]:
    """Mọi mô-đun gốc mà một tệp `.py` nhập (`import x`, `from x import y`)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_pipeline_orchestrate_does_not_import_forbidden_modules() -> None:
    """Không tệp `.py` nào dưới `pipeline_orchestrate/` (trừ `tests/`) nhập `apps.ml`, `torch`,
    `onnxruntime`, `fastapi`.

    `pins`, `keys`, `dispatch`, `tasks` là hàm worker nhập được (BE-00 §7); test này chỉ chặn
    bốn mô-đun cấm tuyệt đối của khối [9], không chặn `apps.api.*` (đã được phép, dữ kiện đã tra).
    """
    offenders: dict[str, set[str]] = {}
    for path in _PACKAGE_ROOT.rglob("*.py"):
        if "tests" in path.relative_to(_PACKAGE_ROOT).parts:
            continue
        imports = _imports_of(path)
        hit = imports & FORBIDDEN_MODULES
        if "apps" in imports:
            source = path.read_text(encoding="utf-8")
            if "apps.ml" in source:
                hit = hit | {"apps.ml"}
        if hit:
            offenders[str(path.relative_to(_PACKAGE_ROOT))] = hit
    assert offenders == {}, f"nhập mô-đun cấm: {offenders}"
