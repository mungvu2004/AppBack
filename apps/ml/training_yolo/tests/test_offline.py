"""Cờ ngoại tuyến phải có hiệu lực trong một tiến trình Python **mới** (khối [8], BE-00 §12).

Trong tiến trình test, `ultralytics` thường đã được nhập bởi test khác, nên `AUTOINSTALL`/`ONLINE`
đọc ở đó không chứng minh được gì: chúng là hằng tính một lần lúc nhập. Vì vậy test này chạy
`prepare_ultralytics()` qua `subprocess` rồi đọc ba hằng đó từ đầu ra.
"""

import os
import subprocess
import sys
import tempfile
from typing import Final

_PROBE: Final = """
from apps.ml.training_yolo.trainer import prepare_ultralytics

prepare_ultralytics()
from ultralytics.utils import AUTOINSTALL, ONLINE, USER_CONFIG_DIR

print(AUTOINSTALL, ONLINE, USER_CONFIG_DIR)
"""


def test_offline_env_subprocess() -> None:
    """Tiến trình mới: `AUTOINSTALL` và `ONLINE` là `False`, `USER_CONFIG_DIR` nằm dưới thư mục tạm."""
    completed = subprocess.run(  # noqa: S603 — argv cố định, không có dữ liệu ngoài
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )
    autoinstall, online, config_dir = completed.stdout.strip().splitlines()[-1].split(maxsplit=2)
    assert autoinstall == "False"
    assert online == "False"
    assert config_dir.startswith(tempfile.gettempdir())
