"""Điểm vào worker: nạp đúng thứ cần nạp, và từ chối chạy trên broker sai chính sách."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from packages.messaging.celery_app import AFTER_COMMIT_INLINE_ENV
from packages.messaging.settings import get_messaging_settings, reset_messaging_settings_cache

REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE = """
import json
import os
import sys

import apps.worker.celery_main as main
from packages.messaging.schedules import beat_schedule

print(json.dumps({
    "ml": [name for name in sys.modules if name == "apps.ml" or name.startswith("apps.ml.")],
    "web": [name for name in ("fastapi", "starlette", "uvicorn", "jwt", "argon2") if name in sys.modules],
    "beat": list(main.app.conf.beat_schedule),
    "beat_ledger": list(beat_schedule()),
    "inline": os.environ.get("DB_AFTER_COMMIT_INLINE"),
    "pipeline_queue": main.app.conf.task_routes[0]("pipeline.x", [], {}, {})["queue"],
}))
"""


def import_worker(broker_url: str) -> dict[str, Any]:
    """Nhập `celery_main` trong một tiến trình Python mới (BE-00 §12) và soi những gì nó nạp."""
    env = {key: value for key, value in os.environ.items() if key != AFTER_COMMIT_INLINE_ENV}
    env |= {"PYTHONPATH": str(REPO_ROOT), "REDIS_BROKER_URL": broker_url, "REDIS_CACHE_URL": broker_url}
    result = subprocess.run(  # noqa: S603 — lệnh cố định: python của môi trường + mã trong repo
        [sys.executable, "-c", PROBE], capture_output=True, text=True, check=True, cwd=REPO_ROOT, env=env
    )
    loaded: dict[str, Any] = json.loads(result.stdout)
    return loaded


def test_the_worker_process_never_pulls_in_the_ml_app(messaging_env: None) -> None:
    """Ảnh `worker` không cài `torch` hay thư viện web; nhập chúng ở đây là hỏng lúc chạy thật."""
    loaded = import_worker(get_messaging_settings().redis_broker_url)

    assert loaded["ml"] == []
    assert loaded["web"] == []


def test_the_worker_process_is_ready_to_run_schedules(messaging_env: None) -> None:
    """Sổ lịch của `packages.messaging` phải được gắn vào app, và định tuyến phải chạy.

    So hai giá trị đọc trong **cùng** tiến trình con, không ghim danh sách: số lịch
    tăng theo từng prompt chủ của bảng "Dọn rác" (BE-00 §7).
    """
    loaded = import_worker(get_messaging_settings().redis_broker_url)

    assert loaded["beat"] == loaded["beat_ledger"]
    assert loaded["pipeline_queue"] == "pipeline.cpu"
    assert loaded["inline"] == "1"


def test_the_worker_refuses_a_broker_that_evicts_keys(
    messaging_env: None, monkeypatch: pytest.MonkeyPatch, redis_cache_url: str
) -> None:
    """Nhập tại chỗ: nhập ở mức module sẽ dựng app Celery ngay lúc thu thập test."""
    from apps.worker.celery_main import check_broker_policy

    check_broker_policy()

    monkeypatch.setenv("REDIS_BROKER_URL", redis_cache_url)
    reset_messaging_settings_cache()
    try:
        with pytest.raises(RuntimeError, match="noeviction"):
            check_broker_policy()
    finally:
        reset_messaging_settings_cache()
