"""Điểm vào của tiến trình worker và của beat.

    celery -A apps.worker.celery_main worker -Q default,pipeline.cpu
    celery -A apps.worker.celery_main beat -s /tmp/celerybeat-schedule

Ảnh `worker` **không** cài `torch`/`ultralytics`, nên module này chỉ dò task dưới
`apps/worker/*` và lịch dưới `apps/api/*`, `apps/worker/*`; task ML do
`apps/ml/celery_main.py` (B5-01) nạp bằng cùng `create_celery`. Beat ghi sổ lịch ở
`/tmp` vì gốc ảnh chỉ đọc.
"""

from celery.signals import worker_init

from packages.messaging.celery_app import create_celery
from packages.messaging.redis import assert_broker_policy, broker_redis_sync
from packages.messaging.schedules import beat_schedule, discover_jobs, discover_submodules

app = create_celery("worker")

# Nhập để `shared_task` của các module chủ vào sổ trước khi worker công bố hàng đợi.
discover_submodules("apps.worker", "tasks")
discover_jobs()

app.conf.beat_schedule = beat_schedule()


@worker_init.connect
def check_broker_policy(**_: object) -> None:
    """Dừng worker ngay nếu broker được phép đuổi khoá — thà không chạy còn hơn mất việc."""
    client = broker_redis_sync()
    try:
        assert_broker_policy(client)
    finally:
        client.close()
