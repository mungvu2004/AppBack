"""Helper dùng chung cho mọi test của `apps/api/drawings` (việc D, U, B, J của B2-04).

Ở đây chỉ những thứ **mọi** nhóm test cần: một "sân khấu" người dùng + dự án + tầng, cách
đọc lại một dòng `pipeline_runs` qua session mới, và fixture trả bus đồng bộ về trạng thái
chưa dựng. Luật nghiệp vụ không bao giờ vào file này (R-07).
"""

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.runs import reset_sync_bus_cache
from packages.db.models.auth import User
from packages.db.models.drawings import PipelineRunRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project


@dataclass(frozen=True, slots=True)
class Scene:
    """Người dùng + dự án + tầng đã `flush` — điểm xuất phát của hầu hết test B2-04."""

    user: User
    project: Project
    floor: FloorRow


async def make_scene(db: AsyncSession, *, level_id: str | None = None) -> Scene:
    """Một sân khấu mới; `level_id` cố định khi test cần dựng lại tầng cùng id."""
    user = await make_user(db)
    project = await make_project(db, owner=user)
    floor = await make_floor(db, project=project, level_id=level_id)
    return Scene(user=user, project=project, floor=floor)


async def read_run(db: AsyncSession, run_id: str) -> PipelineRunRow:
    """Dòng `pipeline_runs` đọc lại từ DB — `refresh` **đúng một** dòng.

    Không `expire_all()`: nó cũng hết hạn `scene.project`/`scene.floor`, và lượt nạp lại lười
    của chúng là IO đồng bộ trong hàm async (`MissingGreenlet`).
    """
    row = (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == run_id))).scalar_one()
    await db.refresh(row)
    return row


@pytest.fixture
def sync_bus_reset() -> Iterator[None]:
    """Bus đồng bộ của `runs.py` dựng lười theo tiến trình; Redis của test đổi URL mỗi lượt."""
    reset_sync_bus_cache()
    yield
    reset_sync_bus_cache()
