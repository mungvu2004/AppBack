"""`deploy/docker/verify.Dockerfile`: mọi `FROM` ghim tag cụ thể + digest (NO-175, K29).

Tag trần (vd `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`) trôi theo bản phát hành mới nhất —
đo 2026-09-24: uv 0.9.30 đổi cách hiển thị marker của `uv.lock` một-môi-trường, làm
`bash tools/verify/run.sh lock` sinh diff hàng trăm dòng dù không gói nào đổi bản.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "deploy" / "docker" / "verify.Dockerfile"

# `image:tag@sha256:...` — tag không được là "latest" hay thiếu hẳn.
_FROM_RE = re.compile(r"^FROM\s+(\S+)", re.MULTILINE)
_PINNED_RE = re.compile(r"^[^\s@]+:[^\s@:]+@sha256:[0-9a-f]{64}$")


def test_every_from_line_pins_tag_and_digest() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    images = _FROM_RE.findall(text)
    assert images, "không tìm thấy dòng FROM nào"
    for image in images:
        assert _PINNED_RE.match(image), f"FROM chưa ghim tag+digest: {image}"
        assert ":latest@" not in image, image
