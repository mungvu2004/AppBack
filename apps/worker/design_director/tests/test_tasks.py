"""Task `run_design_concept`: lõi `direct_concept` + bộ nạp thật trên Postgres và kho local (J01, J06).

Chỉ cổng AI là giả (`FakeGenAI`). Như `apps/worker/lighting_bake/tests/test_tasks.py`: việc `define_task`
đổi lỗi thành mã là hợp đồng B0-05; ở đây kiểm lõi và `fail_design_concept` (thân của `on_failed`).
"""

import json
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.design_director import state
from apps.worker.design_director import tasks
from apps.worker.design_director.run import DesignInputs, direct_concept
from apps.worker.design_director.tasks import fail_design_concept, load_inputs, read_profiles
from apps.worker.design_director.tests.test_run import concept_answer
from packages.genai import GENAI_UNAVAILABLE, GenAIError
from packages.messaging.tasks import TASK_TIMEOUT
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.design_concept import make_design_concept
from packages.testing.factories.floors import make_floor
from packages.testing.factories.library import make_library_item
from packages.testing.factories.projects import make_project
from packages.testing.factories.spatial import make_floor_document
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.genai import FakeGenAI

Maker = async_sessionmaker[AsyncSession]

PROFILE: dict[str, Any] = {
    "sizeMm": {"w": 400, "d": 700, "h": 800},
    "type": "toilet",
    "license": "CC0",
    "qc": {"ok": True},
}


async def _seed(maker: Maker, storage: LocalDiskStorage, clock: FakeClock, tmp_path: Path) -> tuple[str, Path]:
    """Dự án hai tầng (một có tài liệu), ba mẫu (công bố / gỡ / chưa công bố), tệp hồ sơ; trả (dự án, tệp)."""
    async with maker() as db:
        project = await make_project(db, owner=await make_user(db))
        floor = await make_floor(db, project=project, name="Tầng 1")
        await make_floor(db, project=project, name="Tầng 2")
        await make_floor_document(db, floor_pk=floor.pk, clock=clock)
        await db.commit()
        await make_library_item(db, storage, id="wc-pub")
        await make_library_item(db, storage, id="wc-retired", retired=True)
        await make_library_item(db, storage, id="wc-draft", published=False)
    path = tmp_path / "profiles.jsonl"
    lines = [json.dumps({**PROFILE, "id": i}) for i in ("wc-pub", "wc-retired", "wc-draft")]
    path.write_text("\n".join([*lines, "{hỏng"]), encoding="utf-8")
    return project.id, path


async def _concept(maker: Maker, project_id: str, **kw: Any) -> str:
    """Một lượt `queued`."""
    async with maker() as db:
        return (await make_design_concept(db, project_id=project_id, **kw)).id


async def _row(maker: Maker, concept_id: str) -> dict[str, Any]:
    """Dòng `design_concepts` đọc lại."""
    async with maker() as db:
        found = await db.execute(text("SELECT * FROM design_concepts WHERE id = :id"), {"id": concept_id})
        return dict(found.mappings().one())


async def test_load_inputs_reads_floors_library_profiles(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, tmp_path: Path
) -> None:
    """Hai tầng theo thứ tự, chỉ mẫu đã công bố chưa gỡ có hồ sơ + ảnh xem trước."""
    project_id, path = await _seed(db_sessionmaker, local_storage, fake_clock, tmp_path)
    loaded = await load_inputs(db_sessionmaker, local_storage, project_id, "japandi", profiles_path=path)
    assert [lv.name for lv in loaded.levels] == ["Tầng 1", "Tầng 2"]
    assert all(lv.page_image is None and not lv.layer.rooms for lv in loaded.levels)
    assert [p.id for p in loaded.profiles] == ["wc-pub"]
    assert list(loaded.previews) == ["wc-pub"]
    assert loaded.previews["wc-pub"][:4] == b"\x89PNG"


async def test_run_design_concept__J01(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, tmp_path: Path
) -> None:
    """queued → running → done với `result`/`usage`; dự án không phòng nên chỉ một lượt gọi AI."""
    project_id, path = await _seed(db_sessionmaker, local_storage, fake_clock, tmp_path)
    concept_id = await _concept(db_sessionmaker, project_id, style_id="rustic")
    genai = FakeGenAI().queue(concept_answer())
    load = partial(load_inputs, db_sessionmaker, local_storage, profiles_path=path)
    await direct_concept(db_sessionmaker, concept_id=concept_id, load=load, genai=genai)
    row = await _row(db_sessionmaker, concept_id)
    assert (row["status"], row["style_id"], row["failure_code"]) == ("done", "rustic", None)
    assert row["result"]["baseStyle"] == "go-am"
    assert row["result"]["additions"] == []
    assert row["usage"]["calls"] == 1
    assert len(genai.calls) == 1


async def test_run_design_concept__J06(db_sessionmaker: Maker, tmp_path: Path) -> None:
    """Giao lặp sau khi xong: `claim` trả None, không gọi AI, không đổi dòng."""
    async with db_sessionmaker() as db:
        project_id = (await make_project(db, owner=await make_user(db))).id
        await db.commit()
    concept_id = await _concept(db_sessionmaker, project_id, status="done")

    async def load(project: str, style: str | None) -> DesignInputs:
        raise AssertionError("không được nạp")

    genai = FakeGenAI()
    await direct_concept(db_sessionmaker, concept_id=concept_id, load=load, genai=genai)
    assert genai.calls == []
    assert (await _row(db_sessionmaker, concept_id))["status"] == "done"


async def test_failures_write_codes(db_sessionmaker: Maker, tmp_path: Path) -> None:
    """Thiếu cổng AI / `GenAIError` → FAILED; lượt bị đóng giữa chừng → `finish` bỏ qua, giữ `failed`."""
    async with db_sessionmaker() as db:
        project_id = (await make_project(db, owner=await make_user(db))).id
        await db.commit()

    async def load(project: str, style: str | None) -> DesignInputs:
        return DesignInputs(project, style, ())

    no_ai = await _concept(db_sessionmaker, project_id, style_id="japandi")
    await direct_concept(db_sessionmaker, concept_id=no_ai, load=load, genai=None)
    ai_err = await _concept(db_sessionmaker, project_id, style_id="japandi")
    genai = FakeGenAI().queue(GenAIError(GENAI_UNAVAILABLE))
    await direct_concept(db_sessionmaker, concept_id=ai_err, load=load, genai=genai)
    for concept_id in (no_ai, ai_err):
        row = await _row(db_sessionmaker, concept_id)
        assert (row["status"], row["failure_code"]) == ("failed", state.DESIGN_DIRECTOR_FAILED)

    stalled = await _concept(db_sessionmaker, project_id, style_id="japandi")

    async def load_then_stall(project: str, style: str | None) -> DesignInputs:
        async with db_sessionmaker() as db:
            await state.fail(db, stalled, state.DESIGN_DIRECTOR_STALLED)
            await db.commit()
        return await load(project, style)

    genai = FakeGenAI().queue(concept_answer())
    await direct_concept(db_sessionmaker, concept_id=stalled, load=load_then_stall, genai=genai)
    row = await _row(db_sessionmaker, stalled)
    assert (row["status"], row["failure_code"]) == ("failed", state.DESIGN_DIRECTOR_STALLED)


async def test_fail_design_concept_maps_codes(db_sessionmaker: Maker) -> None:
    """Mã chung của `define_task` → FAILED; mã của module giữ nguyên."""
    async with db_sessionmaker() as db:
        project_id = (await make_project(db, owner=await make_user(db))).id
        await db.commit()
    timeout = await _concept(db_sessionmaker, project_id)
    invalid = await _concept(db_sessionmaker, project_id)
    await fail_design_concept(db_sessionmaker, concept_id=timeout, code=TASK_TIMEOUT)
    await fail_design_concept(db_sessionmaker, concept_id=invalid, code=state.DESIGN_DIRECTOR_OUTPUT_INVALID)
    assert (await _row(db_sessionmaker, timeout))["failure_code"] == state.DESIGN_DIRECTOR_FAILED
    assert (await _row(db_sessionmaker, invalid))["failure_code"] == state.DESIGN_DIRECTOR_OUTPUT_INVALID


async def test_images_and_profiles_edge_cases(
    local_storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ảnh vắng / quá trần → None; tệp hồ sơ thiếu → không ứng viên; đường tương đối tính từ gốc repo."""
    await local_storage.put("x/page.png", b"12345", content_type="image/png", max_bytes=5)
    assert await tasks._image(local_storage, None) is None
    assert await tasks._image(local_storage, "x/missing.png") is None
    assert await tasks._image(local_storage, "x/page.png") == b"12345"
    monkeypatch.setattr(tasks, "IMAGE_MAX_BYTES", 2)
    assert await tasks._image(local_storage, "x/page.png") is None
    assert read_profiles(tmp_path / "none.jsonl", {"a"}) == ()
    assert read_profiles(Path("no/such/profiles.jsonl"), {"a"}) == ()
    assert tasks.DesignDirectorWorkerSettings().design_director_profiles_path == tasks.DEFAULT_PROFILES_PATH
