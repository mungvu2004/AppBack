"""apps.worker.datasets — vẽ nhãn và ghi mẫu dataset ML từ tầng đã duyệt (B6-02).

Không nhập gì ở đây: `apps.worker.celery_main` tự dò `tasks`/`jobs` theo tên module
(`packages.messaging.schedules.discover_submodules`), nạp sớm thứ này sẽ kéo `cv2`/`numpy`
vào mọi tiến trình dò module dù không dùng.
"""
