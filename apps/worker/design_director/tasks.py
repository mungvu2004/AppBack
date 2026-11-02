"""Task `design.director.run`: sinh concept nội thất cho một lượt `queued` (AID-01).

Luồng: `claim` (0 dòng = giao lặp, no-op J06) → nạp mọi tầng của dự án (tài liệu + ảnh trang bản vẽ
đang dùng), mẫu thư viện đã công bố kèm hồ sơ `profiles.jsonl` + ảnh xem trước → `run.run_concept`
trong luồng phụ → `finish`; lỗi có mã → `fail`. Lỗi khác (DB, kho) → `define_task` thử lại rồi
`on_failed` ghi `DESIGN_DIRECTOR_FAILED`. Session ngắn, không giữ khi chạm kho hay gọi AI (K22).
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from pathlib import Path
from typing import Final

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.design_director.state import DESIGN_DIRECTOR_FAILED, DESIGN_DIRECTOR_OUTPUT_INVALID, fail
from apps.api.spatial_read.codec import DocumentCorruptError
from apps.api.spatial_read.documents import EMPTY_LAYER, load_documents
from apps.worker.design_director.run import DesignDirectorError, DesignInputs, LevelInput, direct_concept
from packages.core.clock import Clock, SystemClock
from packages.db.engine import session_scope, worker_sessionmaker
from packages.db.models.drawings import DrawingRow
from packages.db.models.floors import FloorRow
from packages.db.models.library import LibraryItemRow
from packages.domain.design_director.profiles import Profile, parse_profiles
from packages.genai import create_genai, get_genai_settings
from packages.messaging import define_task, runner
from packages.messaging.payloads.design_director import DESIGN_DIRECTOR_TASK, DesignConceptPayload
from packages.storage.port import ObjectStorage, read_all_capped

__all__ = ["fail_design_concept", "load_inputs", "run_design_concept"]

_log: Final = logging.getLogger(__name__)

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
DEFAULT_PROFILES_PATH: Final = Path("packages/domain/library/profiles.jsonl")
IMAGE_MAX_BYTES: Final = 30 * 1024 * 1024
"""Ảnh trang/ảnh xem trước lớn hơn bị bỏ (AI vẫn chạy, chỉ thiếu ảnh đó)."""
_CODES: Final = frozenset({DESIGN_DIRECTOR_FAILED, DESIGN_DIRECTOR_OUTPUT_INVALID})


class DesignDirectorWorkerSettings(BaseSettings):
    """`DESIGN_DIRECTOR_PROFILES_PATH`: hồ sơ mẫu jsonl; đường tương đối tính từ gốc repo."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    design_director_profiles_path: Path = DEFAULT_PROFILES_PATH


class _SkipImageError(Exception):
    """Ảnh vắng hoặc quá trần: bỏ ảnh, không hỏng lượt."""


async def _image(storage: ObjectStorage, key: str | None) -> bytes | None:
    """Bytes của object ảnh; vắng/quá trần → `None`. Lỗi kho khác lan ra để thử lại."""
    if key is None:
        return None
    try:
        return await read_all_capped(
            storage, key, max_bytes=IMAGE_MAX_BYTES, too_large=_SkipImageError, on_missing=_SkipImageError
        )
    except _SkipImageError:
        _log.warning("design_director_image_skipped", extra={"key": key})
        return None


def read_profiles(path: Path, published: set[str]) -> tuple[Profile, ...]:
    """Hồ sơ của mẫu đã công bố; thiếu tệp → `()` (concept chỉ có sơn/sàn)."""
    full = path if path.is_absolute() else REPO_ROOT / path
    try:
        text = full.read_text(encoding="utf-8")
    except FileNotFoundError:
        _log.warning("design_director_profiles_missing", extra={"path": str(full)})
        return ()
    parsed = parse_profiles(text.splitlines())
    return tuple(p for p in parsed.profiles if p.id in published)


async def load_inputs(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    project_id: str,
    style_id: str | None,
    *,
    profiles_path: Path,
) -> DesignInputs:
    """Mọi tầng còn sống (theo thứ tự tầng) + mẫu đã công bố chưa gỡ. Tài liệu hỏng → `DESIGN_DIRECTOR_FAILED`."""
    floors_stmt = (
        select(FloorRow.pk, FloorRow.level_id, FloorRow.name, DrawingRow.page_key)
        .outerjoin(DrawingRow, DrawingRow.floor_pk == FloorRow.pk)
        .where(FloorRow.project_id == project_id, FloorRow.deleted_at.is_(None))
        .order_by(FloorRow.floor_order, FloorRow.pk)
    )
    items_stmt = select(LibraryItemRow.id, LibraryItemRow.preview_key).where(
        LibraryItemRow.published_at.is_not(None), LibraryItemRow.retired_at.is_(None)
    )
    async with sessionmaker() as db:
        floors = (await db.execute(floors_stmt)).all()
        try:
            docs = await load_documents(db, [f.pk for f in floors])
        except DocumentCorruptError:
            raise DesignDirectorError(DESIGN_DIRECTOR_FAILED) from None
        items = dict((await db.execute(items_stmt)).tuples().all())
    levels = [
        LevelInput(
            f.level_id, f.name, docs[f.pk].layer if f.pk in docs else EMPTY_LAYER, await _image(storage, f.page_key)
        )
        for f in floors
    ]
    profiles = await asyncio.to_thread(read_profiles, profiles_path, set(items))
    previews = {p.id: data for p in profiles if (data := await _image(storage, items[p.id])) is not None}
    return DesignInputs(project_id, style_id, tuple(levels), profiles, previews)


async def fail_design_concept(sessionmaker: async_sessionmaker[AsyncSession], *, concept_id: str, code: str) -> None:
    """Chốt `failed`; mã chung của `define_task` (`TASK_TIMEOUT`, `RETRY_EXHAUSTED`…) → `DESIGN_DIRECTOR_FAILED`."""
    async with session_scope(sessionmaker) as db:
        await fail(db, concept_id, code if code in _CODES else DESIGN_DIRECTOR_FAILED)


def open_storage(clock: Clock) -> ObjectStorage:
    """Kho thật của tiến trình worker, nhập trễ (khuôn `apps/worker/lighting_bake/tasks.py`)."""
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), None, clock)


def _on_failed(payload: DesignConceptPayload, code: str) -> None:
    """`on_failed` của `define_task`: đánh `failed` trên vòng sự kiện dùng chung."""
    _log.error("design_director_failed", extra={"concept_id": payload.concept_id, "code": code})
    runner().run(fail_design_concept(worker_sessionmaker(), concept_id=payload.concept_id, code=code))


@define_task(name=DESIGN_DIRECTOR_TASK, payload=DesignConceptPayload, on_failed=_on_failed)
async def run_design_concept(payload: DesignConceptPayload) -> None:
    """Hàm task mỏng: dựng tài nguyên thật rồi gọi lõi `direct_concept`."""
    maker = worker_sessionmaker()
    path = DesignDirectorWorkerSettings().design_director_profiles_path
    load = partial(load_inputs, maker, open_storage(SystemClock()), profiles_path=path)
    await direct_concept(maker, concept_id=payload.concept_id, load=load, genai=create_genai(get_genai_settings()))
