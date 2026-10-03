"""Ảnh dịch vụ ghim dùng chung (K29, NO-106, NO-184): nguồn duy nhất cho
`packages/testing/fixtures/services.py` và `tools/ci/h2.py`.

Hằng thuần, không nhập gì — nằm ở tầng thấp (`packages.core`) để cả gói test lẫn công cụ nhập
xuôi chiều, không còn `packages.*` nhập ngược `tools.*`.
"""

from __future__ import annotations

POSTGRES_IMAGE = "postgres:16-alpine"
REDIS_IMAGE = "redis:7-alpine"
# Docker Hub minio/minio không còn phát hành bản cộng đồng; quay.io là nguồn chính thức.
MINIO_IMAGE = "quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
