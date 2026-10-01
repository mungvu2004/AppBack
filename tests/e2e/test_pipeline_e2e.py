"""E2E thật của pipeline (B5-07 [6] "E2E"): ảnh tổng hợp → #5-#7 → #8 tới `completed` → N16/N17/#19.

Dịch vụ thật (K23): Postgres, hai Redis, kho đĩa `local_storage`, Celery nghe bốn hàng
(`pool="solo"`), `ML_BACKEND=fake`. Không `task_always_eager`, không mock DB/Redis/storage/task.
`pipeline_quality` là mảnh cuối của dây (bước `qualityCheck`) nên hai test ở đây chỉ chạy hết tới
`completed` sau khi `feature/b5-07-core` cho `service.py` thật (trước đó `run_quality` ném
`NotImplementedError`, bước `qualityCheck` sẽ `failed`/`INTERNAL`, không tới `completed`).
"""

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator, Callable, Coroutine, Iterator
from pathlib import Path
from typing import Any, Final

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.app import create_app
from apps.api.drawings.progress import LAST_STEP
from apps.api.drawings.tests._upload_helpers import (
    chunk_body,
    chunks_path,
    complete_path,
    init_body,
    init_path,
    progress_path,
    split,
)
from apps.api.project_settings.read import read_settings
from apps.api.projects.summaries import project_rollups
from apps.api.spatial_read.counts import layer_counts, recount_floor
from apps.api.spatial_read.documents import load_document
from apps.api.spatial_write.tests._route_helpers import layer_path as write_layer_path
from apps.api.spatial_write.tests._route_helpers import wire
from apps.ml.runtime.settings import reset_ml_settings_cache
from apps.ml.runtime.tasks_util import reset_infer_context
from apps.worker.pipeline_build.tasks import reset_build_context
from apps.worker.pipeline_orchestrate.pins import load_pins
from apps.worker.pipeline_orchestrate.tasks import reset_orchestrate_storage
from apps.worker.pipeline_persist.tasks import reset_persist_storage
from apps.worker.pipeline_quality.tasks import reset_quality_storage
from packages.core.clock import SystemClock
from packages.core.settings import get_core_settings, reset_settings_cache
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.models.auth import User
from packages.db.models.drawings import PipelineRunRow
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.messaging.celery_app import QUEUES
from packages.messaging.redis import streams_redis
from packages.messaging.schedules import discover_submodules
from packages.messaging.streams import EventBus, upload_stream
from packages.ml_contracts.synthetic import render_plan
from packages.storage.keys import run_artifact
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.auth import SignedIn, sign_in
from packages.testing.fixtures.messaging import WorkerFactory
from packages.vision.preprocess.geometry import find_frame
from packages.vision.preprocess.raster import load_raster
from packages.vision.preprocess.types import DEFAULT_MAX_PIXELS

_log = logging.getLogger(__name__)

POLL_INTERVAL_S: Final = 0.2
POLL_TIMEOUT_S: Final = 120.0
"""Trần hỏi #8 (spec [6]); không mang mã case nên không gắn `perf` (luật 14)."""

SEED: Final = 7
RESCALE_SEED: Final = 5
"""Seed khác `SEED` có `mm_per_px` khác (12.5 so với 10.0) và `find_frame` cũng `None` (tra ở phút đầu)."""


def test_synthetic_plan_has_no_frame() -> None:
    """Ảnh `render_plan` không có khung nhận được (B2-05a/B5-01) — tiền đề của mọi e2e dưới đây.

    Khác `None` → đường nắn tự động của B2-05a cắt dấu nhận của bộ giả: dừng cả tệp, ghi Nợ
    B2-05a/B5-01, không tự sửa (spec [6] "việc làm đầu tiên").
    """
    plan = render_plan(SEED)
    quad = find_frame(load_raster(plan.image_png, max_pixels=DEFAULT_MAX_PIXELS))
    assert quad is None, quad


@pytest_asyncio.fixture(loop_scope="function")
async def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Môi trường một tiến trình duy nhất cho cả app thật và task thật: cùng DB, cùng kho đĩa.

    Khuôn `apps/worker/pipeline_persist/tests/test_persist_runtime.py::process_env` cộng
    `ML_BACKEND=fake` (B5-01): task tự đọc biến môi trường trên vòng sự kiện của chính nó, nên
    mọi thứ phải nằm trong `monkeypatch.setenv`, không truyền fixture object vào task.
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-pipeline-e2e-01")
    monkeypatch.delenv("SECRET_KEY_PREVIOUS", raising=False)
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_S", "10")
    monkeypatch.setenv("METRICS_PORT", "0")
    monkeypatch.setenv("ML_BACKEND", "fake")
    caches = (
        reset_settings_cache,
        reset_database_settings_cache,
        reset_storage_settings_cache,
        reset_ml_settings_cache,
    )
    task_resets = (
        reset_build_context,
        reset_orchestrate_storage,
        reset_persist_storage,
        reset_quality_storage,
        reset_infer_context,
    )
    for reset in caches:
        reset()
    for reset in task_resets:
        reset()
    yield
    for reset in task_resets:
        reset()
    for reset in caches:
        reset()


@pytest.fixture
def e2e_app(process_env: None) -> FastAPI:
    """App thật, verifier thật — dựng **sau** `process_env` để đọc đúng biến môi trường."""
    return create_app(get_core_settings())


@pytest_asyncio.fixture(loop_scope="function")
async def e2e_client(e2e_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Client ASGI của `e2e_app`, có chạy `lifespan`."""
    async with (
        e2e_app.router.lifespan_context(e2e_app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=e2e_app), base_url="https://appback.test") as client,
    ):
        yield client


@pytest.fixture
def e2e_worker(process_env: None, celery_worker_factory: WorkerFactory) -> Iterator[None]:
    """Worker Celery thật nghe cả bốn hàng (`QUEUES`), dựng sau `process_env` để thấy đúng môi trường.

    Dò task đúng cách `apps/worker/celery_main.py` và `apps/ml/celery_main.py` làm khi lên thật
    (K23 ngoại lệ cho e2e: được nhập `apps.ml`) — không liệt tay từng module, dễ sót một cái như
    `pipeline_steps.tasks` (khai `pipeline.orchestrate.step_done`).
    """
    discover_submodules("apps.worker", "tasks")
    discover_submodules("apps.ml", "tasks")

    with celery_worker_factory(QUEUES):
        yield


async def on_db[T](db_url: str, work: Callable[[async_sessionmaker[AsyncSession]], Coroutine[Any, Any, T]]) -> T:
    """Dựng một engine riêng trên vòng hiện tại (cùng vòng của test async), dùng rồi `dispose`.

    Test ở đây là `async def` (khác khuôn đồng bộ của `pipeline_persist/tests/test_persist_runtime.py`
    dùng `asyncio.run`), nên engine dựng ngay trên vòng của test — không cần vòng riêng.
    """
    engine = create_engine(DatabaseSettings(database_url=db_url))
    try:
        return await work(create_sessionmaker(engine))
    finally:
        await engine.dispose()


async def _engineer_scene(maker: async_sessionmaker[AsyncSession]) -> tuple[str, str, str, int]:
    """Người `engineer` thành viên dự án, một tầng; trả `(user_id, project_id, level_id, floor_pk)`."""
    async with maker() as db:
        user = await make_user(db)
        project = await make_project(db, owner=user)
        floor = await make_floor(db, project=project)
        await db.commit()
        return user.id, project.id, floor.level_id, floor.pk


async def _user_row(maker: async_sessionmaker[AsyncSession], user_id: str) -> User:
    """Đọc lại `User` để `sign_in` có bản ghi còn sống trên vòng hiện tại."""
    async with maker() as db:
        return (await db.execute(select(User).where(User.id == user_id))).scalar_one()


async def _upload_png(
    client: httpx.AsyncClient, headers: dict[str, str], project_id: str, level_id: str, data: bytes
) -> tuple[str, httpx.Response]:
    """#5 → #6 (mọi khúc) → #7 bằng client `signed_in`; trả `(upload_id, response của #7)`."""
    body = init_body(project_id, level_id, size_bytes=len(data))
    init = await client.post(init_path(project_id, level_id), json=body, headers=headers)
    assert init.status_code == 200, init.text
    upload_id = str(init.json()["id"])
    path = chunks_path(project_id, upload_id)
    for index, piece in enumerate(split(data)):
        response = await client.post(path, json=chunk_body(piece, index), headers=headers)
        assert response.status_code == 200, response.text
    complete = await client.post(complete_path(project_id, upload_id), json={"uploadId": upload_id}, headers=headers)
    return upload_id, complete


async def _poll_progress(
    client: httpx.AsyncClient, project_id: str, upload_id: str, headers: dict[str, str]
) -> dict[str, Any]:
    """Hỏi #8 mỗi `POLL_INTERVAL_S` tới `completed`/`failed`, trần `POLL_TIMEOUT_S` (spec [6])."""
    deadline = time.monotonic() + POLL_TIMEOUT_S
    wire: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = await client.get(progress_path(project_id, upload_id), headers=headers)
        assert response.status_code == 200, response.text
        wire = response.json()
        if wire["status"] in ("completed", "failed"):
            return wire
        await asyncio.sleep(POLL_INTERVAL_S)
    _log.info("Progress cuối trước trần %ss: %s", POLL_TIMEOUT_S, wire)
    pytest.fail(f"#8 không tới completed/failed trong {POLL_TIMEOUT_S}s; Progress cuối: {wire}")


async def _stream_progress_percents(upload_id: str) -> list[int]:
    """`progressPercent` của mọi sự kiện trên `upload_stream(upload_id)`, theo thứ tự id (spec [6])."""
    client = streams_redis()
    try:
        events = await EventBus(client).read_after(upload_stream(upload_id), "0-0")
    finally:
        await client.aclose()
    return [int(str(event.data["progressPercent"])) for event in events]


async def test_spatial_read_layer__C01_pipeline(
    db_url: str,
    e2e_worker: None,
    e2e_client: httpx.AsyncClient,
) -> None:
    """Ảnh tổng hợp seed 7 → pipeline thật tới `qualityCheck` → N16, N17, #19, `quality.json` (spec [6])."""
    start = time.monotonic()
    user_id, project_id, level_id, floor_pk = await on_db(db_url, _engineer_scene)
    user = await on_db(db_url, lambda maker: _user_row(maker, user_id))
    signed: SignedIn = await sign_in(e2e_client, user)
    headers = signed.headers

    plan = render_plan(SEED)
    upload_id, complete = await _upload_png(e2e_client, headers, project_id, level_id, plan.image_png)
    assert complete.status_code == 200, complete.text

    progress = await _poll_progress(e2e_client, project_id, upload_id, headers)
    assert progress["status"] == "completed", progress
    assert progress["progressPercent"] == 100
    assert progress["step"] == LAST_STEP == "qualityCheck"
    assert "endedAt" in progress

    percents = await _stream_progress_percents(upload_id)
    assert percents == sorted(percents), percents

    layer_response = await e2e_client.get(
        f"/api/projects/{project_id}/floors/{level_id}/spatial/layer", headers=headers
    )
    assert layer_response.status_code == 200, layer_response.text
    body = layer_response.json()
    assert body.get("scaleStatus") == "unresolved"
    walls, openings, rooms, furniture = (
        body["layer"]["walls"],
        body["layer"]["openings"],
        body["layer"]["rooms"],
        body["layer"]["furniture"],
    )
    n_walls, n_doors, n_furniture, n_rooms = (
        len(walls),
        sum(1 for o in openings if o["kind"] == "door"),
        len(furniture),
        len(rooms),
    )
    scale = body["level"]["scaleMillimetresPerPixel"]
    scale_drift = abs(scale - plan.mm_per_px) / plan.mm_per_px
    _log.info(
        "e2e C01_pipeline: tường=%d (plan=%d) ô mở(door)=%d đồ đạc=%d phòng=%d"
        " scale=%.6f plan.mm_per_px=%.6f lệch=%.4f%% thời gian=%.1fs",
        n_walls,
        len(plan.walls),
        n_doors,
        n_furniture,
        n_rooms,
        scale,
        plan.mm_per_px,
        scale_drift * 100,
        time.monotonic() - start,
    )
    assert n_walls >= len(plan.walls) * 0.5
    assert n_doors >= 1
    assert n_furniture >= 1
    assert n_rooms >= 1
    assert scale_drift <= 0.05
    for item in (*walls, *openings, *rooms, *furniture):
        assert item["source"] == "ai", item
        assert item["reviewed"] is False, item

    notifications = await e2e_client.get("/api/notifications", headers=headers)
    assert notifications.status_code == 200, notifications.text
    ai_completed_walls = [n for n in notifications.json() if n["kind"] == "aiCompleted" and n["place"] == "walls"]
    assert len(ai_completed_walls) == 1, ai_completed_walls
    assert ai_completed_walls[0]["floorId"] == level_id

    versions = await e2e_client.get(f"/api/projects/{project_id}/versions?floorId={level_id}", headers=headers)
    assert versions.status_code == 200, versions.text
    assert len(versions.json()["items"]) == 2, versions.json()
    assert all(v["creatorId"] == "system:pipeline" for v in versions.json()["items"])

    async def _server_side(maker: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
        """Số liệu phía DB không qua HTTP: tài liệu, ngưỡng, rollup §2 N1, `recount_floor` lần hai."""
        async with maker() as db:
            doc = await load_document(db, floor_pk)
            assert doc is not None
            threshold = (await read_settings(db, project_id)).confidence_threshold
            rollups = await project_rollups(db, [project_id])
            counts = layer_counts(doc.layer)
            recounted_again = await recount_floor(db, floor_pk=floor_pk, clock=SystemClock())
            return {
                "doc": doc,
                "threshold": threshold,
                "rollups": rollups,
                "counts": counts,
                "recounted_again": recounted_again,
            }

    server = await on_db(db_url, _server_side)
    assert server["recounted_again"] is False
    rollup, counts = server["rollups"][project_id], server["counts"]
    assert rollup.walls_total == counts.walls_total
    assert rollup.walls_reviewed == counts.walls_reviewed
    assert rollup.area_m2 == counts.area_m2

    threshold = float(server["threshold"])

    def _low(items: list[dict[str, Any]]) -> int:
        return sum(
            1 for item in items if item["source"] == "ai" and not item["reviewed"] and item["confidence"] < threshold
        )

    low_confidence = {
        "walls": _low(walls),
        "openings": _low(openings),
        "rooms": _low(rooms),
        "furniture": _low(furniture),
    }

    run_id = await on_db(db_url, lambda maker: _run_id_of(maker, upload_id))
    store = LocalDiskStorage(Path(os.environ["STORAGE_LOCAL_ROOT"]), SystemClock(), "https://appback.test/objects")
    key = run_artifact(project_id, level_id, upload_id, run_id, "qualityCheck", "quality.json")
    quality = json.loads(b"".join([chunk async for chunk in store.open_read(key)]))
    _log.info("quality.json: %s", quality)
    assert quality["lowConfidence"] == low_confidence
    assert quality["runId"] == run_id
    assert quality["confidenceThreshold"] == threshold

    pins = await on_db(db_url, lambda maker: _load_pins(maker, run_id))
    assert pins is not None
    assert set(pins.used.keys()) == {"wallSegmentation", "openingAndFurnitureDetection", "dimensionReading"}
    assert pins.persisted_revision == server["doc"].revision
    assert time.monotonic() - start < 120.0


async def test_pipeline_e2e_rerun_keeps_reviewed(
    db_url: str,
    e2e_worker: None,
    e2e_client: httpx.AsyncClient,
) -> None:
    """K21: duyệt một tường (#35) rồi tải lại cùng ảnh → lượt hai `completed`, tường đã duyệt nguyên."""
    start = time.monotonic()
    user_id, project_id, level_id, floor_pk = await on_db(db_url, _engineer_scene)
    user = await on_db(db_url, lambda maker: _user_row(maker, user_id))
    signed: SignedIn = await sign_in(e2e_client, user)
    headers = signed.headers

    plan = render_plan(SEED)
    upload_id, complete = await _upload_png(e2e_client, headers, project_id, level_id, plan.image_png)
    assert complete.status_code == 200, complete.text
    first = await _poll_progress(e2e_client, project_id, upload_id, headers)
    assert first["status"] == "completed", first

    async def _read_doc(maker: async_sessionmaker[AsyncSession]) -> Any:
        async with maker() as db:
            doc = await load_document(db, floor_pk)
            assert doc is not None
            return doc

    doc_one = await on_db(db_url, _read_doc)
    assert doc_one.layer.walls, "pipeline phải sinh ít nhất một tường để duyệt"
    target = doc_one.layer.walls[0]
    reviewed_wall = target.model_copy(update={"reviewed": True, "source": "human"})
    layer_wire = {
        "walls": [wire(reviewed_wall if w.id == target.id else w) for w in doc_one.layer.walls],
        "openings": [wire(o) for o in doc_one.layer.openings],
        "rooms": [wire(r) for r in doc_one.layer.rooms],
        "furniture": [wire(f) for f in doc_one.layer.furniture],
    }
    put_response = await e2e_client.put(
        write_layer_path(project_id, level_id),
        json={"baseVersion": doc_one.revision, "body": {"layer": layer_wire}},
        headers=headers,
    )
    assert put_response.status_code == 200, put_response.text
    revision_after_review = put_response.json()["revision"]

    upload_id_2, complete_2 = await _upload_png(e2e_client, headers, project_id, level_id, plan.image_png)
    assert complete_2.status_code == 200, complete_2.text
    second = await _poll_progress(e2e_client, project_id, upload_id_2, headers)
    assert second["status"] == "completed", second

    doc_two = await on_db(db_url, _read_doc)
    kept = next(w for w in doc_two.layer.walls if w.id == target.id)
    assert kept == reviewed_wall, (kept, reviewed_wall)
    assert len(doc_two.layer.walls) == len(doc_one.layer.walls)

    versions = await e2e_client.get(f"/api/projects/{project_id}/versions?floorId={level_id}", headers=headers)
    assert versions.status_code == 200, versions.text
    version_items = versions.json()["items"]
    before_rerun = next(v for v in version_items if v["floorRevision"] == revision_after_review)
    assert before_rerun["floorRevision"] == revision_after_review

    _log.info(
        "e2e rerun_keeps_reviewed: revision tr.duyệt=%d revision sau lượt 2=%d tường giữ nguyên=%s thời gian=%.1fs",
        revision_after_review,
        doc_two.revision,
        kept.id,
        time.monotonic() - start,
    )
    assert time.monotonic() - start < 120.0


async def test_pipeline_e2e_rerun_rescales_page(
    db_url: str,
    e2e_worker: None,
    e2e_client: httpx.AsyncClient,
) -> None:
    """Ca tỉ lệ gắn trang (spec [6]): #35 hiệu chỉnh tỉ lệ rồi tải trang khác → tỉ lệ cũ không áp.

    Tỉ lệ gắn với **trang** đang có, không với tầng: sau khi người hiệu chỉnh tỉ lệ ở #35 (nguồn
    `human`), tải một trang pipeline khác (seed `mm_per_px` khác) phải quay lại tỉ lệ pipeline của
    trang mới (`scaleStatus: unresolved`), không giữ tỉ lệ người đặt của trang cũ (HOP-DONG-MOI §4
    "Tỉ lệ gắn với trang").
    """
    start = time.monotonic()
    user_id, project_id, level_id, floor_pk = await on_db(db_url, _engineer_scene)
    user = await on_db(db_url, lambda maker: _user_row(maker, user_id))
    signed: SignedIn = await sign_in(e2e_client, user)
    headers = signed.headers

    plan_one = render_plan(SEED)
    upload_id, complete = await _upload_png(e2e_client, headers, project_id, level_id, plan_one.image_png)
    assert complete.status_code == 200, complete.text
    first = await _poll_progress(e2e_client, project_id, upload_id, headers)
    assert first["status"] == "completed", first

    async def _read_doc(maker: async_sessionmaker[AsyncSession]) -> Any:
        async with maker() as db:
            doc = await load_document(db, floor_pk)
            assert doc is not None
            return doc

    doc_one = await on_db(db_url, _read_doc)
    assert doc_one.layer.walls, "pipeline phải sinh ít nhất một tường để duyệt"
    target = doc_one.layer.walls[0]
    reviewed_wall = target.model_copy(update={"reviewed": True, "source": "human"})
    layer_wire = {
        "walls": [wire(reviewed_wall if w.id == target.id else w) for w in doc_one.layer.walls],
        "openings": [wire(o) for o in doc_one.layer.openings],
        "rooms": [wire(r) for r in doc_one.layer.rooms],
        "furniture": [wire(f) for f in doc_one.layer.furniture],
    }
    human_scale = plan_one.mm_per_px * 2
    put_response = await e2e_client.put(
        write_layer_path(project_id, level_id),
        json={"baseVersion": doc_one.revision, "body": {"layer": layer_wire, "scaleMillimetresPerPixel": human_scale}},
        headers=headers,
    )
    assert put_response.status_code == 200, put_response.text

    plan_two = render_plan(RESCALE_SEED)
    assert plan_two.mm_per_px != plan_one.mm_per_px, "seed hiệu chỉnh phải khác mm_per_px với seed đầu"
    upload_id_2, complete_2 = await _upload_png(e2e_client, headers, project_id, level_id, plan_two.image_png)
    assert complete_2.status_code == 200, complete_2.text
    second = await _poll_progress(e2e_client, project_id, upload_id_2, headers)
    assert second["status"] == "completed", second

    layer_response = await e2e_client.get(
        f"/api/projects/{project_id}/floors/{level_id}/spatial/layer", headers=headers
    )
    assert layer_response.status_code == 200, layer_response.text
    body = layer_response.json()
    assert body.get("scaleStatus") == "unresolved"
    scale = body["level"]["scaleMillimetresPerPixel"]
    drift = abs(scale - plan_two.mm_per_px) / plan_two.mm_per_px

    doc_two = await on_db(db_url, _read_doc)
    assert doc_two.scale_source == "pipeline"
    kept = next(w for w in doc_two.layer.walls if w.id == target.id)
    assert kept == reviewed_wall, (kept, reviewed_wall)

    _log.info(
        "e2e rerun_rescales_page: mm_per_px seed=%d %.3f -> seed=%d %.3f;"
        " scale đọc lại=%.3f lệch=%.4f%% thời gian=%.1fs",
        SEED,
        plan_one.mm_per_px,
        RESCALE_SEED,
        plan_two.mm_per_px,
        scale,
        drift * 100,
        time.monotonic() - start,
    )
    assert drift <= 0.05
    assert time.monotonic() - start < 120.0


async def _run_id_of(maker: async_sessionmaker[AsyncSession], upload_id: str) -> str:
    """`PipelineRunRow.id` của lượt mở cho `upload_id` (duy nhất: #7 chỉ mở một lượt mỗi lượt tải)."""
    async with maker() as db:
        return (await db.execute(select(PipelineRunRow.id).where(PipelineRunRow.upload_id == upload_id))).scalar_one()


async def _load_pins(maker: async_sessionmaker[AsyncSession], run_id: str) -> Any:
    async with maker() as db:
        return await load_pins(db, run_id)
