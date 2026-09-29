"""Hằng dùng chung của test route dataset ML (B6-02, việc B) — một bản cho các file test."""

from typing import Final

DATASETS_PATH: Final = "/api/admin/ml/datasets"
DATASET_QUEUE: Final = "default"
"""Hàng đợi của `default.datasets.build_version` (`packages/messaging/celery_app.py:31`)."""

WALL: Final = "wallSegmentation"
OPENING: Final = "openingAndFurnitureDetection"
DIMENSION: Final = "dimensionReading"


def versions_path(dataset_id: str) -> str:
    """`/api/admin/ml/datasets/{dataset_id}/versions`."""
    return f"{DATASETS_PATH}/{dataset_id}/versions"
