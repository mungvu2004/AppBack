"""Test khói của task thật: đường `run_lighting_bake` → `open_storage` → `_on_failed` → `runner()` (BE-00 §7).

Khuôn `apps/worker/datasets/tests/test_smoke.py`: biến môi trường của tiến trình trỏ sang DB test và
kho local trong `tmp_path`; `BLENDER_BIN=/bin/false` thay Blender (thoát 1) nên lượt hỏng có mã.
"""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from packages.core.settings import reset_settings_cache
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.models.lighting_bake import LightingBakeRow
from packages.db.settings import get_database_settings, reset_database_settings_cache
from packages.messaging.payloads.lighting_bake import LIGHTING_BAKE_INPUT, LIGHTING_BAKE_TASK
from packages.storage.keys import lighting_bake_object, lighting_bake_prefix
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.factories.auth import make_user
from packages.testing.factories.lighting_bake import make_lighting_bake
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.lighting_bake import INPUT_GLB


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Môi trường của tiến trình worker: DB test, kho local `tmp_path/objects`, Blender = `/bin/false`."""
    root = tmp_path / "objects"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(root))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-lighting-bake-01")
    monkeypatch.setenv("BLENDER_BIN", "/bin/false")
    caches = (reset_settings_cache, reset_database_settings_cache, reset_storage_settings_cache)
    for reset in caches:
        reset()
    yield root
    for reset in caches:
        reset()


async def _seed(root: Path) -> tuple[str, str]:
    """Dự án + lượt `queued` + `input.glb` trong DB/kho của tiến trình; trả `(project_id, bake_id)`."""
    maker = create_sessionmaker(create_engine(get_database_settings()))
    try:
        async with maker() as db:
            project = await make_project(db, owner=await make_user(db))
            await db.commit()
            row = await make_lighting_bake(db, project_id=project.id)
            project_id, bake_id = project.id, row.id
    finally:
        await maker.kw["bind"].dispose()
    storage = LocalDiskStorage(root, FakeClock(datetime.now(UTC)), None)
    key = lighting_bake_object(project_id, bake_id, LIGHTING_BAKE_INPUT)
    await storage.put(key, INPUT_GLB, content_type="model/gltf-binary", max_bytes=len(INPUT_GLB) + 1)
    return project_id, bake_id


async def _status(bake_id: str) -> tuple[str, str | None]:
    """`(status, failure_code)` đọc lại từ DB của tiến trình."""
    maker = create_sessionmaker(create_engine(get_database_settings()))
    try:
        async with maker() as db:
            stmt = select(LightingBakeRow.status, LightingBakeRow.failure_code).where(LightingBakeRow.id == bake_id)
            status, code = (await db.execute(stmt)).one()
            return str(status), None if code is None else str(code)
    finally:
        await maker.kw["bind"].dispose()


@pytest.mark.usefixtures("messaging_env")
def test_run_lighting_bake_smoke(celery_test_app: object, process_env: Path) -> None:
    """Blender thoát 1 → `LIGHTING_BAKE_FAILED`, `on_failed` chốt `failed` và xoá tiền tố trên vòng dùng chung."""
    project_id, bake_id = asyncio.run(_seed(process_env))

    result = celery_test_app.tasks[LIGHTING_BAKE_TASK].apply(  # type: ignore[attr-defined]  # `tasks` là mapping động
        args=({"schema_version": 1, "bake_id": bake_id},)
    )
    reset_database_settings_cache()

    assert result.successful()
    assert asyncio.run(_status(bake_id)) == ("failed", "LIGHTING_BAKE_FAILED")
    assert not (process_env / lighting_bake_prefix(project_id, bake_id)).exists() or not any(
        (process_env / lighting_bake_prefix(project_id, bake_id)).iterdir()
    )
