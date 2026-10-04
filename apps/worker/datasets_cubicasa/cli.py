"""`python -m apps.worker.datasets_cubicasa.cli import --src PATH --dataset dst_… [--limit N]` (B6-02b [2]).

Mọi việc nằm trong `main()`: nhập module này không chạm DB, kho hay biến môi trường, nên test
nhập được nó trong một tiến trình có `DATABASE_URL` hỏng mà không có tác dụng phụ (BE-00 §5).
In báo cáo ra stdout bằng `sys.stdout.write` (ruff `T20`); mã từ chối hay `failureCode` ra
stderr. Mã thoát lấy từ `ImportReport.exit_code`: 0 `ready`, 1 `failed`, 2 `refused`.
"""

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from apps.worker.datasets.tasks import open_storage
from apps.worker.datasets_cubicasa.importer import SOURCE_LICENSE, ImportReport, import_cubicasa
from apps.worker.datasets_cubicasa.settings import CubiCasaSettings
from packages.core.clock import SystemClock
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.settings import get_database_settings


def _positive(value: str) -> int:
    """`--limit` nguyên ≥ 1; khác → `ArgumentTypeError` (argparse thoát 2, không ngoại lệ lạ)."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("--limit phải ≥ 1")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Một lệnh con `import`; argparse tự thoát 2 khi thiếu lệnh con hay đối số bắt buộc."""
    parser = argparse.ArgumentParser(prog="python -m apps.worker.datasets_cubicasa.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="nhập CubiCasa5K vào một phiên bản dataset")
    importer.add_argument("--src", type=Path, required=True, help="thư mục đã giải nén hay tệp zip cục bộ")
    importer.add_argument("--dataset", required=True, help="id dataset, dạng dst_…")
    importer.add_argument("--limit", type=_positive, default=None, help="chỉ nhập N mẫu đầu")
    return parser


def _distribution(values: Sequence[float]) -> str:
    """`n, min, p10, p50, p90, max` của một dãy; dãy rỗng → `n=0` (không chia cho 0)."""
    if not values:
        return "n=0"
    ordered = sorted(values)
    last = len(ordered) - 1
    percentiles = (ordered[round(last * q)] for q in (0.1, 0.5, 0.9))
    p10, p50, p90 = percentiles
    return f"n={len(ordered)} min={ordered[0]:.3f} p10={p10:.3f} p50={p50:.3f} p90={p90:.3f} max={ordered[-1]:.3f}"


def _write_counts(label: str, counts: Mapping[str, int]) -> None:
    """Một dòng `label: khoá=số …` ra stdout; bảng rỗng in `-` để người đọc biết đã đo."""
    body = " ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "-"
    sys.stdout.write(f"{label}: {body}\n")


def _write_report(report: ImportReport) -> None:
    """In toàn bộ báo cáo lệnh: phiên bản, giấy phép nguồn, split, mẫu bỏ, nhánh ảnh, phân bố, tên đồ lạ ([2])."""
    sys.stdout.write(f"version: {report.version_id or '-'} ({report.outcome})\n")
    sys.stdout.write(f"license: {SOURCE_LICENSE}\n")
    _write_counts("splits", report.split_counts)
    _write_counts("skipped", report.skipped)
    _write_counts("branches", report.branches)
    for subset, values in sorted(report.ink_ratios.items()):
        sys.stdout.write(f"ink_ratio[{subset}]: {_distribution(values)}\n")
    for key, values in sorted(report.fits.items()):
        sys.stdout.write(f"fit[{key}]: {_distribution(values)}\n")
    unknown = " ".join(f"{name}={count}" for name, count in report.unknown_fixtures) or "-"
    sys.stdout.write(f"unknown_fixtures: {unknown}\n")
    if report.outcome == "refused":
        reason = f" {report.reason}" if report.reason else ""
        sys.stderr.write(f"refused: {report.code}{reason}\n")
    elif report.outcome == "failed":
        sys.stderr.write(f"failed: failureCode={report.code}\n")


async def _import(src: Path, dataset_id: str, limit: int | None) -> ImportReport:
    """Dựng tài nguyên thật của tiến trình (engine, kho, cấu hình) và chạy một lượt nhập.

    Engine luôn `dispose()` trong `finally`: lệnh chạy một lượt rồi thoát, để lại kết nối mở
    thì container worker treo ở lúc đóng.
    """
    engine = create_engine(get_database_settings())
    clock = SystemClock()
    try:
        return await import_cubicasa(
            create_sessionmaker(engine),
            open_storage(clock),
            clock,
            src=src,
            dataset_id=dataset_id,
            limit=limit,
            settings=CubiCasaSettings(),
        )
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """Chạy CLI: phân tích đối số, nhập một lượt, in báo cáo, trả mã thoát của kết cục."""
    args = build_parser().parse_args(argv)
    report = asyncio.run(_import(args.src, args.dataset, args.limit))
    _write_report(report)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
