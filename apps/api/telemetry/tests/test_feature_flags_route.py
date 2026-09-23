"""`GET /api/feature-flags` — #9 (B7-01 [8]: C01, C17, "Theo phiên")."""

import json
from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.settings import reset_auth_settings_cache
from apps.api.auth.tests.support import wait_until
from apps.api.core.auth import Principal, Role
from apps.api.telemetry.settings import reset_telemetry_settings_cache
from packages.core.ids import new_id
from packages.db.models.auth import User
from packages.observability.metrics import render, reset_registry
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.auth import SignedIn, SignIn
from packages.testing.fixtures.clock import FakeClock

PATH = "/api/feature-flags"

FIVE_KEYS_ONE_ROLE = json.dumps(
    {
        "scene.instanced-walls": True,
        "scene.soft-shadows": False,
        "rules.parallel-run": {"roles": ["admin"]},
        "export.pdf-vector": True,
        "qc.live-collaboration": False,
    }
)
TWO_KEYS = json.dumps({"scene.instanced-walls": True, "export.pdf-vector": False})


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("FEATURE_FLAGS", raising=False)
    reset_telemetry_settings_cache()
    yield
    reset_telemetry_settings_cache()


def _principal(fake_clock: FakeClock, role: Role) -> Principal:
    return Principal(user_id=new_id("usr", fake_clock), session_id=f"sid-{role}", role=role)


async def test_telemetry_read_feature_flags__C01(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, fake_clock: FakeClock
) -> None:
    """C01: 5 khoá cấu hình đủ, một khoá theo vai — `admin` → true, `viewer` → false."""
    monkeypatch.setenv("FEATURE_FLAGS", FIVE_KEYS_ONE_ROLE)
    reset_telemetry_settings_cache()

    admin = await api_client.get(PATH, headers=auth_headers(_principal(fake_clock, "admin")))
    assert admin.status_code == 200
    body = admin.json()
    assert body == {
        "scene.instanced-walls": True,
        "scene.soft-shadows": False,
        "rules.parallel-run": True,
        "export.pdf-vector": True,
        "qc.live-collaboration": False,
    }

    viewer = await api_client.get(PATH, headers=auth_headers(_principal(fake_clock, "viewer")))
    assert viewer.json()["rules.parallel-run"] is False


async def test_telemetry_read_feature_flags__C17_empty(
    api_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """C17: `FEATURE_FLAGS={}` → thân `{}`."""
    response = await api_client.get(PATH, headers=auth_headers(fake_principal))
    assert response.status_code == 200
    assert response.json() == {}


async def test_telemetry_read_feature_flags__C17_two_keys(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, fake_principal: Principal
) -> None:
    monkeypatch.setenv("FEATURE_FLAGS", TWO_KEYS)
    reset_telemetry_settings_cache()
    response = await api_client.get(PATH, headers=auth_headers(fake_principal))
    body = response.json()
    assert body == {"scene.instanced-walls": True, "export.pdf-vector": False}
    assert "null" not in response.text
    assert len(body) == 2


async def test_missing_authorization_is_401(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(PATH)
    assert response.status_code == 401


async def test_response_is_not_cached(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    response = await api_client.get(PATH, headers=auth_headers(fake_principal))
    assert response.headers["cache-control"] == "no-store"


async def test_read_increments_metric(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    reset_registry()
    await api_client.get(PATH, headers=auth_headers(fake_principal))
    await api_client.get(PATH, headers=auth_headers(fake_principal))
    assert "appback_feature_flags_reads_total 2.0" in render()


async def test_role_change_applies_within_the_session_cache_ttl(
    auth_client: httpx.AsyncClient,
    signed_in: SignIn,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`auth_app` + `signed_in` (verifier thật), `AUTH_PRINCIPAL_CACHE_TTL_S=1` như C25 của B1-01."""
    monkeypatch.setenv("AUTH_PRINCIPAL_CACHE_TTL_S", "1")
    monkeypatch.setenv("FEATURE_FLAGS", json.dumps({"scene.instanced-walls": {"roles": ["admin"]}}))
    reset_auth_settings_cache()
    reset_telemetry_settings_cache()

    user = await make_user(db_session, role="admin")
    me: SignedIn = await signed_in(user)
    first = await auth_client.get(PATH, headers=me.headers)
    assert first.json()["scene.instanced-walls"] is True

    await db_session.execute(update(User).where(User.id == user.id).values(role="viewer"))
    await db_session.commit()

    async def demoted() -> bool:
        response = await auth_client.get(PATH, headers=me.headers)
        return response.json()["scene.instanced-walls"] is False

    await wait_until(demoted, timeout_s=1.5)
