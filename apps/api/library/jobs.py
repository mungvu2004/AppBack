"""Lịch phát hành object thư viện .glb (B2-06 [6]; khuôn BE-00 §7 "Khuôn lịch nền").

`apps/worker` nhập module này để chạy beat, nên chỉ nhập `packages.*` và `assets` (không
`fastapi`, `starlette`, `jwt`, `argon2`). Lõi nằm ở `assets.run_library_publish`.
"""

from datetime import timedelta
from typing import Final

from apps.api.library.assets import open_storage, run_library_publish
from packages.core.clock import SystemClock
from packages.db.engine import worker_sessionmaker
from packages.messaging import periodic

TASK_NAME: Final = "default.library.publish_library_assets"
EVERY: Final = timedelta(minutes=1)


@periodic(TASK_NAME, every=EVERY)
async def publish_library_assets() -> None:
    """Hàm lịch: dựng tài nguyên thật rồi gọi lõi; báo cáo đã có log từng mục."""
    clock = SystemClock()
    await run_library_publish(worker_sessionmaker(), open_storage(clock), clock)
