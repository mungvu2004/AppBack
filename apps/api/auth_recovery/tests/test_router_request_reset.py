"""`POST /api/auth/password-reset` (N8, B1-03 [2], [8]; CASE loại C)."""

import statistics
import time
from datetime import timedelta
from typing import Final

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth_recovery import router
from apps.api.auth_recovery.settings import get_recovery_settings, reset_recovery_settings_cache
from packages.db.models.auth_recovery import OneTimeToken
from packages.messaging.redis import broker_redis_sync
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.auth import ORIGIN
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

pytestmark = pytest.mark.usefixtures("api_env")

PATH: Final = "/api/auth/password-reset"
QUEUE: Final = "default"
TIMING_ROUNDS: Final = 20
MAX_MEDIAN_GAP_S: Final = 0.050


async def _request_reset(client: httpx.AsyncClient, email: str) -> httpx.Response:
    """Một lượt `POST /api/auth/password-reset` đúng `Origin`."""
    return await client.post(PATH, json={"email": email}, headers=ORIGIN)


async def _active_tokens(db: AsyncSession, user_id: str) -> list[OneTimeToken]:
    rows = await db.execute(
        select(OneTimeToken).where(
            OneTimeToken.user_id == user_id,
            OneTimeToken.purpose == "password_reset",
            OneTimeToken.used_at.is_(None),
            OneTimeToken.superseded_at.is_(None),
        )
    )
    return list(rows.scalars())


def _raise_ip_limit(monkeypatch: pytest.MonkeyPatch, limit: int) -> None:
    monkeypatch.setenv("RECOVERY_IP_LIMIT", str(limit))
    reset_recovery_settings_cache()


async def test_auth_request_password_reset__C01(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đúng: 204 thân rỗng, một token `password_reset` được tạo, đúng một task gửi thư."""
    broker = broker_redis_sync()
    broker.delete(QUEUE)
    user = await make_user(db_session)
    response = await _request_reset(auth_client, user.email)
    assert response.status_code == 204
    assert response.content == b""
    tokens = await _active_tokens(db_session, user.id)
    assert len(tokens) == 1
    assert tokens[0].expires_at == fake_clock.now() + timedelta(minutes=get_recovery_settings().password_reset_ttl_min)
    assert len(queued_payloads(broker, QUEUE)) == 1


async def test_auth_request_password_reset__C02(auth_client: httpx.AsyncClient) -> None:
    """Email sai dạng → 422 `field:"email"` (K37)."""
    response = await auth_client.post(PATH, json={"email": "khong-phai-email"}, headers=ORIGIN)
    assert response.status_code == 422
    assert response.json()["field"] == "email"


async def test_auth_request_password_reset__C03(auth_client: httpx.AsyncClient) -> None:
    """Khoá lạ → 422 `VALIDATION` (`PasswordResetRequestBody` strict)."""
    response = await auth_client.post(PATH, json={"email": "ai-do@example.com", "extra": 1}, headers=ORIGIN)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_auth_request_password_reset__C11(auth_client: httpx.AsyncClient) -> None:
    """Vượt `recovery_ip`/900s → 429 kèm `Retry-After` ≤ 10."""
    limit = get_recovery_settings().recovery_ip_limit
    for index in range(limit):
        response = await _request_reset(auth_client, f"khach-{index}@example.com")
        assert response.status_code == 204, index
    blocked = await _request_reset(auth_client, "khach-cuoi@example.com")
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 10


async def test_auth_request_password_reset__C16(auth_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Email khác hoa thường vẫn là một người: cùng một token còn hiệu lực."""
    user = await make_user(db_session, email="Anh.Nguyen@Cty.vn")
    assert (await _request_reset(auth_client, "anh.nguyen@CTY.VN")).status_code == 204
    assert (await _request_reset(auth_client, "  ANH.NGUYEN@cty.vn ")).status_code == 204
    assert len(await _active_tokens(db_session, user.id)) == 1


async def test_auth_request_password_reset__C24(auth_client: httpx.AsyncClient) -> None:
    """Thiếu/lệch `Origin` → 403 `ORIGIN_MISMATCH`, trước cả kiểm thân."""
    body = {"email": "ai-do@example.com"}
    missing = await auth_client.post(PATH, json=body)
    foreign = await auth_client.post(PATH, json=body, headers={"Origin": "https://ke-gian.example"})
    for response in (missing, foreign):
        assert response.status_code == 403
        assert response.json()["code"] == "ORIGIN_MISMATCH"


async def _timed_reset(client: httpx.AsyncClient, email: str) -> tuple[httpx.Response, float]:
    started = time.perf_counter()
    response = await _request_reset(client, email)
    return response, time.perf_counter() - started


async def test_auth_request_password_reset__C27(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chống dò: nhánh `issue` và nhánh không người cùng 204, cùng thân, trung vị lệch < 50 ms, 40/40 là 204.

    NO-144: mỗi vòng đo dựng một người `active` **mới** cho nhánh "known", để vòng đo thật sự rơi
    vào nhánh `issue` (thêm một `UPDATE` + một `INSERT` + `send_task` thật) — dùng lại một người
    cho mọi vòng (bản cũ) làm mọi vòng sau vòng đầu rơi vào cooldown "noop", so PING với PING chứ
    không so `issue` với `ping` như cặp cần đo.
    """
    _raise_ip_limit(monkeypatch, 1000)
    stranger = "chua-tung-co@example.com"
    warm_user = await make_user(db_session)
    await _timed_reset(auth_client, warm_user.email)  # lượt làm ấm
    await _timed_reset(auth_client, stranger)
    known: list[float] = []
    unknown: list[float] = []
    statuses: list[int] = []
    for _ in range(TIMING_ROUNDS):
        fresh_user = await make_user(db_session)
        known_response, known_elapsed = await _timed_reset(auth_client, fresh_user.email)
        unknown_response, unknown_elapsed = await _timed_reset(auth_client, stranger)
        for response in (known_response, unknown_response):
            statuses.append(response.status_code)
            assert response.content == b""
        known.append(known_elapsed)
        unknown.append(unknown_elapsed)
    assert statuses == [204] * (2 * TIMING_ROUNDS)
    gap = abs(statistics.median(known) - statistics.median(unknown))
    assert gap < MAX_MEDIAN_GAP_S


async def test_auth_request_password_reset__C28(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Hai lượt trong cửa sổ cooldown → 204 cả hai, đúng một token, đúng một lượt gửi task."""
    broker = broker_redis_sync()
    broker.delete(QUEUE)
    user = await make_user(db_session)
    first = await _request_reset(auth_client, user.email)
    second = await _request_reset(auth_client, user.email)
    assert (first.status_code, second.status_code) == (204, 204)
    tokens = await _active_tokens(db_session, user.id)
    assert len(tokens) == 1
    assert len(queued_payloads(broker, QUEUE)) == 1

    fake_clock.advance(timedelta(minutes=16))
    third = await _request_reset(auth_client, user.email)
    assert third.status_code == 204
    fresh = await _active_tokens(db_session, user.id)
    assert len(fresh) == 1
    assert fresh[0].id != tokens[0].id
    assert len(queued_payloads(broker, QUEUE)) == 2


@pytest.mark.parametrize("status", ["pending", "disabled"])
async def test_auth_request_password_reset__no_leak_for_unusable_accounts(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, status: str
) -> None:
    """`pending`/`disabled`/không tồn tại → 204, không token nào được tạo."""
    user = await make_user(db_session, status=status)
    response = await _request_reset(auth_client, user.email)
    assert response.status_code == 204
    assert await _active_tokens(db_session, user.id) == []


@pytest.mark.parametrize("status", ["pending", "disabled"])
async def test_auth_request_password_reset__noop_pings_broker_C27(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """Nhánh "noop" (`pending`/`disabled`) vẫn PING sau commit, y hệt nhánh "không người" (C27)."""
    calls: list[None] = []
    monkeypatch.setattr(router, "_ping_broker", lambda: calls.append(None))
    user = await make_user(db_session, status=status)
    response = await _request_reset(auth_client, user.email)
    assert response.status_code == 204
    assert len(calls) == 1


async def test_auth_request_password_reset__cooldown_noop_pings_broker_C27(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nhánh "noop" vì còn trong cooldown vẫn PING sau commit, không chỉ nhánh cấp token (C27)."""
    user = await make_user(db_session)
    assert (await _request_reset(auth_client, user.email)).status_code == 204
    calls: list[None] = []
    monkeypatch.setattr(router, "_ping_broker", lambda: calls.append(None))
    second = await _request_reset(auth_client, user.email)
    assert second.status_code == 204
    assert len(calls) == 1


async def test_auth_request_password_reset__unknown_email_creates_nothing(
    auth_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Email không tồn tại → 204, không có dòng token nào được ghi."""
    response = await _request_reset(auth_client, "khong-ton-tai@example.com")
    assert response.status_code == 204
    assert (await db_session.execute(select(OneTimeToken))).first() is None
