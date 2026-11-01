"""Payload `bake.lighting.run`: tên task đi hàng `bake`, id sai mẫu hay khoá lạ bị từ chối."""

import pytest
from pydantic import ValidationError

from packages.messaging.celery_app import queue_for
from packages.messaging.payloads.lighting_bake import (
    LIGHTING_BAKE_FILES,
    LIGHTING_BAKE_INPUT,
    LIGHTING_BAKE_TASK,
    LightingBakePayload,
)

BAKE = "bak_01ARZ3NDEKTSV4RRFFQ69G5FJC"


def test_lighting_bake_task__routes_to_the_bake_queue() -> None:
    """Tên task suy ra hàng `bake`, nên chỉ worker bake (có Blender) nhận việc."""
    assert queue_for(LIGHTING_BAKE_TASK) == "bake"


def test_lighting_bake_payload__round_trips_as_json() -> None:
    """Payload hợp lệ mang `schema_version` 1 và đi qua JSON nguyên vẹn."""
    payload = LightingBakePayload(bake_id=BAKE)
    assert payload.model_dump(mode="json") == {"schema_version": 1, "bake_id": BAKE}
    assert LightingBakePayload.model_validate_json(payload.model_dump_json()) == payload


@pytest.mark.parametrize(
    "data",
    [
        {"bake_id": "dsv_01ARZ3NDEKTSV4RRFFQ69G5FJC"},  # sai tiền tố
        {"bake_id": "bak_khong-phai-ulid"},
        {"bake_id": BAKE, "project_id": "prj_01ARZ3NDEKTSV4RRFFQ69G5FAV"},  # khoá lạ
    ],
)
def test_lighting_bake_payload__rejects_bad_messages(data: dict[str, str]) -> None:
    """Id sai mẫu `bak_<ULID>` hay khoá ngoài hợp đồng → `ValidationError` (thông điệp độc)."""
    with pytest.raises(ValidationError):
        LightingBakePayload.model_validate(data)


def test_lighting_bake_files__are_single_segment_names_distinct_from_the_input() -> None:
    """Ba tệp đầu ra cố định, không trùng tên GLB đầu vào."""
    assert LIGHTING_BAKE_FILES == ("baked.glb", "lightmap.png", "manifest.json")
    assert LIGHTING_BAKE_INPUT not in LIGHTING_BAKE_FILES
