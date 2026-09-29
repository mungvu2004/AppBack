"""`python -m apps.api.admin_ml_registry.cli reevaluate <mdl_…>` (B6-01 [6] "CLI").

Đưa bản `failed` về `pending` để lịch `requeue_evaluations` gửi đánh giá lại: `attempts 0`,
`requested_at` và mã lỗi NULL, nên lượt lịch kế tiếp coi nó là "chưa từng gửi". Bản không có
hay không ở `failed` (đang chạy, đã `completed`) → thoát 1, không ghi gì. Mọi việc nằm trong
`main()`; nhập module này không chạm DB.
"""

import argparse
import asyncio
import sys
from typing import Final

from sqlalchemy import update

from packages.core.clock import SystemClock
from packages.db.engine import create_engine, create_sessionmaker, session_scope
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.db.settings import get_database_settings

EXIT_OK: Final = 0
EXIT_FAIL: Final = 1


def build_parser() -> argparse.ArgumentParser:
    """Một lệnh con `reevaluate <version_id>`; argparse tự thoát 2 khi thiếu lệnh hay đối số."""
    parser = argparse.ArgumentParser(prog="python -m apps.api.admin_ml_registry.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    reevaluate = commands.add_parser("reevaluate", help="đưa bản đánh giá lỗi về pending")
    reevaluate.add_argument("version_id", help="id bản, dạng mdl_…")
    return parser


async def _reevaluate(version_id: str) -> bool:
    """`UPDATE … WHERE status = 'failed'` một câu: `True` khi có đúng một dòng được đặt lại.

    Điều kiện `failed` nằm trong chính câu `UPDATE` (không đọc rồi ghi) nên một lượt
    `set_evaluation` chạy song song không bị ghi đè nhầm. Luôn đóng engine.
    """
    engine = create_engine(get_database_settings())
    stmt = (
        update(ModelVersionRow)
        .where(ModelVersionRow.id == version_id, ModelVersionRow.evaluation_status == "failed")
        .values(
            evaluation_status="pending",
            evaluation_attempts=0,
            evaluation_requested_at=None,
            evaluation_error_code=None,
            updated_at=SystemClock().now(),
        )
        .returning(ModelVersionRow.id)
    )
    try:
        async with session_scope(create_sessionmaker(engine)) as db:
            return (await db.execute(stmt)).scalar_one_or_none() is not None
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """Chạy CLI; in kết quả ra stdout, lý do thất bại ra stderr; trả mã thoát."""
    args = build_parser().parse_args(argv)
    if not asyncio.run(_reevaluate(args.version_id)):
        sys.stderr.write(f"{args.version_id}: không có bản này hoặc bản không ở trạng thái failed\n")
        return EXIT_FAIL
    sys.stdout.write(f"{args.version_id}: pending\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
