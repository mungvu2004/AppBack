"""N19 — phục hồi về bản có mục đã duyệt là duyệt lại chúng, nên cũng đòi `qc.approve` (NFR-02).

Trạng thái mẫu: `revision 1` một tường người đã duyệt (bản v1), `revision 2` cùng tường đó bỏ duyệt.
Phục hồi v1 đặt lại `reviewed=True` cho tường — đúng một lượt duyệt đi qua đường khác #35.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.spatial_read.documents import load_document
from apps.api.spatial_write.tests._helpers import make_wall, simple_layer
from apps.api.versions.tests._helpers import versions_of
from apps.api.versions.tests._route_helpers import Stage, commit_snap, make_stage, put_layer, restore
from packages.domain.spatial import SpatialLayer
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.permissions import assert_forbidden


def _human_layer(stage: Stage, *, reviewed: bool) -> SpatialLayer:
    """Lớp một tường người vẽ, duyệt hay chưa theo `reviewed`."""
    return simple_layer(stage.level_id, walls=(make_wall(stage.level_id, source="human", reviewed=reviewed),))


async def _reviewed_then_unreviewed(db: AsyncSession, stage: Stage, clock: FakeClock) -> str:
    """Ghi tường đã duyệt (chụp bản v1) rồi bỏ duyệt nó; trả id bản v1."""
    await put_layer(db, stage, clock, _human_layer(stage, reviewed=True), base=0)
    first = (await commit_snap(db, stage, clock)).id
    assert await put_layer(db, stage, clock, _human_layer(stage, reviewed=False), base=1) == 2
    return first


@pytest.mark.usefixtures("engineer_without_qc_approve")
async def test_versions_restore_version__reapprove_without_qc_approve(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Có `layer.edit`, thiếu `qc.approve` → 403 thân W7; tầng vẫn ở `revision 2`, tường chưa duyệt.

    Bản "trước" (`create_version`) chạy trước `write_layer` ném 403: giao dịch rollback cả nó,
    nên số phiên bản của tầng không đổi.
    """
    stage = await make_stage(db_session)
    first = await _reviewed_then_unreviewed(db_session, stage, fake_clock)
    versions_before = len(await versions_of(db_sessionmaker, stage.floor.pk))

    response = await restore(api_client, stage, first, 2)

    assert_forbidden(response)
    assert len(await versions_of(db_sessionmaker, stage.floor.pk)) == versions_before
    await db_session.commit()
    document = await load_document(db_session, stage.floor.pk)
    assert document is not None
    assert (document.revision, document.layer.walls[0].reviewed) == (2, False)


async def test_versions_restore_version__reapprove_with_qc_approve(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Engineer theo ma trận thật có `qc.approve` → 201, tường được duyệt lại."""
    stage = await make_stage(db_session)
    first = await _reviewed_then_unreviewed(db_session, stage, fake_clock)

    response = await restore(api_client, stage, first, 2)

    assert response.status_code == 201, response.text
    await db_session.commit()
    document = await load_document(db_session, stage.floor.pk)
    assert document is not None
    assert document.layer.walls[0].reviewed is True
