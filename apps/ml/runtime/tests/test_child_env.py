"""`allowlisted_env`: một nguồn lọc môi trường cho tiến trình con của `ml` (NO-326, R-07)."""

import os

import pytest

from apps.ml.runtime.child_env import allowlisted_env


def test_allowlisted_env_keeps_names_and_prefixes_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Giữ tên trong `keep` và biến mang tiền tố trong `prefixes`; bí mật khác không lọt; `PYTHONPATH` luôn có."""
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s3cret")
    monkeypatch.setenv("KEEP_ME", "1")
    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.delenv("PYTHONPATH", raising=False)
    env = allowlisted_env(frozenset({"KEEP_ME"}), ("ML_",))
    assert env == {"KEEP_ME": "1", "ML_DEVICE": "cpu", "PYTHONPATH": os.getcwd()}


def test_allowlisted_env_does_not_override_an_existing_pythonpath(monkeypatch: pytest.MonkeyPatch) -> None:
    """`PYTHONPATH` của tiến trình cha (qua `keep`) thắng giá trị mặc định `os.getcwd()`."""
    monkeypatch.setenv("PYTHONPATH", "/opt/appback")
    assert allowlisted_env(frozenset({"PYTHONPATH"}), ())["PYTHONPATH"] == "/opt/appback"
