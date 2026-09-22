"""Gộp artifact ba job coverage thành junit và vết case dùng chung cho `tools.case_gate`.

CLI cố định ở `B0-09/hop-dong.md` §2: `python -m tools.ci.merge_artifacts --root <dir>
--jobs <j1,j2,...> --junit-out <file> --trace-out <file>`. Chạy trong job `coverage` sau
khi tải xong artifact `cov-<job>` của mỗi job vào `<root>/<job>/`. Không ghi gì nếu thiếu
artifact hay dữ liệu hỏng — job `coverage` phải thấy lỗi trước khi gộp lặng lẽ.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _job_dir(root: Path, job: str) -> Path:
    """Đường artifact đã tải của một job: `<root>/<job>/`."""
    return root / job


def _missing_artifacts(root: Path, job: str) -> list[str]:
    """Tên file thiếu của một job: junit, vết case, và ít nhất một `.coverage.*`."""
    job_dir = _job_dir(root, job)
    missing = [name for name in (f"junit-{job}.xml", f"trace-{job}.jsonl") if not (job_dir / name).is_file()]
    if not any(job_dir.glob(".coverage.*")):
        missing.append(".coverage.*")
    return missing


def _load_testsuites(path: Path) -> list[ET.Element]:
    """Đọc một junit; trả các `<testsuite>` con — gốc `<testsuites>` hay `<testsuite>` đều nhận."""
    try:
        root = ET.parse(path).getroot()  # noqa: S314 -- junit do pytest job này sinh trong CI, không phải input ngoài
    except ET.ParseError as exc:
        raise ValueError(f"junit hỏng: {path}: {exc}") from exc
    return list(root) if root.tag == "testsuites" else [root]


def _merge_junit(root: Path, jobs: list[str]) -> ET.Element:
    """Gộp `<testsuite>` của mọi job vào một `<testsuites>` gốc, giữ nguyên mọi testcase con (tên trùng giữ đủ)."""
    merged = ET.Element("testsuites")
    for job in jobs:
        for suite in _load_testsuites(_job_dir(root, job) / f"junit-{job}.xml"):
            merged.append(suite)
    return merged


def _trace_lines(path: Path) -> list[tuple[int, str]]:
    """Đọc vết theo dòng (stream, R-22); trả `(số dòng, nội dung)`, bỏ dòng trống ở cuối file.

    Một dòng trống ở giữa file không phải "dòng trống cuối" — được giữ lại để lượt kiểm JSON
    phía sau báo hỏng đúng chỗ, thay vì âm thầm bỏ qua dữ liệu vết bị hỏng giữa chừng.
    """
    lines: list[tuple[int, str]] = []
    pending: tuple[int, str] | None = None
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.rstrip("\n")
            if pending is not None:
                lines.append(pending)
                pending = None
            if line.strip() == "":
                pending = (lineno, line)
                continue
            lines.append((lineno, line))
    return lines


def _merge_trace(root: Path, jobs: list[str]) -> tuple[list[str], list[str]]:
    """Gộp vết case theo thứ tự `jobs`; trả (dòng hợp lệ theo thứ tự, lỗi `file:dòng` của dòng không phải JSON)."""
    merged: list[str] = []
    errors: list[str] = []
    for job in jobs:
        path = _job_dir(root, job) / f"trace-{job}.jsonl"
        for lineno, line in _trace_lines(path):
            try:
                json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"{path}:{lineno}")
                continue
            merged.append(line)
    return merged, errors


def main(argv: list[str] | None = None) -> int:
    """Kiểm đủ artifact mọi job rồi gộp junit + vết case; thoát 1 (không ghi gì) khi thiếu hoặc hỏng."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--junit-out", required=True, type=Path)
    parser.add_argument("--trace-out", required=True, type=Path)
    args = parser.parse_args(argv)
    jobs: list[str] = args.jobs.split(",")

    missing = [f"thiếu artifact của job {job}: {name}" for job in jobs for name in _missing_artifacts(args.root, job)]
    if missing:
        for line in missing:
            sys.stderr.write(line + "\n")
        return 1

    try:
        merged_junit = _merge_junit(args.root, jobs)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1

    merged_trace, trace_errors = _merge_trace(args.root, jobs)
    if trace_errors:
        for err in trace_errors:
            sys.stderr.write(f"dòng vết không phải JSON: {err}\n")
        return 1

    args.junit_out.write_bytes(ET.tostring(merged_junit, encoding="utf-8", xml_declaration=True))
    args.trace_out.write_text("\n".join(merged_trace) + ("\n" if merged_trace else ""), encoding="utf-8")
    sys.stdout.write(f"merge_artifacts: gộp {len(jobs)} job, {len(merged_trace)} dòng vết\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
