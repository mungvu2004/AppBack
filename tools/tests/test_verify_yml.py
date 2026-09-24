"""`deploy/compose/verify.yml`: một ảnh + một volume dùng chung giữa các worktree (NO-108).

Quét tĩnh YAML — không dựng container, không so hai lượt verify song song thật (host chỉ cho
tối đa 2 `verify-run`, phép thử đó là việc của cổng đầy đủ ở reviewer, không phải test đơn vị này).
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_YML = REPO_ROOT / "deploy" / "compose" / "verify.yml"


def _load() -> dict:  # type: ignore[type-arg]
    return yaml.safe_load(VERIFY_YML.read_text(encoding="utf-8"))


def test_verify_yml_volume_has_fixed_shared_name() -> None:
    """Thiếu `name:` thì compose tự gắn tiền tố project (`appback-verify-<worktree>_appback-work`)
    — mỗi worktree một volume riêng thay vì một `/work` dùng chung (đo 2026-09-24: 42 volume, 76,6 GB)."""
    doc = _load()
    assert doc["volumes"]["appback-work"]["name"] == "appback-work"


def test_verify_yml_service_has_fixed_non_latest_image() -> None:
    """`image:` cố định cho service `verify` — mọi worktree build ra cùng một tên ảnh thay vì tên
    riêng theo project compose; không dùng tag `latest` (K29)."""
    doc = _load()
    image = doc["services"]["verify"]["image"]
    assert image
    assert not image.endswith(":latest")
