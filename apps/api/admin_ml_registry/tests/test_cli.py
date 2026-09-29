"""CLI `reevaluate` (B6-01 [6] "CLI", [8] "Lịch"): `failed` → `pending`; id lạ hay bản khác → thoát 1."""

import asyncio
from collections.abc import Iterator

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_registry import cli
from packages.core.ids import new_id
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.db.settings import reset_database_settings_cache
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.fixtures.clock import FakeClock

OPENING = "openingAndFurnitureDetection"


@pytest.fixture
def process_env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường của tiến trình CLI: chỉ cần DB test riêng."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    yield
    reset_database_settings_cache()


async def _failed(db: AsyncSession, maker: async_sessionmaker[AsyncSession]) -> ModelVersionRow:
    """Bản `failed` đã dùng hết lượt: `attempts 6`, đã gửi, mã `RETRY_EXHAUSTED`."""
    row = await make_model_version(db, family=OPENING, status="failed")
    async with maker() as other:
        await other.execute(
            update(ModelVersionRow)
            .where(ModelVersionRow.id == row.id)
            .values(
                evaluation_attempts=6, evaluation_requested_at=row.created_at, evaluation_error_code="RETRY_EXHAUSTED"
            )
        )
        await other.commit()
    return row


@pytest.mark.usefixtures("process_env")
async def test_reevaluate_resets_a_failed_version_to_pending(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], capsys: pytest.CaptureFixture[str]
) -> None:
    """`failed` → `pending`, `attempts 0`, `requested_at` và mã lỗi NULL; in id ra stdout, thoát 0."""
    row = await _failed(db_session, db_sessionmaker)

    code = await asyncio.to_thread(cli.main, ["reevaluate", row.id])

    assert code == cli.EXIT_OK
    assert capsys.readouterr().out == f"{row.id}: pending\n"
    await db_session.refresh(row)
    assert (
        row.evaluation_status,
        row.evaluation_attempts,
        row.evaluation_requested_at,
        row.evaluation_error_code,
        row.metrics,
    ) == ("pending", 0, None, None, None)


@pytest.mark.usefixtures("process_env")
async def test_reevaluate_exits_one_for_an_unknown_id(
    fake_clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    """Id không có trong bảng → thoát 1, lý do ra stderr, stdout trống."""
    unknown = new_id("mdl", fake_clock)

    code = await asyncio.to_thread(cli.main, ["reevaluate", unknown])

    captured = capsys.readouterr()
    assert code == cli.EXIT_FAIL
    assert captured.out == ""
    assert unknown in captured.err


@pytest.mark.usefixtures("process_env")
@pytest.mark.parametrize("status", ["pending", "running", "completed"])
async def test_reevaluate_leaves_non_failed_versions_untouched(db_session: AsyncSession, status: str) -> None:
    """Bản chưa `failed` → thoát 1 và không ghi gì (kể cả `metrics` của bản `completed`)."""
    row = await make_model_version(db_session, family=OPENING, status=status)
    before = (row.evaluation_status, row.evaluation_attempts, dict(row.metrics) if row.metrics else None)

    code = await asyncio.to_thread(cli.main, ["reevaluate", row.id])

    assert code == cli.EXIT_FAIL
    await db_session.refresh(row)
    assert (row.evaluation_status, row.evaluation_attempts, row.metrics) == before


def test_cli_requires_a_command_and_an_id(capsys: pytest.CaptureFixture[str]) -> None:
    """Thiếu lệnh hay thiếu id: argparse thoát 2, không chạm DB."""
    for argv in ([], ["reevaluate"]):
        with pytest.raises(SystemExit) as raised:
            cli.main(argv)
        assert raised.value.code == 2
    assert "usage" in capsys.readouterr().err
