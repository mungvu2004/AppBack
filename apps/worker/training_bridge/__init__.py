"""apps.worker.training_bridge — cầu nối runner huấn luyện ↔ DB và ba lịch của job (B6-03a).

Không nhập gì ở đây: `apps.worker.celery_main` tự dò `tasks`/`jobs` theo tên module
(`packages.messaging.schedules.discover_submodules`). Gói này không nhập `fastapi`,
`starlette`, `jwt`, `argon2` (BE-00 §7, test ranh giới), không nhập `apps.ml` (B6-03b).
"""
