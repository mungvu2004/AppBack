"""Điểm vào tiến trình worker `ml`.

    celery -A apps.ml.celery_main worker -Q ml.infer,ml.training

Nhập mọi `apps.ml.<module>.tasks` một cấp để `shared_task` vào sổ trước khi worker công
bố hàng. Lúc khởi động (`worker_init`): broker phải `noeviction`, và bộ giả
(`ML_BACKEND=fake`) không bao giờ chạy ở `staging`/`production` — ở đó nó sẽ trả đáp án
rỗng cho mọi bản vẽ thật mà không ai hay.
"""

from celery.signals import worker_init

from apps.ml.runtime.settings import get_ml_settings
from packages.core.settings import get_core_settings
from packages.messaging.celery_app import create_celery
from packages.messaging.redis import assert_broker_policy, broker_redis_sync
from packages.messaging.schedules import discover_submodules

app = create_celery("ml")

discover_submodules("apps.ml", "tasks")


def check_backend(app_env: str, backend: str) -> None:
    """Bộ giả chỉ cho dev/test/ci; ở `staging`/`production` → `RuntimeError`, worker không lên."""
    if backend == "fake" and app_env in ("staging", "production"):
        raise RuntimeError(f"ML_BACKEND=fake bị cấm ở APP_ENV={app_env}")


@worker_init.connect
def check_worker(**_: object) -> None:
    """Dừng worker ngay nếu broker được phép đuổi khoá hay đang bật bộ giả ở môi trường thật."""
    check_backend(get_core_settings().app_env, get_ml_settings().ml_backend)
    client = broker_redis_sync()
    try:
        assert_broker_policy(client)
    finally:
        client.close()
