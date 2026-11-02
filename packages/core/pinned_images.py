"""Ảnh dịch vụ ghim dùng chung (K29, NO-106, NO-184): nguồn duy nhất cho
`packages/testing/fixtures/services.py` và `tools/ci/h2.py`.

Hằng thuần, không nhập gì — nằm ở tầng thấp (`packages.core`) để cả gói test lẫn công cụ nhập
xuôi chiều, không còn `packages.*` nhập ngược `tools.*`.
"""

from __future__ import annotations

POSTGRES_IMAGE = "postgres:16-alpine"
REDIS_IMAGE = "redis:7-alpine"
# MinIO đã lưu trữ bản cộng đồng: quay.io (401), Docker Hub và dl.min.io (410) không còn phát (02/11/2026).
# Bản sao nguyên ảnh quay.io cũ (digest sha256:8d70bc15…) trên GHCR của repo; không còn bản vá bảo mật.
MINIO_IMAGE = "ghcr.io/mungvu999-ctrl/minio:RELEASE.2025-09-07T16-13-09Z"
