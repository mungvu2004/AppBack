"""NO-247: `measurements` gọi khoá dùng chung ở `packages.db.locks`, không giữ bản riêng."""

import importlib.util


def test_measurements__has_no_private_locks_module() -> None:
    """`apps.api.measurements.locks` đã chuyển về `packages.db.locks`."""
    assert importlib.util.find_spec("apps.api.measurements.locks") is None
