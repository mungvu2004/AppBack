"""Điểm mở rộng `discover`/`override`/`resolve` (BE-00 §2.2)."""

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import pytest

from apps.api.core import extensions
from packages.core.settings import reset_settings_cache

SUBMODULE: Final = "probe"
ATTR: Final = "PROBE"
REPO_ROOT: Final = Path(__file__).resolve().parents[4]

# Tiến trình con chặn đúng bốn gói của BE-00 §7 rồi nhập hai module mà hàm worker
# được phép nhập; in "ok" nếu cả hai vào được.
_BOUNDARY_CODE: Final = """
import sys

BLOCKED = {"fastapi", "starlette", "uvicorn", "jwt", "argon2"}


class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("bi chan: " + name)
        return None


sys.meta_path.insert(0, Blocker())
import apps.api.core.extensions  # noqa: E402
import apps.api.core.wire  # noqa: E402

print("ok")
"""


@pytest.fixture
def probe_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Hai gói con tạm dưới `apps.api` — không tạo file nào trong repo."""
    import apps.api

    for name in ("zz_beta", "zz_alpha"):
        package = tmp_path / name
        package.mkdir()
        (package / "__init__.py").write_text('"""gói tạm"""\n', encoding="utf-8")
        (package / f"{SUBMODULE}.py").write_text(f'"""probe"""\n{ATTR} = "{name}"\n', encoding="utf-8")
    # Một module phẳng (không phải gói) nằm cạnh: `discover` phải bỏ qua, không ném.
    (tmp_path / "zz_module_phang.py").write_text('"""module phẳng"""\n', encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(apps.api, "__path__", [*apps.api.__path__, str(tmp_path)])
    extensions.reset_cache()
    yield tmp_path
    for name in list(sys.modules):
        if ".zz_alpha" in name or ".zz_beta" in name:
            del sys.modules[name]
    extensions.reset_cache()


def test_discover_sorts_by_module_name(probe_package: Path) -> None:
    """Thứ tự là thứ tự tên module, để kết quả tất định giữa các lần chạy."""
    found = extensions.discover(SUBMODULE, ATTR)
    assert [value for _name, value in found] == ["zz_alpha", "zz_beta"]


def test_discover_uses_cache(probe_package: Path) -> None:
    """Lần thứ hai trả đúng cùng một danh sách (không dò đĩa lại)."""
    assert extensions.discover(SUBMODULE, ATTR) is extensions.discover(SUBMODULE, ATTR)


def test_missing_attr_raises(probe_package: Path) -> None:
    """Có file mà thiếu hằng → `RuntimeError`, không im lặng bỏ qua."""
    with pytest.raises(RuntimeError, match="thiếu KHAC"):
        extensions.discover(SUBMODULE, "KHAC")


def test_import_error_propagates(probe_package: Path) -> None:
    """Module có thật mà nhập hỏng thì lỗi phải nổi lên (không bắt `ImportError`)."""
    (probe_package / "zz_alpha" / f"{SUBMODULE}.py").write_text(
        '"""probe"""\nimport khong_co_goi_nay\n', encoding="utf-8"
    )
    extensions.reset_cache()
    with pytest.raises(ModuleNotFoundError, match="khong_co_goi_nay"):
        extensions.discover(SUBMODULE, ATTR)


def test_discover_skips_modules_without_the_file(probe_package: Path) -> None:
    """Gói con không có file điểm mở rộng thì không xuất hiện trong kết quả."""
    names = [name for name, _ in extensions.discover(SUBMODULE, ATTR)]
    assert all(name.endswith(f".{SUBMODULE}") for name in names)
    assert not any("core" in name for name in names)


def test_override_only_in_test_env(storage_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`override` là lối tiêm của test; ở `dev` nó phải hỏng."""
    app: Any = type("App", (), {})()
    extensions.override(app, SUBMODULE, [("giả", 1)])
    assert extensions.resolve(app, SUBMODULE, ATTR) == [("giả", 1)]

    monkeypatch.setenv("APP_ENV", "dev")
    reset_settings_cache()
    with pytest.raises(RuntimeError, match="APP_ENV=test"):
        extensions.override(app, SUBMODULE, [])


def test_resolve_falls_back_to_discover(storage_env: None, probe_package: Path) -> None:
    """App không có override, hay `app=None` → dò thật."""
    app: Any = type("App", (), {})()
    assert extensions.resolve(app, SUBMODULE, ATTR) == extensions.discover(SUBMODULE, ATTR)
    assert extensions.resolve(None, SUBMODULE, ATTR) == extensions.discover(SUBMODULE, ATTR)


def test_override_is_per_app(storage_env: None, probe_package: Path) -> None:
    """Override của app này không ảnh hưởng app kia."""
    first: Any = type("App", (), {})()
    second: Any = type("App", (), {})()
    extensions.override(first, SUBMODULE, [("chỉ-của-first", 1)])
    assert extensions.resolve(second, SUBMODULE, ATTR) == extensions.discover(SUBMODULE, ATTR)


def test_wire_and_extensions_import_without_web_packages() -> None:
    """Hàm worker nhập được `wire` và `extensions` khi bốn gói web bị chặn (BE-00 §7)."""
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", _BOUNDARY_CODE],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
