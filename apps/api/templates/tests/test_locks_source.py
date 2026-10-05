"""NO-247: `templates` không nhập khoá từ module anh em `measurements` — khoá ở `packages.db.locks`."""

import inspect

from apps.api.templates import service
from packages.db import locks


def test_templates_service__lock_comes_from_packages_db() -> None:
    """`service.py` không nhập `apps.api.measurements.locks`."""
    assert "measurements.locks" not in inspect.getsource(service)


def test_templates_service__lock_is_the_packages_db_function() -> None:
    """Hành vi, không chỉ chuỗi nguồn: tên `lock_project_scope` trong `service` chính là hàm của `packages.db.locks`."""
    assert vars(service)["lock_project_scope"] is locks.lock_project_scope
