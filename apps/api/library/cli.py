"""`python -m apps.api.library.cli publish` (B2-06 [6]): đưa danh mục lên storage ngay.

Chạy sau seed khi triển khai, để danh mục không rỗng tới lượt lịch đầu. Cùng lõi với lịch
(`assets.run_library_publish`). Mọi việc nằm trong `main()`; mã thoát 0 khi không mục nào
hỏng, 1 khi `failed > 0` (storage hỏng làm mục `failed`, không làm CLI sập).

`import-files <thư mục>`: phát hành mẫu từ tệp (`FILE_CATALOGUE`) có trong thư mục (`<id>.glb`,
`<id>.png` nếu có); cùng mã thoát.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Final

from apps.api.library.assets import ImportReport, PublishReport, import_files, open_storage, run_library_publish
from packages.core.clock import SystemClock
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.settings import get_database_settings

EXIT_OK: Final = 0
EXIT_FAIL: Final = 1


def build_parser() -> argparse.ArgumentParser:
    """Lệnh con `publish` và `import-files <dir>`; argparse tự thoát 2 khi thiếu lệnh."""
    parser = argparse.ArgumentParser(prog="python -m apps.api.library.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("publish", help="đưa object của danh mục lên storage")
    files = commands.add_parser("import-files", help="phát hành mẫu từ tệp .glb trong một thư mục")
    files.add_argument("directory", type=Path)
    return parser


async def _publish() -> PublishReport:
    """Một lượt `run_library_publish` với engine và storage của tiến trình; luôn đóng engine."""
    engine = create_engine(get_database_settings())
    clock = SystemClock()
    try:
        return await run_library_publish(create_sessionmaker(engine), open_storage(clock), clock)
    finally:
        await engine.dispose()


async def _import_files(directory: Path) -> ImportReport:
    """Một lượt `import_files` với engine và storage của tiến trình; luôn đóng engine."""
    engine = create_engine(get_database_settings())
    clock = SystemClock()
    try:
        return await import_files(create_sessionmaker(engine), open_storage(clock), clock, directory)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """Chạy CLI; in bảng đếm ra stdout, lỗi ra stderr; trả mã thoát."""
    args = build_parser().parse_args(argv)
    if args.command == "import-files":
        files = asyncio.run(_import_files(args.directory))
        sys.stdout.write(f"published={files.published} skipped={files.skipped} failed={files.failed}\n")
        failed = files.failed
    else:
        report = asyncio.run(_publish())
        sys.stdout.write(
            f"published={report.published} verified={report.verified} skipped={report.skipped} failed={report.failed}\n"
        )
        failed = report.failed
    if failed:
        sys.stderr.write(f"{failed} mục chưa phát hành được\n")
        return EXIT_FAIL
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
