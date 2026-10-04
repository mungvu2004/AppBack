"""CLI `import` (B6-02b [2]): mã thoát, báo cáo stdout, mã lỗi stderr, nhập module không tác dụng phụ.

`cli.main` chạy trong luồng riêng (`asyncio.to_thread`) vì nó gọi `asyncio.run` — không lồng
được vào vòng lặp của test. Môi trường tiến trình (DB test, kho local trong `tmp_path`) theo
khuôn `apps/api/admin_ml_registry/tests/test_jobs.py`.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.worker.datasets_cubicasa import cli
from apps.worker.datasets_cubicasa.tests.fake_cubicasa import new_dataset, write_dataset
from packages.core.settings import reset_settings_cache
from packages.db.settings import reset_database_settings_cache
from packages.storage.settings import reset_storage_settings_cache

Maker = async_sessionmaker[AsyncSession]
LAYOUT = {"high_quality": ["101", "102"], "colorful": ["7"]}


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường của tiến trình lệnh: DB test riêng, kho local và thư mục tạm trong `tmp_path`."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-cubicasa-import-001")
    monkeypatch.setenv("CUBICASA_WORK_DIR", str(tmp_path / "work"))
    caches = (reset_settings_cache, reset_database_settings_cache, reset_storage_settings_cache)
    for reset in caches:
        reset()
    yield
    for reset in caches:
        reset()


@pytest.fixture
def src(tmp_path: Path) -> Path:
    """Nguồn giả ba mẫu, hai subset — đủ để báo cáo có cả split lẫn phân bố `ink_ratio`."""
    root = tmp_path / "src"
    root.mkdir()
    return write_dataset(root, LAYOUT)


@pytest.mark.usefixtures("process_env")
async def test_import_prints_report_and_exits_zero(
    db_sessionmaker: Maker, src: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lượt nhập thành công → thoát 0; stdout có id bản, giấy phép CC BY-NC, split và phân bố `ink_ratio`."""
    dataset_id = await new_dataset(db_sessionmaker)

    code = await asyncio.to_thread(cli.main, ["import", "--src", str(src), "--dataset", dataset_id])

    captured = capsys.readouterr()
    assert (code, captured.err) == (0, "")
    assert "dsv_" in captured.out
    assert "license: CC-BY-NC-4.0 " in captured.out
    assert "splits: " in captured.out
    assert "ink_ratio[high_quality]: n=" in captured.out
    assert "unknown_fixtures: BaseCabinet=3" in captured.out


@pytest.mark.usefixtures("process_env")
async def test_import_exits_two_for_an_unknown_dataset(src: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Dataset không có → thoát 2, `DATASET_NOT_FOUND` ra stderr."""
    code = await asyncio.to_thread(cli.main, ["import", "--src", str(src), "--dataset", "dst_x"])

    captured = capsys.readouterr()
    assert code == 2
    assert "DATASET_NOT_FOUND" in captured.err


@pytest.mark.usefixtures("process_env")
async def test_import_exits_one_over_the_sample_cap(
    db_sessionmaker: Maker, src: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`CUBICASA_MAX_SAMPLES=2` với 3 mẫu → thoát 1, `failureCode=DATASET_TOO_LARGE` ra stderr."""
    monkeypatch.setenv("CUBICASA_MAX_SAMPLES", "2")
    dataset_id = await new_dataset(db_sessionmaker)

    code = await asyncio.to_thread(cli.main, ["import", "--src", str(src), "--dataset", dataset_id])

    captured = capsys.readouterr()
    assert code == 1
    assert "DATASET_TOO_LARGE" in captured.err


@pytest.mark.parametrize(
    "argv",
    [["import", "--dataset", "dst_x"], ["import", "--src", ".", "--dataset", "d", "--limit", "0"]],
)
def test_import_rejects_bad_arguments(argv: list[str]) -> None:
    """Thiếu `--src` hay `--limit 0` → argparse thoát 2 trước khi chạm DB hay kho."""
    with pytest.raises(SystemExit) as caught:
        cli.main(argv)

    assert caught.value.code == 2


def test_importing_the_module_has_no_side_effects(tmp_path: Path) -> None:
    """Nhập `cli` với `DATABASE_URL` hỏng vẫn thoát 0: mọi việc nằm trong `main()` (BE-00 §5)."""
    env = {**os.environ, "PYTHONPATH": str(Path.cwd()), "DATABASE_URL": "khong-phai-dsn", "APP_ENV": "test"}
    result = subprocess.run(
        [sys.executable, "-c", "import apps.worker.datasets_cubicasa.cli"],
        check=False,
        capture_output=True,
        cwd=tmp_path,
        env=env,
    )

    assert (result.returncode, result.stderr) == (0, b"")


@pytest.mark.usefixtures("process_env")
async def test_import_honours_the_limit_flag(
    db_sessionmaker: Maker, src: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--limit 2` phân tích được (nguyên ≥ 1) và chỉ nhập hai mẫu."""
    dataset_id = await new_dataset(db_sessionmaker)

    code = await asyncio.to_thread(cli.main, ["import", "--src", str(src), "--dataset", dataset_id, "--limit", "2"])

    assert code == 0
    assert "train=2" in capsys.readouterr().out


def test_distribution_of_an_empty_series() -> None:
    """Dãy rỗng chỉ in `n=0` (không có mẫu nào thì không có phân vị nào để chia)."""
    assert cli._distribution(()) == "n=0"
