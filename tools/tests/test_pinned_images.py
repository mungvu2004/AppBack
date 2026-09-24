"""`tools/pinned_images.py`: nguồn hằng ảnh ghim dùng chung (NO-106) — chỉ kiểm dạng ghim (K29)."""

from tools import pinned_images


def test_images_are_pinned_not_latest() -> None:
    for image in (pinned_images.POSTGRES_IMAGE, pinned_images.REDIS_IMAGE, pinned_images.MINIO_IMAGE):
        assert not image.endswith(":latest")
        assert ":" in image.rsplit("/", 1)[-1]
