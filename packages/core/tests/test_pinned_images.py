"""`packages/core/pinned_images.py`: nguồn hằng ảnh ghim dùng chung (NO-106) — chỉ kiểm dạng ghim (K29)."""

from packages.core import pinned_images


def test_images_are_pinned_not_latest() -> None:
    """Mỗi ảnh ghim có tag cụ thể, không `:latest`."""
    for image in (pinned_images.POSTGRES_IMAGE, pinned_images.REDIS_IMAGE, pinned_images.MINIO_IMAGE):
        assert not image.endswith(":latest")
        assert ":" in image.rsplit("/", 1)[-1]
