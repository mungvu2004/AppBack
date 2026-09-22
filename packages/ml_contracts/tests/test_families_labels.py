"""Bảng họ và nhãn khớp lõi và miền (gương FE): bước pipeline, loại đồ, loại ô mở, kiểu mở."""

from typing import get_args

from packages.core.pipeline import PIPELINE_STEPS
from packages.domain.spatial.model import Furniture, Opening
from packages.ml_contracts.families import (
    BASE_MODELS,
    FAMILY_METRIC,
    FAMILY_STEP,
    MODEL_FAMILIES,
    TRAINABLE_FAMILIES,
)
from packages.ml_contracts.labels import COCO_TO_LABEL, DETECTION_LABELS, LABEL_TARGETS, OBJECT_LABELS


def test_families_are_pipeline_steps() -> None:
    """Họ trùng id bước FE (`pipeline.ts:48-55`), theo đúng thứ tự bước."""
    steps = [step for step, _ in PIPELINE_STEPS]
    assert list(MODEL_FAMILIES) == steps[1:4]
    assert dict(FAMILY_STEP) == {family: family for family in MODEL_FAMILIES}
    assert MODEL_FAMILIES[:2] == TRAINABLE_FAMILIES
    assert set(BASE_MODELS) == set(TRAINABLE_FAMILIES)
    assert set(FAMILY_METRIC) == set(MODEL_FAMILIES)
    assert len(set(FAMILY_METRIC.values())) == 3


def test_object_labels_are_the_yolo_class_order() -> None:
    assert OBJECT_LABELS[:3] == ("door", "double_door", "window")
    assert OBJECT_LABELS[-1] == "stair"
    assert len(OBJECT_LABELS) == 10
    assert (*OBJECT_LABELS, "other") == DETECTION_LABELS
    assert set(COCO_TO_LABEL.values()) <= set(DETECTION_LABELS)
    assert COCO_TO_LABEL["dining table"] == "table"
    assert COCO_TO_LABEL["sink"] == COCO_TO_LABEL["toilet"] == "sanitary_fixture"


def test_label_targets_match_the_domain() -> None:
    """Đích của mọi nhãn là loại có thật trong mô hình miền (`types.ts:135-163`)."""
    furniture_kinds = set(get_args(Furniture.model_fields["kind"].annotation))
    opening_kinds = set(get_args(Opening.model_fields["kind"].annotation))
    swings = set(get_args(Opening.model_fields["swing"].annotation))
    assert set(LABEL_TARGETS) == set(DETECTION_LABELS)
    for label, target in LABEL_TARGETS.items():
        if target.category == "opening":
            assert target.domain_kind in opening_kinds
            assert target.swing in swings
            assert target.height_mm is not None
        else:
            assert target.domain_kind in furniture_kinds, label
            assert (target.width_mm, target.height_mm, target.sill_mm, target.swing) == (None, None, None, None)
    assert LABEL_TARGETS["door"].width_mm == 900
    assert LABEL_TARGETS["double_door"].width_mm is None
    assert (LABEL_TARGETS["window"].width_mm, LABEL_TARGETS["window"].sill_mm) == (1200, 900)
    assert LABEL_TARGETS["kitchen_cabinet"].domain_kind == "kitchenCabinet"
