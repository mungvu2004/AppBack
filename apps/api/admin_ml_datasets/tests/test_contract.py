"""Hợp đồng chung của module: quyền, wire model (B6-02 [2], [7]).

- **C07** cho cả bốn `op`: `require_admin` khai ở router nên cổng chạy **trước** endpoint;
- `dataset_out`/`dataset_version_out`: vắng trường thay vì `null` (W2, K02), không cột nội
  bộ nào (K01, `createdBy`/`projectIds`/`requeueCount`/`buildStartedAt`);
- `CreateDatasetIn`/`BuildDatasetVersionIn`: khoá lạ, `projectIds: []` → lỗi validate (C03, C02).
"""

from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.admin_ml_datasets.schemas import (
    BuildDatasetVersionIn,
    CreateDatasetIn,
    dataset_out,
    dataset_version_out,
)
from apps.api.admin_ml_datasets.tests._helpers import WALL, versions_path
from apps.api.core.auth import Principal, fake_token
from apps.api.core.routing import AppRoute
from packages.core.ids import new_id
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.fixtures.clock import FakeClock

_ROUTES: Final[tuple[tuple[str, str, str], ...]] = (
    ("ml_list_datasets", "GET", "/api/admin/ml/datasets"),
    ("ml_create_dataset", "POST", "/api/admin/ml/datasets"),
    ("ml_list_dataset_versions", "GET", versions_path("dst_01KB6020000000000000000001")),
    ("ml_build_dataset_version", "POST", versions_path("dst_01KB6020000000000000000001")),
)
_BODIES: Final[dict[str, dict[str, Any]]] = {
    "ml_create_dataset": {"name": "x", "family": WALL},
    "ml_build_dataset_version": {},
}


def _route(app: FastAPI, name: str) -> AppRoute:
    for route in app.routes:
        if isinstance(route, AppRoute) and route.name == name:
            return route
    raise KeyError(f"route {name!r} chưa được mount")


def _engineer_headers(clock: FakeClock) -> dict[str, str]:
    return {"Authorization": f"Bearer {fake_token(Principal(new_id('usr', clock), 'sid-eng', 'engineer'))}"}


async def _forbidden_for_engineer(client: AsyncClient, clock: FakeClock, op: str) -> None:
    _op, method, path = next(row for row in _ROUTES if row[0] == op)
    response = await client.request(method, path, headers=_engineer_headers(clock), json=_BODIES.get(op))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


# Bốn hàm mỏng thay cho một hàm `parametrize`: `tools/case_gate.py` suy `op` từ **tên hàm**
# (`^test_(?P<op>.+?)__(?P<case>[A-Z]\d{2}...)`), nên một hàm mang tên chung sẽ gắn C07 vào một op
# không tồn tại và cả bốn op cùng thiếu C07. Thân vẫn dùng chung `_forbidden_for_engineer`.


async def test_ml_list_datasets__C07(api_client: AsyncClient, fake_clock: FakeClock) -> None:
    """`engineer` → 403 `FORBIDDEN` (cổng `require_admin` của router, chạy trước endpoint)."""
    await _forbidden_for_engineer(api_client, fake_clock, "ml_list_datasets")


async def test_ml_create_dataset__C07(api_client: AsyncClient, fake_clock: FakeClock) -> None:
    """`engineer` → 403 `FORBIDDEN`."""
    await _forbidden_for_engineer(api_client, fake_clock, "ml_create_dataset")


async def test_ml_list_dataset_versions__C07(api_client: AsyncClient, fake_clock: FakeClock) -> None:
    """`engineer` → 403 `FORBIDDEN`."""
    await _forbidden_for_engineer(api_client, fake_clock, "ml_list_dataset_versions")


async def test_ml_build_dataset_version__C07(api_client: AsyncClient, fake_clock: FakeClock) -> None:
    """`engineer` → 403 `FORBIDDEN`; bản `building` **không** được tạo vì cổng chặn trước endpoint."""
    await _forbidden_for_engineer(api_client, fake_clock, "ml_build_dataset_version")


def test_ml_datasets_routes_are_all_admin_only(api_app: FastAPI) -> None:
    routes = [_route(api_app, op) for op, _method, _path in _ROUTES]

    assert [route.wire_method for route in routes] == [method for _op, method, _path in _ROUTES]
    assert all(route.protected for route in routes)


def test_ml_create_dataset_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="unexpected"):
        CreateDatasetIn(name="x", family=WALL, unexpected=1)


def test_build_dataset_version_in_rejects_empty_project_ids() -> None:
    with pytest.raises(ValueError, match="at least 1 item"):
        BuildDatasetVersionIn(projectIds=[])
    assert BuildDatasetVersionIn().project_ids is None


async def test_dataset_out_omits_internal_columns(db_session: AsyncSession) -> None:
    """`created_by`, `name_key` không bao giờ ra dây (K01)."""
    row = await make_dataset(db_session, family=WALL)

    wire = dataset_out(row).model_dump(by_alias=True)

    assert set(wire) == {"createdAt", "family", "id", "name"}


async def test_dataset_version_out_split_counts_and_failure_code_are_exclusive(db_session: AsyncSession) -> None:
    dataset = await make_dataset(db_session, family=WALL)
    ready = await make_dataset_version(db_session, dataset=dataset, status="ready", sequence=1)
    failed = await make_dataset_version(db_session, dataset=dataset, status="failed", sequence=2)
    building = await make_dataset_version(db_session, dataset=dataset, status="building", sequence=3)

    ready_wire = dataset_version_out(ready).model_dump(by_alias=True)
    failed_wire = dataset_version_out(failed).model_dump(by_alias=True)
    building_wire = dataset_version_out(building).model_dump(by_alias=True)

    assert set(ready_wire["splitCounts"]) == {"train", "validation", "test"}
    assert "failureCode" not in ready_wire
    assert failed_wire["failureCode"] == failed.failure_code
    assert "splitCounts" not in failed_wire
    assert {"manifestSha256", "splitCounts", "failureCode"}.isdisjoint(building_wire)
    assert {"projectIds", "requeueCount", "buildStartedAt", "createdBy"}.isdisjoint(ready_wire)
