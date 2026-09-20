"""`python -m packages.db.new_revision --code <mã> --slug <việc>` (BE-00 §6.1).

Đặt tên thay cho người: `revision = r<yyyymmdd>_<mã>[_fix<nnn>]` (≤ 32 ký tự vì
`alembic_version.version_num` là `VARCHAR(32)`), file `<revision>_<slug>.py`.
Từ chối khi prompt đã có revision, khi cây có > 1 head (rebase trước đã, không tạo
revision merge — việc của người điều phối), khi slug sai mẫu hay id quá dài.
"""

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from alembic import command
from alembic.script import ScriptDirectory

from packages.db.migrate_check import alembic_config

MAX_REVISION_LEN: Final = 32
_SLUG_RE: Final = re.compile(r"[a-z][a-z0-9_]*")
_CODE_RE: Final = re.compile(r"[a-z][a-z0-9_]*")  # cùng mẫu với tools/lint_migrations.py
_FIX_RE: Final = re.compile(r"[0-9]{3}")
_REVISION_RE: Final = re.compile(r"r(?P<date>[0-9]{8})_(?P<code>[a-z][a-z0-9_]*?)(?:_fix(?P<fix>[0-9]{3}))?")


def _say(text: str) -> None:
    print(text)  # noqa: T201 — CLI in kết quả ra stdout cho worker


def revision_id(code: str, slug_date: str, fix: str | None) -> str:
    return f"r{slug_date}_{code}" + (f"_fix{fix}" if fix else "")


def _existing(script: ScriptDirectory, code: str, fix: str | None) -> str | None:
    for revision in script.walk_revisions():
        match = _REVISION_RE.fullmatch(str(revision.revision))
        if match and match.group("code") == code and match.group("fix") == fix:
            return str(revision.revision)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m packages.db.new_revision")
    parser.add_argument("--code", required=True, help="mã prompt, ví dụ B2-01")
    parser.add_argument("--slug", required=True, help="việc, snake_case, ví dụ add_projects")
    parser.add_argument("--fix", help="số FIX ba chữ số, ví dụ 001")
    parser.add_argument("--autogenerate", action="store_true", help="so model với DB (cần DATABASE_URL)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code = args.code.lower().replace("-", "_")
    if not _CODE_RE.fullmatch(code):
        _say(f"mã prompt sai mẫu: {args.code}")
        return 2
    if not _SLUG_RE.fullmatch(args.slug):
        _say(f"slug phải là snake_case: {args.slug}")
        return 2
    if args.fix is not None and not _FIX_RE.fullmatch(args.fix):
        _say(f"--fix phải là ba chữ số: {args.fix}")
        return 2

    new_id = revision_id(code, datetime.now(UTC).strftime("%Y%m%d"), args.fix)
    if len(new_id) > MAX_REVISION_LEN:
        _say(f"revision id dài {len(new_id)} > {MAX_REVISION_LEN} ký tự: {new_id}")
        return 2

    config = alembic_config()
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) > 1:
        _say(f"cây có {len(heads)} head: {', '.join(heads)}. Rebase lên nhánh tích hợp rồi chạy lại.")
        return 2
    taken = _existing(script, code, args.fix)
    if taken is not None:
        _say(f"{args.code} đã có revision {taken}; mỗi prompt (và mỗi FIX) tối đa một revision.")
        return 2

    command.revision(config, message=args.slug, rev_id=new_id, autogenerate=args.autogenerate)
    created = next(Path(script.versions).glob(f"{new_id}_*.py"), None)
    _say(f"đã tạo {created}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
