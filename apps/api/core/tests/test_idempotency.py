"""Idempotency của `AppRoute` trên Postgres thật (BE-00 §7, C10, C22, K23)."""

import asyncio
from typing import Final

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import Response

from apps.api.core.auth import Principal
from apps.api.core.idempotency import (
    NO_STORE_STATUSES,
    Claim,
    check_key,
    request_digest,
    storable,
)
from apps.api.core.tests.sample import (
    after_commit_marks,
    clear_after_commit_marks,
    deny_sample,
    grant_stub,
    sample_app,
    sample_client,
    sample_row_ids,
)
from packages.core.errors import AppError
from packages.db.models.idempotency import STATE_COMPLETED, IdempotencyRecord
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock

__all__ = ["clear_after_commit_marks", "sample_app", "sample_client"]

KEY: Final = "khoa-idempotency-01"
SETTLE_S: Final = 0.05


def _headers(principal: Principal, key: str = KEY) -> dict[str, str]:
    """Header đủ cho một lượt ghi có idempotency.

    Phải là **cùng** một `Principal` giữa hai lượt: khoá idempotency có phạm vi
    `(user_id, method, route_template, key)` (BE-00 §7).
    """
    return {**auth_headers(principal), "Idempotency-Key": key}


async def _records(maker: async_sessionmaker[AsyncSession]) -> list[tuple[str, int | None, str]]:
    """(state, status_code, request_hash) của mọi dòng — đọc sẵn để session đóng vẫn dùng được."""
    async with maker() as session:
        rows = await session.execute(
            select(IdempotencyRecord.state, IdempotencyRecord.status_code, IdempotencyRecord.request_hash).order_by(
                IdempotencyRecord.id
            )
        )
        return [(str(state), status, str(digest)) for state, status, digest in rows.all()]


async def _count(maker: async_sessionmaker[AsyncSession]) -> int:
    async with maker() as session:
        return int((await session.execute(select(func.count()).select_from(IdempotencyRecord))).scalar_one())


# ---------------------------------------------------------------------------
# Hàm thuần
# ---------------------------------------------------------------------------


def test_check_key_rejects_short_key() -> None:
    """Khoá ngắn hơn 8 ký tự là 422 `VALIDATION`, không phải "coi như không có"."""
    with pytest.raises(AppError) as caught:
        check_key("ngan")
    assert caught.value.code.code == "VALIDATION"
    assert caught.value.params["field"] == "idempotencyKey"


def test_check_key_accepts_pattern() -> None:
    assert check_key("A-b_0123456789") == "A-b_0123456789"


def test_request_digest_sorts_query() -> None:
    """Query cùng nội dung khác thứ tự phải ra cùng hash."""
    left = request_digest("POST", "/api/x", "b=2&a=1", b"{}")
    right = request_digest("POST", "/api/x", "a=1&b=2", b"{}")
    assert left == right


def test_request_digest_separates_path_and_body() -> None:
    """Đường thật nằm trong hash: cùng khoá gửi sang dự án khác là request khác."""
    assert request_digest("POST", "/api/a", "", b"{}") != request_digest("POST", "/api/b", "", b"{}")
    assert request_digest("POST", "/api/a", "", b"1") != request_digest("POST", "/api/a", "", b"2")


@pytest.mark.parametrize("status", [*sorted(NO_STORE_STATUSES), 500, 503])
def test_storable_is_false_for_unstorable_status(status: int) -> None:
    """401/408/429 và mọi 5xx không được lưu (BE-00 §7)."""
    assert storable(Response(status_code=status)) is False


@pytest.mark.parametrize("status", [200, 204, 409, 422])
def test_storable_is_true_for_stored_status(status: int) -> None:
    assert storable(Response(status_code=status)) is True


# ---------------------------------------------------------------------------
# Đường HTTP
# ---------------------------------------------------------------------------


async def test_replay_returns_stored_response(
    sample_client: httpx.AsyncClient,
    sample_app: FastAPI,
    fake_principal: Principal,
    clear_after_commit_marks: None,
) -> None:
    """C10: lượt lặp cùng thân trả lại **đúng** response cũ, handler không chạy lại."""
    headers = _headers(fake_principal)
    first = await sample_client.post("/api/sample/after-commit", json={"name": "a"}, headers=headers)
    second = await sample_client.post("/api/sample/after-commit", json={"name": "a"}, headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert second.headers["content-type"] == first.headers["content-type"]
    assert after_commit_marks == ["a"], "replay không được chạy lại callback sau commit"
    assert await sample_row_ids(sample_app.state.sessionmaker) == ["a"]


async def test_same_key_other_path_is_reused(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Cùng khoá, cùng thân, khác `project_id` → 422 `IDEMPOTENCY_KEY_REUSED`."""
    headers = _headers(fake_principal)
    body = {"name": "a"}
    first = await sample_client.post(
        "/api/sample/projects/prj-1/items", json={**body, "projectId": "prj-1"}, headers=headers
    )
    second = await sample_client.post(
        "/api/sample/projects/prj-2/items", json={**body, "projectId": "prj-2"}, headers=headers
    )
    assert first.status_code == 200
    assert second.status_code == 422
    assert second.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_same_key_other_body_is_reused(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Cùng khoá mà thân khác → 422, không bao giờ trả lại response của thân cũ."""
    headers = _headers(fake_principal)
    await sample_client.post("/api/sample/items", json={"name": "a"}, headers=headers)
    second = await sample_client.post("/api/sample/items", json={"name": "b"}, headers=headers)
    assert second.status_code == 422
    assert second.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_parallel_same_key_gives_one_in_progress(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """C22: lượt thứ hai khi lượt đầu chưa xong → 503 `IDEMPOTENCY_IN_PROGRESS`, `Retry-After: 1`."""
    sample_app.state.gate = asyncio.Event()
    sample_app.dependency_overrides[deny_sample] = grant_stub
    headers = _headers(fake_principal)

    running = asyncio.create_task(sample_client.post("/api/sample/gated", json={"name": "a"}, headers=headers))
    await asyncio.sleep(SETTLE_S)
    second = await sample_client.post("/api/sample/gated", json={"name": "a"}, headers=headers)
    sample_app.state.gate.set()
    first = await running

    assert second.status_code == 503
    assert second.json()["code"] == "IDEMPOTENCY_IN_PROGRESS"
    assert second.headers["Retry-After"] == "1"
    assert first.status_code == 200


async def test_expired_lease_is_taken_over(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal, fake_clock: FakeClock
) -> None:
    """Hết hạn thuê: lượt mới chiếm dòng, lượt cũ hoàn tất 0 dòng → rollback + 503."""
    from datetime import timedelta

    sample_app.state.gate = asyncio.Event()
    sample_app.dependency_overrides[deny_sample] = grant_stub
    headers = _headers(fake_principal)

    old = asyncio.create_task(sample_client.post("/api/sample/gated", json={"name": "a"}, headers=headers))
    await asyncio.sleep(SETTLE_S)
    fake_clock.advance(timedelta(minutes=1))
    new = asyncio.create_task(sample_client.post("/api/sample/gated", json={"name": "a"}, headers=headers))
    await asyncio.sleep(SETTLE_S)
    sample_app.state.gate.set()
    old_response, new_response = await old, await new

    assert new_response.status_code == 200
    assert old_response.status_code == 503
    assert old_response.json()["code"] == "IDEMPOTENCY_IN_PROGRESS"


async def test_permission_error_leaves_no_record(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Dependency quyền ném 404 **trước** bước nhận việc → không tạo dòng nào."""
    response = await sample_client.post("/api/sample/guarded", json={"name": "a"}, headers=_headers(fake_principal))
    assert response.status_code == 404
    assert response.json()["resource"] == "project"
    assert await _count(sample_app.state.sessionmaker) == 0


async def test_completed_record_is_not_replayed_when_permission_fails(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Dòng `completed` cùng hash mà quyền nay 404 → 404, không replay, dòng giữ nguyên."""
    sample_app.dependency_overrides[deny_sample] = grant_stub
    headers = _headers(fake_principal)
    first = await sample_client.post("/api/sample/guarded", json={"name": "a"}, headers=headers)
    assert first.status_code == 200

    sample_app.dependency_overrides.clear()
    second = await sample_client.post("/api/sample/guarded", json={"name": "a"}, headers=headers)
    assert second.status_code == 404

    records = await _records(sample_app.state.sessionmaker)
    assert len(records) == 1
    assert records[0][0] == STATE_COMPLETED
    assert records[0][1] == 200


async def test_returned_conflict_is_completed_and_committed(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Handler **trả** 409 → dòng `completed`, ghi DB của handler vẫn được commit."""
    response = await sample_client.post("/api/sample/conflict", json={"name": "x"}, headers=_headers(fake_principal))
    assert response.status_code == 409
    records = await _records(sample_app.state.sessionmaker)
    assert [record[0] for record in records] == [STATE_COMPLETED]
    assert records[0][1] == 409
    assert await sample_row_ids(sample_app.state.sessionmaker) == ["x"]

    replay = await sample_client.post("/api/sample/conflict", json={"name": "x"}, headers=_headers(fake_principal))
    assert replay.status_code == 409
    assert await sample_row_ids(sample_app.state.sessionmaker) == ["x"], "replay không được ghi lần hai"


async def test_validation_error_leaves_no_in_progress_row(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Thân sai kiểu (422 của Pydantic) → dòng nhận việc bị xoá."""
    response = await sample_client.post("/api/sample/items", json={"name": 7}, headers=_headers(fake_principal))
    assert response.status_code == 422
    assert await _count(sample_app.state.sessionmaker) == 0


async def test_server_error_allows_retry(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Handler 500 → không lưu; lượt sau cùng khoá vẫn chạy lại chứ không 422."""
    headers = _headers(fake_principal)
    first = await sample_client.post("/api/sample/boom", json={"name": "a"}, headers=headers)
    assert first.status_code == 500
    assert await _count(sample_app.state.sessionmaker) == 0

    second = await sample_client.post("/api/sample/boom", json={"name": "khac"}, headers=headers)
    assert second.status_code == 500, "thân khác vẫn phải chạy lại, không phải 422 REUSED"


async def test_public_route_ignores_idempotency_header(sample_client: httpx.AsyncClient, sample_app: FastAPI) -> None:
    """Route công khai không nhận việc và không đọc header (không có phạm vi ẩn danh)."""
    response = await sample_client.get("/api/sample/public", headers={"Idempotency-Key": KEY})
    assert response.status_code == 200
    assert await _count(sample_app.state.sessionmaker) == 0


async def test_bad_key_is_422(sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal) -> None:
    """Header sai mẫu → 422 `VALIDATION`, không âm thầm bỏ qua idempotency."""
    response = await sample_client.post(
        "/api/sample/items", json={"name": "a"}, headers=_headers(fake_principal, key="x")
    )
    assert response.status_code == 422
    assert response.json()["field"] == "idempotencyKey"
    assert await _count(sample_app.state.sessionmaker) == 0


async def test_without_header_no_record(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Không gửi `Idempotency-Key` thì không có dòng nào (FE chỉ gửi cho PUT và lượt idempotent)."""
    response = await sample_client.post("/api/sample/items", json={"name": "a"}, headers=auth_headers(fake_principal))
    assert response.status_code == 200
    assert await _count(sample_app.state.sessionmaker) == 0


def test_claim_is_frozen() -> None:
    """`Claim` là dữ liệu bất biến: không ai đổi token giữa chừng."""
    from uuid import uuid4

    claim = Claim(record_id=1, token=uuid4())
    with pytest.raises(AttributeError):
        claim.record_id = 2  # type: ignore[misc]  # kiểm đúng tính bất biến của dataclass frozen
