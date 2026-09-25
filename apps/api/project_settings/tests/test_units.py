"""Test đơn vị: schema, băm thân, CHECK của bảng và ranh giới nhập (B2-02 [5], [8])."""

import ast
import math
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.project_settings import read as read_module
from apps.api.project_settings.read import DEFAULT_SETTINGS, read_settings
from apps.api.project_settings.schemas import ProjectSettingsBodyIn
from apps.api.project_settings.service import body_digest
from apps.api.project_settings.tests.support import GOOD_BODY, seed_engineer_project
from packages.db.models.project_settings import ProjectSettingsRow

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")


def _body(**overrides: Any) -> ProjectSettingsBodyIn:
    """Thân hợp lệ với vài trường ghi đè."""
    return ProjectSettingsBodyIn.model_validate({**GOOD_BODY, **overrides})


def test_body__rounds_half_up_and_normalizes_notes() -> None:
    """Làm tròn `ROUND_HALF_UP` qua `Decimal(str(x))`; ghi chú trim, giữ `\\n` và `\\t`."""
    body = _body(confidenceThreshold=0.0005, defaultScaleMmPerPx=2, notes="  a\nb\tc  ")
    assert body.confidence_threshold == Decimal("0.001")
    assert body.default_scale_mm_per_px == Decimal("2.000000")
    assert body.notes == "a\nb\tc"


@pytest.mark.parametrize("bad", [float("nan"), math.inf, True, "1", None])
def test_body__rejects_non_finite_or_non_number(bad: Any) -> None:
    """`NaN`, vô cực, `bool`, chuỗi và `null` không là số hợp lệ."""
    with pytest.raises(ValidationError):
        _body(confidenceThreshold=bad)


def test_digest__is_stable_and_sensitive() -> None:
    """Cùng cột → cùng băm 64 hex; đổi một trường → băm khác; số thập phân ghi bằng chuỗi."""
    columns = {"notes": "x", "n": 1, "d": Decimal("0.500")}
    assert body_digest(columns) == body_digest(dict(reversed(list(columns.items()))))
    assert len(body_digest(columns)) == 64
    assert body_digest(columns) != body_digest({**columns, "d": Decimal("0.501")})


async def test_read_settings__default_when_no_row(db_session: AsyncSession) -> None:
    """Dự án chưa có dòng → `DEFAULT_SETTINGS` (revision 0)."""
    _, project = await seed_engineer_project(db_session)
    assert await read_settings(db_session, project.id) == DEFAULT_SETTINGS


@pytest.mark.parametrize(
    "override",
    [
        {"revision": 0},
        {"building_type": "villa"},
        {"notes": ""},
        {"length_unit": "km"},
        {"snap_tolerance_mm": 0},
        {"confidence_threshold": Decimal("1.001")},
        {"default_scale_mm_per_px": Decimal("0.009")},
        {"last_body_sha256": "abc"},
    ],
)
async def test_model__check_constraints_hold(db_session: AsyncSession, override: dict[str, Any]) -> None:
    """Mỗi CHECK của bảng chặn giá trị ngoài dải ngay ở DB thật."""
    _, project = await seed_engineer_project(db_session)
    fields: dict[str, Any] = {
        "project_id": project.id,
        "revision": 1,
        "building_type": "mixed",
        "length_unit": "mm",
        "snap_tolerance_mm": 50,
        "confidence_threshold": Decimal("0.75"),
        "default_scale_mm_per_px": Decimal(1),
        "last_writer_id": "usr_x",
        "last_body_sha256": "0" * 64,
    }
    db_session.add(ProjectSettingsRow(**{**fields, **override}))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


def _python(code: str) -> subprocess.CompletedProcess[str]:
    """Chạy một đoạn Python ở gốc repo, trả kết quả (không ném khi mã thoát khác 0)."""
    return subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False
    )


def test_read_module__imports_without_web_or_crypto_packages() -> None:
    """`read.py` nhập được khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn (worker nhập ngoài API)."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = _python(f"import sys; {blocked}; import {read_module.__name__}")
    assert result.returncode == 0, result.stderr


def test_package_init__is_docstring_only() -> None:
    """`__init__.py` chỉ có docstring (không import, không hằng)."""
    source = (REPO_ROOT / "apps/api/project_settings/__init__.py").read_text(encoding="utf-8")
    assert len(ast.parse(source).body) == 1
