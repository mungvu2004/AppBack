"""C14 của N6: hai người ghi song song với cùng base → một 200, một 409, revision tăng đúng 1 (B2-02 [8])."""

import asyncio

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.project_settings.read import read_settings
from apps.api.project_settings.tests.support import put_settings, replace_body, seed_project
from packages.testing.factories.auth import make_user


@pytest.mark.parametrize("base", [0, 1])
async def test_settings_replace_settings__C14(
    api_client: httpx.AsyncClient, db_session: AsyncSession, base: int
) -> None:
    """Hai kỹ sư cùng base (0 = chưa có dòng, 1 = đã có) gọi song song: chỉ một bên thắng."""
    first = await make_user(db_session, role="engineer")
    second = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=first, members=[second])
    if base == 1:
        assert (await put_settings(api_client, project.id, first, replace_body(0))).status_code == 200

    results = await asyncio.gather(
        put_settings(api_client, project.id, first, replace_body(base, snapToleranceMm=41)),
        put_settings(api_client, project.id, second, replace_body(base, snapToleranceMm=42)),
    )
    statuses = sorted(response.status_code for response in results)
    final = (await read_settings(db_session, project.id)).revision
    codes = [r.status_code for r in results]
    print(f"C14 settings_replace_settings base={base}: status = {codes}, revision cuối = {final}")
    assert statuses == [200, 409]
    assert final == base + 1
    loser = next(r for r in results if r.status_code == 409)
    assert loser.json()["currentVersion"] == base + 1
