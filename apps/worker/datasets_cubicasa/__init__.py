"""apps.worker.datasets_cubicasa — lệnh nhập CubiCasa5K thành phiên bản dataset bất biến (B6-02b).

Không task, không lịch: người vận hành chạy `python -m apps.worker.datasets_cubicasa.cli import`
trong container worker. Không nhập gì ở đây (như `apps.worker.datasets`): nhập gói không được
kéo `cv2`/`numpy` hay chạm DB.
"""
