"""Dataset và phiên bản bất biến: N28-N31, hàm dùng lại cho `apps/worker/datasets` (B6-02).

`versions.py` là nguồn duy nhất ghi `dataset_versions` (BE-00 §7): worker nhập thẳng bốn
hàm ở đó, không qua HTTP. `router.py`, `schemas.py`, `service.py` chỉ là mặt HTTP.
"""
