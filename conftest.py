"""Conftest gốc: nạp mọi fixture dùng chung dưới packages/testing/fixtures/.

Prompt sau **không sửa** file này (BE-01 [7]); thêm fixture bằng file mới
trong packages/testing/fixtures/, conftest này tự dò và nạp theo tên.
"""

from pathlib import Path

_FIXTURES_DIR = Path(__file__).parent / "packages" / "testing" / "fixtures"

pytest_plugins = [
    f"packages.testing.fixtures.{path.stem}" for path in sorted(_FIXTURES_DIR.glob("*.py")) if path.stem != "__init__"
]
