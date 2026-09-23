"""`python -m apps.api.projects.cli add-member --project prj_… --email E` (B2-01 [2]).

Đường vá tay của người vận hành: thêm một người **đã có** vào một dự án **đã có** mà không
cần đăng nhập. Không ghi nhật ký hoạt động (`added_by="system:cli"` đã là vết duy nhất cần
thiết, và `record_activity` đòi một `Principal` mà CLI không có).

Mọi việc nằm trong `main()`: B0-06 nhập mọi module của `apps.api`, nên nhập file này không
được kết nối gì. Mã thoát: 0 thêm xong **hoặc** đã là thành viên (lệnh idempotent), 1 không
tìm thấy người/dự án hay người bị vô hiệu.
"""

import argparse
import asyncio
import sys
from typing import Final

from sqlalchemy import select

from apps.api.projects.memberships import add_member
from packages.core.clock import SystemClock
from packages.core.text import normalize_email
from packages.db.engine import create_engine, create_sessionmaker, session_scope
from packages.db.models.auth import User
from packages.db.models.projects import Project
from packages.db.settings import get_database_settings

EXIT_OK: Final = 0
EXIT_FAIL: Final = 1
ADDED_BY: Final = "system:cli"


def build_parser() -> argparse.ArgumentParser:
    """Một lệnh con `add-member`; argparse tự thoát 2 khi thiếu tham số."""
    parser = argparse.ArgumentParser(prog="python -m apps.api.projects.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add-member", help="thêm một người dùng vào một dự án")
    add.add_argument("--project", required=True)
    add.add_argument("--email", required=True)
    return parser


def _say(stream: str, text: str) -> None:
    """In một dòng ra stdout hay stderr (CLI không dùng `print`, không dùng log)."""
    (sys.stdout if stream == "out" else sys.stderr).write(text + "\n")


async def _add_member(project_id: str, email: str) -> int:
    """Một giao dịch: tìm người và dự án chưa xoá mềm rồi thêm thành viên; trả mã thoát."""
    engine = create_engine(get_database_settings())
    try:
        async with session_scope(create_sessionmaker(engine)) as db:
            user = (
                await db.execute(
                    select(User).where(User.email_normalized == normalize_email(email), User.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if user is None:
                _say("err", f"không có người dùng nào với email {email}")
                return EXIT_FAIL
            if user.status == "disabled":
                _say("err", f"người dùng {user.id} đang bị vô hiệu")
                return EXIT_FAIL
            project = (
                await db.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
            ).scalar_one_or_none()
            if project is None:
                _say("err", f"không có dự án nào với id {project_id}")
                return EXIT_FAIL
            added = await add_member(db, project_id=project.id, user_id=user.id, added_by=ADDED_BY, clock=SystemClock())
            _say("out", f"{user.id} đã thêm vào {project.id}" if added else f"{user.id} vốn đã là thành viên")
            return EXIT_OK
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """Chạy CLI; trả mã thoát (0, 1, hoặc 2 của argparse)."""
    args = build_parser().parse_args(argv)
    return asyncio.run(_add_member(args.project, args.email))


if __name__ == "__main__":
    sys.exit(main())
