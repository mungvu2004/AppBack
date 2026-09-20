"""Sổ quyền, `Origin`, `Principal` và dependency tài nguyên của khung."""

from typing import Final

import httpx
import pytest

from apps.api.core.auth import (
    DenyAllTokenVerifier,
    FakeTokenVerifier,
    Principal,
    current_principal,
    fake_token,
)
from apps.api.core.permissions import ANY_ROLE, permission_dependency, permission_key_of, registered
from apps.api.core.tests.sample import deny_sample, sample_app, sample_client
from packages.core.errors import AppError
from packages.core.ids import new_id
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.storage import PUBLIC_BASE_URL

__all__ = ["sample_app", "sample_client"]

FOREIGN_ORIGIN: Final = "https://ke-la.example"


class _FakeState:
    """`request.state` rỗng — đúng cảnh route công khai."""


class _FakeRequest:
    state = _FakeState()


def test_permission_dependency_exposes_key() -> None:
    """`Operation.permission_key` đọc đúng thuộc tính này (CASE §2.3)."""
    assert permission_key_of(deny_sample) == "sample.manage"
    assert deny_sample in registered()


def test_permission_key_of_plain_callable_is_none() -> None:
    def plain() -> None: ...

    assert permission_key_of(plain) is None


def test_permission_dependency_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="không được rỗng"):
        permission_dependency("")


def test_any_role_is_the_bind_dash() -> None:
    """Route bảo vệ không có cổng quyền nào mang khoá `—` đúng như cột BE-BIND."""
    assert ANY_ROLE == "—"


def test_principal_rejects_bad_user_id() -> None:
    with pytest.raises(ValueError, match="usr_"):
        Principal(user_id="nguoi-dung", session_id="sid", role="admin")


def test_principal_rejects_empty_session(fake_clock: FakeClock) -> None:
    with pytest.raises(ValueError, match="session_id"):
        Principal(user_id=new_id("usr", fake_clock), session_id="", role="admin")


def test_principal_rejects_unknown_role(fake_clock: FakeClock) -> None:
    with pytest.raises(ValueError, match="vai lạ"):
        Principal(user_id=new_id("usr", fake_clock), session_id="sid", role="owner")  # type: ignore[arg-type]  # kiểm đúng vai lạ


async def test_fake_verifier_reads_token(fake_principal: Principal) -> None:
    """Token mẫu giải đúng về `Principal` đã ký."""
    verified = await FakeTokenVerifier().verify(fake_token(fake_principal), _FakeRequest())  # type: ignore[arg-type]  # verifier mẫu không dùng request
    assert verified == fake_principal


@pytest.mark.parametrize("token", ["rac", "fake:usr_x:sid:admin", "fake:a:b:c:d", "khac:1:2:3"])
async def test_fake_verifier_rejects_bad_tokens(token: str) -> None:
    """C05: chuỗi rác, id sai mẫu, sai số phần đều là 401 `UNAUTHENTICATED`."""
    with pytest.raises(AppError, match="UNAUTHENTICATED"):
        await FakeTokenVerifier().verify(token, _FakeRequest())  # type: ignore[arg-type]  # như trên


async def test_deny_all_verifier_rejects_everything() -> None:
    with pytest.raises(AppError, match="UNAUTHENTICATED"):
        await DenyAllTokenVerifier().verify("bat-ky", _FakeRequest())  # type: ignore[arg-type]  # như trên


def test_current_principal_needs_protected_route() -> None:
    """Gọi trên route công khai là lỗi lập trình, phải lộ ra ngay."""
    with pytest.raises(RuntimeError, match="route được bảo vệ"):
        current_principal(_FakeRequest())  # type: ignore[arg-type]  # request giả đủ cho hàm này


async def test_require_origin_needs_matching_origin(
    sample_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """C24: thiếu hoặc lệch `Origin` ở endpoint ghi là 403 `ORIGIN_MISMATCH`."""
    headers = auth_headers(fake_principal)
    missing = await sample_client.post("/api/sample/origin", json={"name": "a"}, headers=headers)
    foreign = await sample_client.post(
        "/api/sample/origin", json={"name": "a"}, headers={**headers, "Origin": FOREIGN_ORIGIN}
    )
    assert missing.status_code == foreign.status_code == 403
    assert missing.json()["code"] == "ORIGIN_MISMATCH"


async def test_require_origin_accepts_own_origin(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    response = await sample_client.post(
        "/api/sample/origin",
        json={"name": "a"},
        headers={**auth_headers(fake_principal), "Origin": PUBLIC_BASE_URL},
    )
    assert response.status_code == 200


async def test_reject_foreign_origin_allows_missing_header(
    sample_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """K31: GET cùng origin không gửi `Origin`; chỉ lệch mới chặn."""
    headers = auth_headers(fake_principal)
    assert (await sample_client.get("/api/sample/origin", headers=headers)).status_code == 200
    foreign = await sample_client.get("/api/sample/origin", headers={**headers, "Origin": FOREIGN_ORIGIN})
    assert foreign.status_code == 403


async def test_deps_resolve_from_app_state(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Mọi dependency của `deps.py` lấy đúng tài nguyên mà `lifespan` đã gắn."""
    response = await sample_client.get("/api/sample/deps", headers=auth_headers(fake_principal))
    assert response.status_code == 200
    body = response.json()
    assert body["userId"] == fake_principal.user_id
    assert body["bus"] == "EventBus"
    assert body["storage"] == "LocalDiskStorage"
    assert body["baseUrl"] == PUBLIC_BASE_URL
    assert body["now"].endswith("Z")
