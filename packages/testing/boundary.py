"""Hằng chung của test ranh giới nhập (R-07): một bản, khớp hợp đồng `.importlinter`.

`tools/tests/test_boundary_constants.py` giữ hai chiều: hằng khớp hợp đồng, và không test
nào tự chép lại tuple gói bị chặn (NO-240/NO-283 đều do bản chép thiếu `uvicorn`).
"""

from typing import Final

# Hợp đồng `worker-no-web`, `api-jobs-no-web`: worker và jobs không nhập các gói này.
WORKER_BLOCKED: Final = ("fastapi", "starlette", "uvicorn", "jwt", "argon2")

# Hợp đồng `api-cli-no-web`: CLI chạy trong ảnh api (có jwt, argon2) nhưng không dựng web.
CLI_BLOCKED: Final = ("fastapi", "starlette", "uvicorn")

# Thư viện của hợp đồng `domain-vision-isolated`: gói thuần domain/vision không nhập các thư viện này.
PURE_BLOCKED: Final = ("sqlalchemy", "fastapi", "celery", "torch")
