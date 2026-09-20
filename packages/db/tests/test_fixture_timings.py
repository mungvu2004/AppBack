"""Số đo của fixture CSDL (B0-03 [11].4). In bằng `logging`, không `print` (BE-00 §12)."""

import logging
import secrets
import time

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
