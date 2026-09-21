"""Test case chung, tham số hoá theo route **được bảo vệ** của app thật (CASE §2.1).

Hôm nay repo chưa có route được bảo vệ nào, nên tập tham số rỗng và pytest báo
"empty parameter set" — `case_gate` chấp nhận đúng một lý do bỏ qua này (BE-00 §12).
Prompt sau thêm route là các case dưới đây tự áp cho nó, không ai phải sửa file này.

Máy móc của từng case được chứng minh bằng app thử ở `test_routing.py`,
`test_idempotency.py` và `test_middleware.py`.
"""

import re
from typing import Final
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from apps.api.core.app import create_app
from apps.api.core.auth import Principal, TokenVerifier
from apps.api.core.idempotency import LEASE, TTL, request_digest
from apps.api.core.openapi import Operation, operations
from apps.api.core.permissions import registered
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, SESSION_REVOKED
from packages.core.settings import get_core_settings
from packages.db.errors import translate_db_error
from packages.db.models.idempotency import STATE_IN_PROGRESS, IdempotencyRecord
from packages.testing.fixtures.api import auth_headers, make_api_client
from packages.testing.fixtures.clock import FakeClock

IDEMPOTENCY_KEY: Final = "khoa-chung-cho-case"
ULID: Final = "01JABCDEFGHJKMNPQRSTVWXYZ0"
"""Thân ULID hợp lệ (Crockford base32 HOA, 26 ký tự) cho mọi id mẫu (W4)."""

# Giá trị mẫu cho mọi tên tham số đường đang dùng trong BE-BIND (khối [8] của B0-06).
PATH_VALUES: Final[dict[str, str]] = {
    "project_id": f"prj_{ULID}",
    "upload_id": f"upl_{ULID}",
    "version_id": f"ver_{ULID}",
    "notification_id": f"ntf_{ULID}",
    "user_id": f"usr_{ULID}",
    "model_version_id": f"mdl_{ULID}",
    "dataset_id": f"dst_{ULID}",
    "job_id": f"job_{ULID}",
    "floor_id": "L-ABCDEFGHIJ",
    "measurement_id": "MS-0001",
    "item_id": "muc-thu-vien",
    "family": "wallSegmentation",
    "token": "token-mau-cua-case-chung",
}

BAD_TOKENS: Final = (
    "chuoi-rac",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c3JfeCJ9.chu-ky-ngau-nhien",
    f"fake:usr_{ULID}:sid:owner",
    "",
)

_PARAM_RE: Final = re.compile(r"\{([^}]+)\}")


def _protected() -> list[Operation]:
    """Thao tác được bảo vệ của app thật — tập tham số của case chung."""
    return [operation for operation in operations() if operation.protected]


def _idempotent() -> list[Operation]:
    """Thao tác được bảo vệ có idempotency — tập tham số của C10, C22."""
    return [operation for operation in _protected() if operation.idempotency != "off"]


def _url(operation: Operation) -> str:
    """Đường thật của một thao tác; tham số lạ làm test hỏng và **nêu tên** nó."""

    def value(match: re.Match[str]) -> str:
        """Giá trị mẫu của một tham số đường; tham số lạ làm test hỏng."""
        name = match.group(1)
        if name not in PATH_VALUES:
            raise AssertionError(f"{operation.op}: chưa có giá trị mẫu cho tham số đường {name!r}")
        return PATH_VALUES[name]

    return _PARAM_RE.sub(value, operation.path)


async def _send(client: httpx.AsyncClient, operation: Operation, **kwargs: object) -> httpx.Response:
    """Gửi đúng method của thao tác tới đường thật của nó."""
    return await client.request(operation.method, _url(operation), **kwargs)  # type: ignore[arg-type]  # kwargs của httpx


def _grant_everything(app: FastAPI) -> None:
    """Mọi dependency quyền chạy **trước** bước nhận việc, nên C10/C22 phải qua được chúng."""
    for dependency in registered():
        app.dependency_overrides[dependency] = lambda: None


class _BrokenVerifier:
    """C13: verifier ném đúng lỗi đã dịch từ Postgres mất kết nối."""

    async def verify(self, token: str, request: object) -> Principal:
        """Ném 503 đã dịch, như khi Postgres mất kết nối."""
        translated = translate_db_error(OperationalError("SELECT 1", {}, Exception("mất kết nối")))
        raise translated if translated is not None else DEPENDENCY_UNAVAILABLE.error(retry_after=5)


class _RevokedVerifier:
    """C25: phiên đã thu hồi → 401 `SESSION_REVOKED` (W10, K30)."""

    async def verify(self, token: str, request: object) -> Principal:
        """Ném 401 `SESSION_REVOKED`, như khi phiên đã bị thu hồi."""
        raise SESSION_REVOKED.error()


def _app_with(verifier: TokenVerifier, clock: FakeClock) -> FastAPI:
    """App thật với verifier tiêm vào — để dựng C13, C25."""
    return create_app(get_core_settings(), token_verifier=verifier, clock=clock)


@pytest.mark.case("C04")
@pytest.mark.parametrize("operation", _protected(), ids=lambda item: item.op)
async def test_common__C04(operation: Operation, api_client: httpx.AsyncClient) -> None:
    """Không có token → 401 `UNAUTHENTICATED`."""
    response = await _send(api_client, operation)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.case("C05")
@pytest.mark.parametrize("operation", _protected(), ids=lambda item: item.op)
@pytest.mark.parametrize("token", BAD_TOKENS)
async def test_common__C05(operation: Operation, token: str, api_client: httpx.AsyncClient) -> None:
    """Token rác, chữ ký lạ, vai lạ, rỗng → 401 `UNAUTHENTICATED`."""
    response = await _send(api_client, operation, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.case("C12")
@pytest.mark.parametrize("operation", _protected(), ids=lambda item: item.op)
async def test_common__C12(operation: Operation, api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Thân vượt trần → 413 `PAYLOAD_TOO_LARGE` trước khi handler chạy."""
    response = await _send(
        api_client,
        operation,
        headers={**auth_headers(fake_principal), "Content-Type": "application/json"},
        content=b"a" * (operation.body_limit + 1),
    )
    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.case("C13")
@pytest.mark.parametrize("operation", _protected(), ids=lambda item: item.op)
async def test_common__C13(
    operation: Operation, api_env: None, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Phụ thuộc hỏng → 503 kèm `Retry-After`, thân không lộ stack."""
    async with make_api_client(_app_with(_BrokenVerifier(), fake_clock)) as client:
        response = await _send(client, operation, headers=auth_headers(fake_principal))
    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    assert "Retry-After" in response.headers
    assert "Traceback" not in response.text


@pytest.mark.case("C25")
@pytest.mark.parametrize("operation", _protected(), ids=lambda item: item.op)
async def test_common__C25(
    operation: Operation, api_env: None, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Phiên đã thu hồi → 401 `SESSION_REVOKED`."""
    async with make_api_client(_app_with(_RevokedVerifier(), fake_clock)) as client:
        response = await _send(client, operation, headers=auth_headers(fake_principal))
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"


@pytest.mark.case("C22")
@pytest.mark.parametrize("operation", _idempotent(), ids=lambda item: item.op)
async def test_common__C22(
    operation: Operation, api_app: FastAPI, api_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """Lượt trước còn hạn thuê → 503 `IDEMPOTENCY_IN_PROGRESS` + `Retry-After: 1`."""
    _grant_everything(api_app)
    headers = {**auth_headers(fake_principal), "Idempotency-Key": IDEMPOTENCY_KEY}
    await _seed_in_progress(api_app, operation, fake_principal)
    response = await _send(api_client, operation, headers=headers, json={})
    assert response.status_code == 503
    assert response.json()["code"] == "IDEMPOTENCY_IN_PROGRESS"
    assert response.headers["Retry-After"] == "1"


@pytest.mark.case("C10")
@pytest.mark.parametrize("operation", _idempotent(), ids=lambda item: item.op)
async def test_common__C10(
    operation: Operation, api_app: FastAPI, api_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """Lượt lặp cùng thân trả lại response cũ; thân khác → 422 `IDEMPOTENCY_KEY_REUSED`."""
    _grant_everything(api_app)
    headers = {**auth_headers(fake_principal), "Idempotency-Key": IDEMPOTENCY_KEY}
    first = await _send(api_client, operation, headers=headers, json={})
    replay = await _send(api_client, operation, headers=headers, json={})
    assert (replay.status_code, replay.content) == (first.status_code, first.content)

    reused = await _send(api_client, operation, headers=headers, json={"khac": True})
    assert reused.status_code == 422
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


async def _seed_in_progress(app: FastAPI, operation: Operation, principal: Principal) -> None:
    """Dựng sẵn một dòng `in_progress` còn hạn cho đúng request mà C22 sắp gửi."""
    now = app.state.clock.now()
    async with app.state.sessionmaker() as session:
        session.add(
            IdempotencyRecord(
                user_id=principal.user_id,
                method=operation.method,
                route_template=operation.path,
                key=IDEMPOTENCY_KEY,
                request_hash=request_digest(operation.method, _url(operation), "", b"{}"),
                state=STATE_IN_PROGRESS,
                claim_token=uuid4(),
                lease_until=now + LEASE,
                expires_at=now + TTL,
            )
        )
        await session.commit()
