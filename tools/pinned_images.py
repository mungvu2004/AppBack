"""Ảnh dịch vụ ghim dùng chung (K29, NO-106): nguồn duy nhất cho
`packages/testing/fixtures/services.py` và `tools/ci/h2.py`.

Không phải mã test — cả hai nơi trên đều được phép nhập module này (R-28 chỉ cấm nhập
`packages.testing` từ mã không phải test; `tools/pinned_images` nằm ngoài gói đó).
"""

from __future__ import annotations

POSTGRES_IMAGE = "postgres:16-alpine"
REDIS_IMAGE = "redis:7-alpine"
# Docker Hub minio/minio không còn phát hành bản cộng đồng; quay.io là nguồn chính thức.
MINIO_IMAGE = "quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
