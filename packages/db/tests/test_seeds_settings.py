"""Seed tự dò và `DatabaseSettings`."""

import importlib
import secrets
import sys
from pathlib import Path
from typing import Final, cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import load_all_models, model_modules
from packages.db.seeds import apply_seeds, load_seeds
from packages.db.seeds.__main__ import main as seeds_main
from packages.db.settings import DatabaseSettings, get_database_settings, reset_database_settings_cache

URL = "postgresql+asyncpg://u:p@localhost:5432/appback"

SEED_TEMPLATE = """\
ORDER = {order}
ENVS = frozenset({envs!r})


async def seed(session):
    session.append({name!r})
"""


@pytest.fixture
def seed_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Gói seed tạm, tên duy nhất mỗi test: sys.modules nhớ gói theo tên."""
    package = tmp_path / f"seedpkg_{secrets.token_hex(4)}"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    return package


def _write(package: Path, name: str, *, order: int, envs: tuple[str, ...] = ("ci", "dev")) -> None:
    package.joinpath(f"{name}.py").write_text(
        SEED_TEMPLATE.format(order=order, envs=sorted(envs), name=name), encoding="utf-8"
    )


def test_load_seeds_sorted_by_order_then_name(seed_package: Path) -> None:
    _write(seed_package, "b_late", order=2)
    _write(seed_package, "a_late", order=2)
    _write(seed_package, "z_early", order=1)
    assert [seed.name for seed in load_seeds("ci", seed_package, seed_package.name)] == ["z_early", "a_late", "b_late"]


def test_load_seeds_filters_by_env(seed_package: Path) -> None:
    _write(seed_package, "demo", order=1, envs=("dev",))
    _write(seed_package, "core", order=1, envs=("ci", "production"))
    assert [seed.name for seed in load_seeds("ci", seed_package, seed_package.name)] == ["core"]
    assert [seed.name for seed in load_seeds("production", seed_package, seed_package.name)] == ["core"]
    assert [seed.name for seed in load_seeds("dev", seed_package, seed_package.name)] == ["demo"]


@pytest.mark.parametrize(
    ("body", "missing"),
    [
        ("ORDER = 1\n", "seed, ENVS"),
        ("ENVS = frozenset({'ci'})\n", "seed, ORDER"),
        ("ORDER = 1\nENVS = frozenset({'ci'})\n", "seed"),
    ],
)
def test_load_seeds_requires_all_attributes(seed_package: Path, body: str, missing: str) -> None:
    seed_package.joinpath("broken.py").write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match=f"thiếu {missing}"):
        load_seeds("ci", seed_package, seed_package.name)


def test_load_seeds_rejects_wrong_envs_type(seed_package: Path) -> None:
    seed_package.joinpath("odd.py").write_text(
        "ORDER = 1\nENVS = 'ci'\n\n\nasync def seed(session):\n    pass\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="ENVS phải là frozenset"):
        load_seeds("ci", seed_package, seed_package.name)


async def test_apply_seeds_runs_in_order(seed_package: Path) -> None:
    _write(seed_package, "second", order=2)
    _write(seed_package, "first", order=1)
    recorder: list[str] = []
    names = await apply_seeds(cast("AsyncSession", recorder), "ci", seed_package, seed_package.name)
    assert names == ("first", "second")
    assert recorder == ["first", "second"]


APP_ENVS: Final = ("dev", "test", "ci", "staging", "production")
"""Tập `APP_ENV` hợp lệ của `packages/core/settings.py:25` — `ENVS` của seed phải nằm trong đây."""


@pytest.mark.parametrize("env", APP_ENVS)
def test_repo_seeds_load_in_every_env(env: str) -> None:
    """Mọi seed **thật** của repo nạp được ở mọi môi trường, tên duy nhất, `ENVS` hợp lệ.

    Không liệt kê tên seed: danh sách ấy đổi mỗi lần một prompt thêm seed của mình, và chốt
    nó lại là dựng đúng cái bất biến giòn mà FIX-108 gỡ. Bất biến thật của bộ dò là "đọc
    được và khai đủ", nên repo chưa có seed nào thì mọi vòng lặp rỗng và test vẫn xanh.
    """
    seeds = load_seeds(env)
    names = [seed.name for seed in seeds]
    assert len(names) == len(set(names))
    for seed in seeds:
        assert isinstance(seed.envs, frozenset)
        assert seed.envs <= frozenset(APP_ENVS)
        assert env in seed.envs


def test_repo_seeds_are_sorted_by_order_then_name() -> None:
    """Thứ tự chạy ổn định `(ORDER, tên)` trên chính cây seed của repo, bao nhiêu seed cũng đúng."""
    seeds = load_seeds("ci")
    assert list(seeds) == sorted(seeds, key=lambda seed: (seed.order, seed.name))


def test_repo_demo_seeds_never_reach_production() -> None:
    """Seed demo (không khai `production`) không bao giờ lọt vào lượt chạy `production`."""
    production = {seed.name for seed in load_seeds("production")}
    demo = {seed.name for seed in load_seeds("dev") if "production" not in seed.envs}
    assert production & demo == set()


# --- DatabaseSettings ----------------------------------------------------------


def test_settings_defaults() -> None:
    settings = DatabaseSettings(database_url=URL)
    assert (settings.db_pool_size, settings.db_max_overflow, settings.db_pool_timeout_s) == (10, 5, 5)
    assert (settings.db_statement_timeout_ms, settings.db_lock_timeout_ms) == (10000, 5000)
    assert (settings.db_connect_timeout_s, settings.db_after_commit_workers) == (10, 8)


@pytest.mark.parametrize("url", ["postgresql://u@h/db", "postgres://u@h/db", "sqlite+aiosqlite:///x.db", ""])
def test_settings_require_asyncpg_driver(url: str) -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        DatabaseSettings(database_url=url)


def test_settings_read_env_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("DB_POOL_SIZE", "3")
    reset_database_settings_cache()
    try:
        first = get_database_settings()
        assert first.db_pool_size == 3
        assert get_database_settings() is first
        monkeypatch.setenv("DB_POOL_SIZE", "7")
        reset_database_settings_cache()
        assert get_database_settings().db_pool_size == 7
    finally:
        reset_database_settings_cache()


# --- CLI và bộ nạp model -------------------------------------------------------


def test_seeds_main_requires_app_env(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    assert seeds_main() == 2
    assert "thiếu APP_ENV" in capsys.readouterr().out


def test_seeds_main_reports_what_it_ran(
    db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI chạy đúng những seed `load_seeds` tìm được và nói tên chúng ra; repo rỗng → câu "không có".

    Dòng in so với `load_seeds("ci")` chứ không với một danh sách chép tay: cùng lý do với
    `test_repo_seeds_load_in_every_env` (FIX-108) — số seed của repo đổi theo từng prompt.
    """
    monkeypatch.setenv("APP_ENV", "ci")
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        assert seeds_main() == 0
    finally:
        reset_database_settings_cache()
    names = [seed.name for seed in load_seeds("ci")]
    expected = ", ".join(names) if names else "không có seed nào"
    assert capsys.readouterr().out.splitlines() == [f"seed ci: {expected}"]


def test_load_all_models_imports_every_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / f"modelpkg_{secrets.token_hex(4)}"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "thing.py").write_text("LOADED = True\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    assert model_modules(package) == ["thing"]
    load_all_models(package, package.name)
    assert sys.modules[f"{package.name}.thing"].LOADED is True
