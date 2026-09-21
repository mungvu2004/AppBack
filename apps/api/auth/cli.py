"""`python -m apps.api.auth.cli create-admin --email E --name N [--password-stdin]` (BE-00 §5).

Cách **duy nhất** tạo admin đầu tiên (K7 = B: không có đăng ký công khai). Mọi việc nằm
trong `main()`: B0-06 nhập mọi module của `apps.api`, nên nhập file này không được đọc
stdin, không kết nối gì.

Mật khẩu chỉ đi qua stdin (`--password-stdin`, một dòng) hoặc `getpass` — không qua tham số
dòng lệnh (lộ ở `ps`, lịch sử shell) hay biến môi trường. Không ghi nhật ký hoạt động,
không log gì chứa mật khẩu.

Mã thoát: 0 tạo xong (in `usr_…`), 2 đầu vào sai (email, tên, mật khẩu < 8 ký tự),
3 email đã có người dùng (sau chuẩn hoá, C16).
"""

import argparse
import asyncio
import getpass
import sys
from typing import Final

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from apps.api.auth.emails import validate_wire_email
from apps.api.auth.passwords import MIN_PASSWORD_LENGTH, hash_password
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.text import nfc, normalize_email
from packages.db.engine import create_engine, create_sessionmaker, session_scope
from packages.db.errors import unique_violation
from packages.db.models.auth import NAME_MAX, User
from packages.db.settings import get_database_settings

EXIT_OK: Final = 0
EXIT_INVALID: Final = 2
EXIT_EXISTS: Final = 3
EMAIL_UNIQUE: Final = "uq_users_email"


def build_parser() -> argparse.ArgumentParser:
    """Một lệnh con `create-admin`; argparse tự thoát 2 khi thiếu tham số."""
    parser = argparse.ArgumentParser(prog="python -m apps.api.auth.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-admin", help="tạo admin active đầu tiên")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--password-stdin", action="store_true", help="đọc mật khẩu từ một dòng stdin")
    return parser


def _say(stream: str, text: str) -> None:
    """In một dòng ra stdout hay stderr (CLI không dùng `print`, không dùng log)."""
    (sys.stdout if stream == "out" else sys.stderr).write(text + "\n")


def _read_password(from_stdin: bool) -> str:
    """Một dòng stdin (bỏ ký tự xuống dòng cuối) hoặc `getpass` không hiện chữ."""
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    return getpass.getpass("Mật khẩu: ")


async def _insert_admin(email: str, name: str, password_hash: str) -> str | None:
    """Chèn admin `active`; email đã có (ràng buộc `uq_users_email`) → `None`."""
    user_id = new_id("usr", SystemClock())
    engine = create_engine(get_database_settings())
    try:
        async with session_scope(create_sessionmaker(engine)) as db:
            await db.execute(
                insert(User).values(
                    id=user_id,
                    email=email,
                    email_normalized=normalize_email(email),
                    name=name,
                    password_hash=password_hash,
                    role="admin",
                    status="active",
                )
            )
    except IntegrityError as exc:
        if unique_violation(exc) != EMAIL_UNIQUE:
            raise
        return None
    finally:
        await engine.dispose()
    return user_id


async def _create_admin(email: str, name: str, password: str) -> int:
    """Băm (NFC, executor riêng) rồi chèn; không mở kết nối nào trước khi băm xong."""
    user_id = await _insert_admin(email, name, await hash_password(password))
    if user_id is None:
        _say("err", "email đã có người dùng")
        return EXIT_EXISTS
    _say("out", user_id)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Chạy CLI; trả mã thoát (0, 2, 3)."""
    args = build_parser().parse_args(argv)
    try:
        email = validate_wire_email(args.email)
    except ValueError:
        _say("err", "email sai dạng")
        return EXIT_INVALID
    name = nfc(args.name.strip())
    if not 1 <= len(name) <= NAME_MAX:
        _say("err", f"tên phải dài 1-{NAME_MAX} ký tự")
        return EXIT_INVALID
    password = _read_password(args.password_stdin)
    if len(nfc(password)) < MIN_PASSWORD_LENGTH:
        _say("err", f"mật khẩu phải dài ít nhất {MIN_PASSWORD_LENGTH} ký tự")
        return EXIT_INVALID
    return asyncio.run(_create_admin(email, name, password))


if __name__ == "__main__":
    sys.exit(main())
