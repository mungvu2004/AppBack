"""Từ chối của N22 (B3-05 [8] "Từ chối", "Preset"): mỗi mã một test, thân lỗi đúng `code` và `field`."""

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.rules.tests.support import (
    config_path,
    get_config,
    headers_of,
    put_config,
    replace_body,
    seed_admin_project,
)


async def _rejected(
    client: httpx.AsyncClient, db: AsyncSession, overrides: dict[str, Any], code: str, field: str | None
) -> None:
    """PUT `overrides` (base 0) → 422 `code` (+ `field` nếu cho); `revision` không đổi (vẫn 0)."""
    owner, project = await seed_admin_project(db)
    response = await put_config(client, project.id, owner, replace_body(0, overrides))
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == code
    if field is not None:
        assert body["field"] == field
    assert (await get_config(client, project.id, owner)).json() == {"revision": 0, "overrides": {}}


async def test_rules_replace_config__unknown_code(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`GARAGE-WIDTH` (đúng mẫu, ngoài danh mục) → `RULE_CODE_UNKNOWN`."""
    await _rejected(api_client, db_session, {"GARAGE-WIDTH": {"enabled": True}}, "RULE_CODE_UNKNOWN", "body.overrides")


async def test_rules_replace_config__code_pattern(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`wall-thickness` (sai mẫu) → `VALIDATION`, không phải `RULE_CODE_UNKNOWN`."""
    await _rejected(api_client, db_session, {"wall-thickness": {"enabled": True}}, "VALIDATION", None)


async def test_rules_replace_config__unknown_threshold(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`wall.fooMm` → `RULE_THRESHOLD_UNKNOWN`."""
    overrides = {"WALL-THICKNESS": {"thresholds": {"wall.fooMm": 50}}}
    await _rejected(api_client, db_session, overrides, "RULE_THRESHOLD_UNKNOWN", "body.overrides")


async def test_rules_replace_config__threshold_under_other_code(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`wall.minThicknessMm` dưới `DOOR-WIDTH` → `RULE_THRESHOLD_UNKNOWN`."""
    overrides = {"DOOR-WIDTH": {"thresholds": {"wall.minThicknessMm": 50}}}
    await _rejected(api_client, db_session, overrides, "RULE_THRESHOLD_UNKNOWN", "body.overrides")


async def test_rules_replace_config__general_threshold_ok(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`general.jointToleranceMm` dưới `GENERAL` → 200."""
    owner, project = await seed_admin_project(db_session)
    overrides = {"GENERAL": {"thresholds": {"general.jointToleranceMm": 20}}}
    assert (await put_config(api_client, project.id, owner, replace_body(0, overrides))).status_code == 200


@pytest.mark.parametrize("value", [29, 201])
async def test_rules_replace_config__out_of_range(
    api_client: httpx.AsyncClient, db_session: AsyncSession, value: int
) -> None:
    """`wall.minThicknessMm` 29 và 201 (ngoài `[30, 200]`) → `RULE_THRESHOLD_OUT_OF_RANGE`, không kẹp."""
    overrides = {"WALL-THICKNESS": {"thresholds": {"wall.minThicknessMm": value}}}
    await _rejected(api_client, db_session, overrides, "RULE_THRESHOLD_OUT_OF_RANGE", "body.overrides")


@pytest.mark.parametrize("value", [0.5, 1])
async def test_rules_replace_config__range_bounds_ok(
    api_client: httpx.AsyncClient, db_session: AsyncSession, value: float
) -> None:
    """`wallSupport.minSupportShare` 0.5 và 1 (biên) → 200."""
    owner, project = await seed_admin_project(db_session)
    overrides = {"WALL-UNSUPPORTED": {"thresholds": {"wallSupport.minSupportShare": value}}}
    response = await put_config(api_client, project.id, owner, replace_body(0, overrides))
    assert response.status_code == 200
    assert response.json()["overrides"] == overrides


@pytest.mark.parametrize(("name", "value"), [("enabled", False), ("severity", "warning")])
async def test_rules_replace_config__general_not_toggleable(
    api_client: httpx.AsyncClient, db_session: AsyncSession, name: str, value: Any
) -> None:
    """`GENERAL` mang `enabled` hoặc `severity` → `RULE_GENERAL_NOT_TOGGLEABLE`, `field` trỏ tới khoá đó."""
    await _rejected(
        api_client,
        db_session,
        {"GENERAL": {name: value}},
        "RULE_GENERAL_NOT_TOGGLEABLE",
        f"body.overrides.GENERAL.{name}",
    )


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999"])
async def test_rules_replace_config__non_finite_raw(
    api_client: httpx.AsyncClient, db_session: AsyncSession, literal: str
) -> None:
    """Thân thô có `NaN`, `Infinity`, `1e999` làm ngưỡng → 422 `VALIDATION`, không ghi gì."""
    owner, project = await seed_admin_project(db_session)
    raw = (
        '{"baseVersion": 0, "body": {"overrides": {"WALL-THICKNESS": '
        f'{{"thresholds": {{"wall.minThicknessMm": {literal}}}}}}}}}}}'
    )
    headers = {**headers_of(owner), "Content-Type": "application/json"}
    response = await api_client.put(config_path(project.id), content=raw, headers=headers)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert (await get_config(api_client, project.id, owner)).json()["revision"] == 0


async def test_rules_replace_config__two_errors_first_by_code_order(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Hai lỗi cùng lúc → mã của lỗi đứng trước theo thứ tự chữ; bị từ chối thì `revision` không đổi."""
    overrides = {
        "GARAGE-WIDTH": {"enabled": True},
        "DOOR-WIDTH": {"thresholds": {"door.minWidthMm": 100}},
    }
    await _rejected(api_client, db_session, overrides, "RULE_THRESHOLD_OUT_OF_RANGE", "body.overrides")


_PRESETS: dict[str, dict[str, Any]] = {
    # `src/domain/rules/presets.ts:90-113` (buildCommercialConfig): hạ ROOM-NO-WINDOW, siết hành lang và cửa.
    "commercial": {
        "ROOM-NO-WINDOW": {"severity": "suggestion"},
        "CORRIDOR-WIDTH": {"thresholds": {"corridor.minClearWidthMm": 1200}},
        "DOOR-BLOCKS-PATH": {"thresholds": {"door.minClearPassageMm": 900}},
    },
    # `src/domain/rules/presets.ts:120-157` (buildIndustrialConfig): tắt luật phòng ở, siết thoát nạn/cửa/tường.
    "industrial": {
        "ROOM-AREA-BELOW-MINIMUM": {"enabled": False},
        "ROOM-NO-WINDOW": {"enabled": False},
        "ROOM-FURNITURE-MISMATCH": {"enabled": False},
        "CORRIDOR-WIDTH": {"thresholds": {"corridor.minClearWidthMm": 1500}},
        "DOOR-WIDTH": {"severity": "critical", "thresholds": {"door.minWidthMm": 1200}},
        "ESCAPE-DISTANCE": {"thresholds": {"escape.maxDistanceMm": 20000}},
        "WALL-THICKNESS": {"severity": "critical", "thresholds": {"wall.minThicknessMm": 200}},
        "WALL-UNSUPPORTED": {"thresholds": {"wallSupport.minSupportShare": 0.95}},
    },
}


@pytest.mark.parametrize("preset", sorted(_PRESETS))
async def test_rules_replace_config__preset_roundtrip(
    api_client: httpx.AsyncClient, db_session: AsyncSession, preset: str
) -> None:
    """`overrides` của preset văn phòng / nhà xưởng → 200; N21 đọc lại đúng từng giá trị, gồm `false` và `critical`."""
    owner, project = await seed_admin_project(db_session)
    response = await put_config(api_client, project.id, owner, replace_body(0, _PRESETS[preset]))
    assert response.status_code == 200
    read = await get_config(api_client, project.id, owner)
    assert read.json() == {"revision": 1, "overrides": _PRESETS[preset]}
