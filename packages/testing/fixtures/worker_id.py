"""Mã tiến trình xdist: một hằng, một cách đọc, không tác dụng phụ lúc nhập (FIX-114, review F-3).

`db.py` (tên database mỗi tiến trình) và `services.py` (dịch vụ dùng chung) đều phải biết tiến
trình xdist nào đang chạy. Để hằng ở `services.py` thì `db.py` nhập nó là kéo theo `filelock`,
`testcontainers` **và** tác dụng phụ `testcontainers_config.ryuk_disabled = True` — module CSDL
hoá ra phụ thuộc module container, ngược hướng. Module này chỉ có `os`, nên nhập từ đâu cũng rẻ
và không đổi trạng thái gì.

Đọc biến môi trường chứ không lấy fixture `worker_id` của pytest-xdist: mã ở đây còn phải chạy
khi `-p no:xdist` và ở ngoài thân test (fixture phiên, hàm trợ giúp).
"""

import os

XDIST_WORKER_ENV = "PYTEST_XDIST_WORKER"


def xdist_worker_id() -> str:
    """Mã tiến trình xdist (`gw0`, `gw11`…), hay chuỗi rỗng khi chạy ngoài `pytest -n`.

    Cắt khoảng trắng: giá trị chỉ toàn khoảng trắng được coi như không có, để nó không lọt vào
    tên database hay khoá file dùng chung.
    """
    return os.environ.get(XDIST_WORKER_ENV, "").strip()
