"""C14 của N22: hai admin song song với cùng base → một 200, một 409, revision tăng đúng 1 (B3-05 [8])."""

import asyncio

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.rules.tests.support import put_config, replace_body, seed_project
from packages.testing.factories.auth import make_user


@pytest.mark.parametrize("base", [0, 1])
async def test_rules_replace_config__C14(api_client: httpx.AsyncClient, db_session: AsyncSession, base: int) -> None:
    """Hai admin cùng base (0 = chưa có dòng, 1 = đã có) gọi song song: chỉ một bên thắng."""
    first = await make_user(db_session, role="admin")
    second = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=first, members=[second])
    if base == 1:
        assert (await put_config(api_client, project.id, first, replace_body(0))).status_code == 200

    results = await asyncio.gather(
        put_config(api_client, project.id, first, replace_body(base, {"DOOR-WIDTH": {"severity": "critical"}})),
        put_config(api_client, project.id, second, replace_body(base, {"DOOR-WIDTH": {"severity": "warning"}})),
    )
    codes = [response.status_code for response in results]
    final = (await db_session.execute(text("SELECT revision FROM rule_configs"))).scalar_one()
    print(f"C14 rules_replace_config base={base}: status = {codes}, revision cuối = {final}")
    assert sorted(codes) == [200, 409]
    assert final == base + 1
    loser = next(response for response in results if response.status_code == 409)
    assert loser.json()["currentVersion"] == base + 1
    assert loser.json()["remoteChanges"] == []
