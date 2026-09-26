"""`python -m apps.api.spatial_read.cli check-documents` (B3-02 [6], FIX.md luật 6).

Duyệt mọi dòng `floor_documents` theo lô bằng `documents.scan_corrupt` — cùng luật với
đường đọc của route, nên CLI không thể lệch khỏi nó. In mỗi `floor_pk` hỏng một dòng.
Mã thoát: 0 sạch, 1 có dòng hỏng, 2 tham số sai (argparse). Mọi việc nằm trong `main()`:
B0-06 nhập mọi module `apps.api` nên nhập file này không được kết nối gì.
"""

import argparse
import asyncio
import sys
from typing import Final

from apps.api.spatial_read.documents import scan_corrupt
from apps.api.spatial_read.settings import get_spatial_read_settings
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.settings import get_database_settings

EXIT_OK: Final = 0
EXIT_CORRUPT: Final = 1


def build_parser() -> argparse.ArgumentParser:
    """Một lệnh con `check-documents`; argparse tự thoát 2 khi thiếu hay sai tham số."""
    parser = argparse.ArgumentParser(prog="python -m apps.api.spatial_read.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-documents", help="liệt kê tầng có tài liệu không giải mã được")
    return parser


async def _check_documents() -> list[int]:
    """Mọi `floor_pk` hỏng, theo thứ tự tăng dần; mỗi lô một session ngắn."""
    engine = create_engine(get_database_settings())
    maker = create_sessionmaker(engine)
    limit = get_spatial_read_settings().spatial_recount_batch
    corrupt: list[int] = []
    cursor: int | None = 0
    try:
        while cursor is not None:
            async with maker() as db:
                found, cursor = await scan_corrupt(db, after_pk=cursor, limit=limit)
            corrupt += found
    finally:
        await engine.dispose()
    return corrupt


def main(argv: list[str] | None = None) -> int:
    """Chạy CLI; trả mã thoát."""
    build_parser().parse_args(argv)
    corrupt = asyncio.run(_check_documents())
    for floor_pk in corrupt:
        sys.stdout.write(f"{floor_pk}\n")
    return EXIT_CORRUPT if corrupt else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
