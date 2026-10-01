"""Điều phối pipeline, nửa sau (B5-06c): nhận kết quả bước, quét bù lượt kẹt, dọn artifact `runs/`.

Không có hàm cho prompt sau. `celery_main` nạp `tasks` và `jobs` qua `discover_submodules`,
nên gói không nhập lại chúng ở đây.
"""
