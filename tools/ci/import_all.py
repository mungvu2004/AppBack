"""Nhập toàn bộ module của một app để bắt lỗi nhập sớm, trong đúng ảnh Docker của nó (job `build`).

Chỉ dùng stdlib ở mức module: chạy trong ảnh chỉ có mã của một app, `tools/` được mount
rời — ảnh `ml` chẳng hạn có thể thiếu `fastapi`, nên `tools.ci.import_all` không được kéo
theo bất cứ phụ thuộc ngoài nào ở đầu file (import trong hàm với `worker` là ngoại lệ có
lý do, xem `_import_worker_schedule`).
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

_APPS = ("api", "worker", "ml")


def _module_name(root: Path, path: Path) -> str:
    """Đường `<root>/apps/x/y/__init__.py` hay `.../y.py` → tên chấm `apps.x.y`."""
    parts = path.relative_to(root).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _discover_modules(root: Path, app: str) -> list[str]:
    """Mọi module `.py` dưới `<root>/apps/<app>/`, sắp theo tên chấm (thứ tự ổn định); bỏ `tests/`, `__pycache__/`."""
    app_dir = root / "apps" / app
    names = set()
    for path in app_dir.rglob("*.py"):
        parts = path.relative_to(app_dir).parts
        if "tests" in parts or "__pycache__" in parts:
            continue
        names.add(_module_name(root, path))
    return sorted(names)


def _import_worker_schedule(failures: list[str]) -> None:
    """Nhập sổ lịch beat sau khi mọi module `apps.worker` đã nhập.

    Nhập `packages.messaging.schedules` bên trong hàm (không ở đầu module): ảnh `api`/`ml`
    không cài Celery, nhập ở đầu file sẽ làm `import_all` không chạy được trong ảnh đó.
    """
    from packages.messaging import schedules

    try:
        schedules.discover_jobs()
        schedules.beat_schedule()
    except Exception as exc:  # noqa: BLE001 -- gom lỗi sổ lịch cùng module hỏng, không để lỗi này giấu lỗi kia
        failures.append(f"packages.messaging.schedules: {type(exc).__name__}: {exc}")


def main(argv: list[str] | None = None) -> int:
    """Nhập mọi module của một app; `worker` thêm kiểm sổ lịch beat. Thoát 1 khi có module nhập hỏng."""
    parser = argparse.ArgumentParser()
    parser.add_argument("app", choices=_APPS)
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    root: Path = args.root if args.root is not None else Path.cwd()
    sys.path.insert(0, str(root))

    modules = _discover_modules(root, args.app)
    failures: list[str] = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 -- job build cần thấy hết module hỏng một lượt, không dừng ở cái đầu
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    if args.app == "worker":
        _import_worker_schedule(failures)

    for line in failures:
        sys.stderr.write(line + "\n")
    sys.stdout.write(f"import_all: đã nhập {len(modules)} module\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
