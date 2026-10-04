"""Sổ lịch nền: khai báo, chu kỳ tối thiểu, và cách dò module một cấp."""

import re
import subprocess
import sys
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from packages.messaging.schedules import (
    MIN_PERIOD_S,
    beat_schedule,
    discover_jobs,
    discover_submodules,
    periodic,
    schedule_entries,
)

PROBE = "probe_pkg"
REPO_ROOT = Path(__file__).resolve().parents[3]
RUNS: list[str] = []


@periodic("tests.jobs.trim_probe", timedelta(minutes=5))
def trim_probe() -> None:
    """Lịch đồng bộ mẫu trên hàng `default`; ghi tên vào `RUNS` khi chạy."""
    RUNS.append("trim_probe")


@periodic("pipeline.tests.sweep_probe", timedelta(hours=1))
async def sweep_probe() -> None:
    """Lịch `async` mẫu trên hàng `pipeline.cpu`; ghi tên vào `RUNS` khi chạy."""
    RUNS.append("sweep_probe")


@pytest.fixture
def probe_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Một gói thật trên đĩa, gỡ khỏi `sys.modules` khi xong để test sau không thấy nó."""
    root = tmp_path / PROBE
    (root / "with_tasks").mkdir(parents=True)
    (root / "without_tasks").mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "with_tasks" / "__init__.py").write_text("", encoding="utf-8")
    (root / "with_tasks" / "tasks.py").write_text("LOADED = True\n", encoding="utf-8")
    (root / "without_tasks" / "__init__.py").write_text("", encoding="utf-8")
    (root / "plain.py").write_text("raise AssertionError('module lẻ không được nhập')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    yield root
    for name in [name for name in sys.modules if name == PROBE or name.startswith(f"{PROBE}.")]:
        del sys.modules[name]


def test_a_period_below_the_floor_is_refused() -> None:
    """Chu kỳ ngắn hơn một lượt chạy thì beat chất đống việc trên hàng."""
    with pytest.raises(ValueError, match=str(MIN_PERIOD_S)):

        @periodic("tests.jobs.too_often", timedelta(seconds=MIN_PERIOD_S - 1))
        def too_often() -> None:
            """Chu kỳ dưới trần."""


def test_the_floor_itself_is_allowed() -> None:
    """Chu kỳ đúng bằng trần tối thiểu được nhận và vào `beat_schedule`."""

    @periodic("tests.jobs.exactly_one_minute", timedelta(seconds=MIN_PERIOD_S))
    def exactly_one_minute() -> None:
        """Đúng chu kỳ tối thiểu."""

    assert "tests.jobs.exactly_one_minute" in beat_schedule()


def test_two_schedules_cannot_share_a_name() -> None:
    """Hai lịch trùng tên bị từ chối ngay lúc khai — beat chỉ chạy được một."""
    with pytest.raises(ValueError, match=re.escape("tests.jobs.trim_probe")):

        @periodic("tests.jobs.trim_probe", timedelta(minutes=5))
        def trim_probe_again() -> None:
            """Trùng tên với lịch đã khai ở đầu module."""


def test_beat_schedule_carries_the_period_and_the_queue() -> None:
    """`beat_schedule` mang đúng chu kỳ (giây) và hàng suy từ tiền tố tên."""
    schedule = beat_schedule()

    assert schedule["tests.jobs.trim_probe"] == {
        "task": "tests.jobs.trim_probe",
        "schedule": 300.0,
        "options": {"queue": "default"},
    }
    assert schedule["pipeline.tests.sweep_probe"]["options"] == {"queue": "pipeline.cpu"}


def test_schedule_entries_are_sorted_and_name_their_function() -> None:
    """`schedule_entries` xếp theo tên và ghi đúng tên hàm lịch."""
    entries = {entry.name: entry for entry in schedule_entries()}

    assert entries["tests.jobs.trim_probe"].function == "trim_probe"
    assert [entry.name for entry in schedule_entries()] == sorted(entries)


def test_an_async_schedule_runs_on_the_shared_loop() -> None:
    """Hàm lịch `async` đi qua cùng đường chạy với task `async`."""
    RUNS.clear()
    sweep_probe.apply()

    assert RUNS == ["sweep_probe"]


def test_a_sync_schedule_runs_too() -> None:
    """Hàm lịch đồng bộ chạy được qua task Celery."""
    RUNS.clear()
    trim_probe.apply()

    assert RUNS == ["trim_probe"]


def test_discover_submodules_imports_one_level_down(probe_package: Path) -> None:
    """Chỉ nhập `<gói con>.tasks` một cấp, không nhập module lẻ của gói."""
    discover_submodules(PROBE, "tasks")

    assert f"{PROBE}.with_tasks.tasks" in sys.modules
    assert f"{PROBE}.plain" not in sys.modules


def test_a_package_without_the_submodule_is_skipped(probe_package: Path) -> None:
    """Gói con không có `tasks` thì bỏ qua, không ném."""
    discover_submodules(PROBE, "tasks")

    assert f"{PROBE}.without_tasks.tasks" not in sys.modules


def test_a_missing_package_is_not_an_error() -> None:
    """Gói gốc chưa tồn tại không phải lỗi (app chưa dựng)."""
    discover_submodules("khong_co_goi_nay", "tasks")


def test_a_submodule_that_fails_to_import_is_reported(probe_package: Path) -> None:
    """Nuốt lỗi nhập ở đây nghĩa là một task biến mất khỏi sổ mà không ai biết."""
    (probe_package / "with_tasks" / "tasks.py").write_text("import khong_co_thu_vien_nay\n", encoding="utf-8")

    with pytest.raises(ModuleNotFoundError, match="khong_co_thu_vien_nay"):
        discover_submodules(PROBE, "tasks")


def test_discover_jobs_tolerates_apps_that_do_not_exist_yet() -> None:
    """`discover_jobs` chạy được khi một số app `jobs` chưa tồn tại."""
    discover_jobs()


def test_discover_worker_tasks_registers_a_known_worker_task() -> None:
    """Tiến trình mới chưa nhập task nào của `apps/worker`: một lời gọi nạp chúng vào sổ Celery như worker thật.

    Chạy trong tiến trình con (khuôn `test_register_tasks__module_not_imported_before`): trong tiến trình
    pytest, `pipeline.orchestrate.start` là `shared_task` đã vào sổ khi một test trước nhập
    `apps.worker.pipeline_orchestrate.tasks`, nên khẳng định tại chỗ xanh kể cả khi hàm không làm gì (N2).
    """
    probe = (
        "import sys\n"
        "from celery import current_app\n"
        "from packages.messaging.schedules import discover_worker_tasks\n"
        "assert 'apps.worker.pipeline_orchestrate.tasks' not in sys.modules\n"
        "discover_worker_tasks()\n"
        "print('pipeline.orchestrate.start' in current_app.tasks)\n"
    )
    result = subprocess.run(  # noqa: S603 — lệnh cố định: python của môi trường + đoạn mã trong test
        [sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=120
    )
    assert result.stdout.strip() == "True"
