"""Audit `pip-audit` với danh sách miễn có hạn — chặn lỗ hổng đã có bản sửa mà chưa miễn có lý do.

CLI cố định ở `B0-09/hop-dong.md` §2: `python -m tools.ci.audit --allowlist <file>
--report <pip-audit.json> [--today YYYY-MM-DD]`. Không tự chạy `pip-audit`: `job.sh` chạy
`uvx pip-audit --format json` rồi truyền báo cáo vào qua `--report` (không được sửa
`pyproject.toml` gốc để thêm `pip-audit` vào lock).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AllowlistEntry:
    """Một mục miễn: `id` lỗ hổng, lý do (≥ 10 ký tự sau strip), ngày hết hạn."""

    id: str
    reason: str
    expires: datetime.date


def _load_allowlist(path: Path, today: datetime.date) -> tuple[list[AllowlistEntry], list[str]]:
    """Đọc `audit-allowlist.toml`; trả (mục hợp lệ, lỗi cấu hình). Có lỗi cấu hình thì `main` không đọc tiếp báo cáo."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    entries: list[AllowlistEntry] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(data.get("ignore", [])):
        label = raw.get("id", f"mục #{idx}")
        missing = [k for k in ("id", "reason", "expires") if k not in raw]
        if missing:
            errors.append(f"{label}: thiếu trường {', '.join(missing)}")
            continue
        reason = raw["reason"]
        if len(str(reason).strip()) < 10:
            errors.append(f"{label}: lý do miễn quá ngắn (< 10 ký tự sau khi cắt khoảng trắng)")
            continue
        expires = raw["expires"]
        if not isinstance(expires, datetime.date):
            errors.append(f"{label}: expires không phải ngày TOML (YYYY-MM-DD không có nháy)")
            continue
        if expires < today:
            errors.append(f"{label}: đã hết hạn ({expires})")
            continue
        entry_id = raw["id"]
        if entry_id in seen_ids:
            errors.append(f"{label}: id miễn trùng")
            continue
        seen_ids.add(entry_id)
        entries.append(AllowlistEntry(id=entry_id, reason=str(reason), expires=expires))
    return entries, errors


def _check_report(report: dict[str, Any], allowlist: list[AllowlistEntry]) -> tuple[list[str], set[str]]:
    """Duyệt báo cáo pip-audit; trả (dòng lỗ hổng có bản sửa mà chưa miễn, tập id miễn đã khớp ≥ 1 lần)."""
    allowlist_ids = {e.id for e in allowlist}
    failures: list[str] = []
    matched: set[str] = set()
    for dep in report.get("dependencies", []):
        skip_reason = dep.get("skip_reason")
        if skip_reason:
            sys.stdout.write(f"audit: bỏ qua gói {dep.get('name')}: {skip_reason}\n")
            continue
        for vuln in dep.get("vulns", []):
            candidates = {vuln.get("id", "")} | set(vuln.get("aliases", []))
            hit = candidates & allowlist_ids
            if hit:
                matched |= hit
                continue
            fix_versions = vuln.get("fix_versions") or []
            if fix_versions:
                failures.append(
                    f"{dep.get('name')} {dep.get('version')} {vuln.get('id')} sửa ở {','.join(fix_versions)}"
                )
            else:
                sys.stdout.write(f"audit: {dep.get('name')} {dep.get('version')} {vuln.get('id')} chưa có bản sửa\n")
    return failures, matched


def main(argv: list[str] | None = None) -> int:
    """Kiểm allowlist rồi đối chiếu báo cáo pip-audit; thoát 1 khi cấu hình sai hoặc có lỗ hổng chưa miễn."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowlist", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--today", default=None)
    args = parser.parse_args(argv)
    # Mặc định UTC (không phải giờ máy runner) để "hôm nay" không lệch múi giờ giữa các runner.
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.datetime.now(datetime.UTC).date()

    allowlist, config_errors = _load_allowlist(args.allowlist, today)
    if config_errors:
        for err in config_errors:
            sys.stderr.write(f"audit-allowlist: {err}\n")
        return 1

    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"audit: báo cáo pip-audit không phải JSON hợp lệ: {exc}\n")
        return 1

    failures, matched = _check_report(report, allowlist)
    for entry in allowlist:
        if entry.id not in matched:
            sys.stdout.write(f"audit: mục miễn {entry.id} không khớp lỗ hổng nào\n")

    if failures:
        for line in failures:
            sys.stderr.write(line + "\n")
        return 1
    sys.stdout.write("audit: đạt\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
