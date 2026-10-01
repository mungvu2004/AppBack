"""Job huấn luyện: N32-N37 (B6-03a). Cầu nối ghi tiến trình ở `apps/worker/training_bridge`.

`settings.py`, `errors.py` không nhập `fastapi`: worker nhập thẳng hai file này (như
`apps/worker/datasets` nhập `admin_ml_datasets`) mà vẫn qua test ranh giới của BE-00 §7.
"""
