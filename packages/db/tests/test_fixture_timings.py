"""Số đo của fixture CSDL (B0-03 [11].4). In bằng `logging`, không `print` (BE-00 §12)."""

import logging
import secrets
import time

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.db.engine import GATE_CONNECT_TIMEOUT_S
from packages.testing.fixtures import db as db_fixtures

log = logging.getLogger(__name__)
ROUNDS = 3


def test_db_fixture_timings(postgres_url: str) -> None:
    """Dựng một database mẫu riêng rồi nhân bản vài lần, để số đo không phụ thuộc thứ tự test."""
    template = f"tpl_{secrets.token_hex(4)}"
    started = time.perf_counter()
    db_fixtures._create_database(postgres_url, template)
    db_fixtures._alembic_upgrade(db_fixtures._with_database(postgres_url, template))
    template_s = time.perf_counter() - started

    durations: list[float] = []
    try:
        for _ in range(ROUNDS):
            child = f"t_{secrets.token_hex(4)}"
            start = time.perf_counter()
            db_fixtures._create_database(postgres_url, child, template=template)
            durations.append(time.perf_counter() - start)
            db_fixtures._drop_database(postgres_url, child)
    finally:
        db_fixtures._drop_database(postgres_url, template)

    log.info(
        "db_template: %.2f s · db_url trung bình: %.3f s (%d lượt, nhanh nhất %.3f s)",
        template_s,
        sum(durations) / len(durations),
        ROUNDS,
        min(durations),
    )
    assert len(durations) == ROUNDS


async def test_db_sessionmaker_chịu_trần_bắt_tay_cổng(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """NO-036: engine của fixture bắt tay với `GATE_CONNECT_TIMEOUT_S`, không phải 10 s của đường request.

    Mọi test nối Postgres qua chặng `host.docker.internal`, có lúc kẹt ~68 s (NO-007); trần
    10 s làm cổng đỏ giả theo số lượng test. Đọc trần thật qua sự kiện `do_connect`.
    """
    engine: AsyncEngine = db_sessionmaker.kw["bind"]
    timeouts: list[object] = []
    event.listen(engine.sync_engine, "do_connect", lambda _d, _r, _a, params: timeouts.append(params["timeout"]))
    async with db_sessionmaker() as session:
        await session.execute(text("SELECT 1"))
    assert timeouts == [GATE_CONNECT_TIMEOUT_S]
