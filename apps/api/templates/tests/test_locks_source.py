"""NO-247: `templates` không nhập khoá từ module anh em `measurements` — khoá ở `packages.db.locks`."""

import inspect

from apps.api.templates import service


def test_templates_service__lock_comes_from_packages_db() -> None:
    """`service.py` không nhập `apps.api.measurements.locks`."""
    assert "measurements.locks" not in inspect.getsource(service)
