"""Hàm thuần của `service`: lọc khi trả (`filter_overrides`) và kiểm danh mục tầng 2 (`check_catalog`)."""

from typing import Any

import pytest

from apps.api.rules.service import check_catalog, filter_overrides
from packages.core.errors import AppError


def test_filter_overrides__drops_unknown_code_key_and_empties() -> None:
    """Mã lạ, khoá lạ, khoá dưới mã khác bị bỏ; `thresholds` rỗng → bỏ khoá; override rỗng → bỏ mã; `False`/`0` giữ."""
    stored: dict[str, dict[str, Any]] = {
        "OLD-RULE": {"enabled": False},
        "WALL-THICKNESS": {"thresholds": {"wall.oldMm": 5}},
        "DOOR-WIDTH": {"enabled": False, "thresholds": {"wall.minThicknessMm": 60, "door.minWidthMm": 700}},
        "ESCAPE-DISTANCE": {"thresholds": {"escape.openingOnOutlineToleranceMm": 0}},
        "GENERAL": {"thresholds": {"general.jointToleranceMm": 5}},
        "WALL-LENGTH": {"severity": "critical", "thresholds": {"wall.oldMm": 1}},
    }
    assert filter_overrides(stored) == {
        "DOOR-WIDTH": {"enabled": False, "thresholds": {"door.minWidthMm": 700}},
        "ESCAPE-DISTANCE": {"thresholds": {"escape.openingOnOutlineToleranceMm": 0}},
        "GENERAL": {"thresholds": {"general.jointToleranceMm": 5}},
        "WALL-LENGTH": {"severity": "critical"},
    }


@pytest.mark.parametrize(
    ("overrides", "code", "field"),
    [
        ({"GARAGE-WIDTH": {"enabled": True}}, "RULE_CODE_UNKNOWN", "body.overrides"),
        ({"WALL-LENGTH": {"thresholds": {"wall.fooMm": 1}}}, "RULE_THRESHOLD_UNKNOWN", "body.overrides"),
        ({"DOOR-WIDTH": {"thresholds": {"wall.minThicknessMm": 60}}}, "RULE_THRESHOLD_UNKNOWN", "body.overrides"),
        (
            {"WALL-THICKNESS": {"thresholds": {"wall.minThicknessMm": 29}}},
            "RULE_THRESHOLD_OUT_OF_RANGE",
            "body.overrides",
        ),
        ({"GENERAL": {"enabled": False}}, "RULE_GENERAL_NOT_TOGGLEABLE", "body.overrides.GENERAL.enabled"),
        ({"GENERAL": {"severity": "warning"}}, "RULE_GENERAL_NOT_TOGGLEABLE", "body.overrides.GENERAL.severity"),
        # Hai lỗi cùng lúc: mã đứng trước theo thứ tự chữ thắng (`DOOR-WIDTH` < `GARAGE-WIDTH`).
        (
            {"GARAGE-WIDTH": {"enabled": True}, "DOOR-WIDTH": {"thresholds": {"door.minWidthMm": 1}}},
            "RULE_THRESHOLD_OUT_OF_RANGE",
            "body.overrides",
        ),
        # Trong một mã: khoá đứng trước thắng (`door.minClearPassageMm` < `zzz.unknown`).
        (
            {"DOOR-BLOCKS-PATH": {"thresholds": {"door.minClearPassageMm": 1, "zzz.unknown": 1}}},
            "RULE_THRESHOLD_OUT_OF_RANGE",
            "body.overrides",
        ),
    ],
)
def test_check_catalog__first_error_wins(overrides: dict[str, dict[str, Any]], code: str, field: str) -> None:
    """Mỗi kiểu lỗi cho đúng mã và `field`; nhiều lỗi thì lỗi đứng trước theo thứ tự chữ thắng."""
    with pytest.raises(AppError) as caught:
        check_catalog(overrides)
    assert caught.value.code.code == code
    assert caught.value.params["field"] == field


def test_check_catalog__accepts_bounds() -> None:
    """Biên `[min, max]` hợp lệ; ngưỡng của `GENERAL` dưới `GENERAL` hợp lệ."""
    check_catalog(
        {
            "GENERAL": {"thresholds": {"general.jointToleranceMm": 500, "general.parallelAngleDeg": 0}},
            "WALL-UNSUPPORTED": {"enabled": False, "thresholds": {"wallSupport.minSupportShare": 1}},
        }
    )
