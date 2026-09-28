"""Danh mục luật (B3-05 [8] "Danh mục"): đếm, tính nhất quán và tính thuần (không nhập fastapi/sqlalchemy)."""

import importlib
import sys

import pytest

from apps.api.rules.catalog import GENERAL_CODE, RULE_CODES, THRESHOLD_SPECS


def test_catalog__rule_codes() -> None:
    """25 mã, không trùng, không có `GENERAL`, đúng thứ tự ALL_RULES ở các đầu nhóm."""
    assert len(RULE_CODES) == 25
    assert len(set(RULE_CODES)) == 25
    assert GENERAL_CODE not in RULE_CODES
    assert (RULE_CODES[0], RULE_CODES[8], RULE_CODES[15], RULE_CODES[22], RULE_CODES[-1]) == (
        "WALL-THICKNESS",
        "WALL-OVERLAP",
        "ROOM-NO-DOOR",
        "ROOM-FURNITURE-MISMATCH",
        "WINDOW-ON-INNER-WALL",
    )


def test_catalog__threshold_specs() -> None:
    """26 khoá, `min <= max`, mọi `rule_code` hợp lệ, đúng 2 khoá dưới `GENERAL` và 8 khoá `room.minArea.*`."""
    assert len(THRESHOLD_SPECS) == 26
    assert all(spec.min <= spec.max for spec in THRESHOLD_SPECS.values())
    assert all(spec.rule_code in {*RULE_CODES, GENERAL_CODE} for spec in THRESHOLD_SPECS.values())
    assert sum(spec.rule_code == GENERAL_CODE for spec in THRESHOLD_SPECS.values()) == 2
    assert sum(key.startswith("room.minArea.") for key in THRESHOLD_SPECS) == 8


def test_catalog__imports_without_fastapi_or_sqlalchemy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nhập lại `apps.api.rules.catalog` khi `fastapi`, `sqlalchemy` bị chặn trong `sys.modules` (H4 chạy ngoài app)."""
    monkeypatch.setitem(sys.modules, "fastapi", None)
    monkeypatch.setitem(sys.modules, "sqlalchemy", None)
    monkeypatch.delitem(sys.modules, "apps.api.rules.catalog")
    fresh = importlib.import_module("apps.api.rules.catalog")
    assert (len(fresh.RULE_CODES), len(fresh.THRESHOLD_SPECS)) == (25, 26)
