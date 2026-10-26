"""`apps.api.spatial_read.readiness.readiness_of` — bảng ca của luật H5 §2.2 (FIX-P0-10).

Hàm thuần, không DB: mỗi lý do bật/tắt một ca; đường truy vấn `latest_run_facts` được kiểm qua
HTTP ở `test_routes_layer.py` (`__C01_readiness_*`).
"""

from collections.abc import Mapping
from dataclasses import replace

import pytest

from apps.api.spatial_read.assemble import effective_scale_source
from apps.api.spatial_read.documents import ScaleSource, empty_document
from apps.api.spatial_read.readiness import RunFacts, readiness_of
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.object_keys import model_prefix
from packages.domain.spatial import SpatialLayer
from packages.ml_contracts.families import MODEL_FAMILIES, ModelFamily
from packages.ml_contracts.payloads import ModelRef
from packages.testing.factories.pipeline_orchestrate import classic_ref
from packages.testing.factories.spatial import sample_floor_layer

LEVEL_ID = "L-LEVEL000000"
REVIEWED = sample_floor_layer(0, level_id=LEVEL_ID, reviewed=True)
UNREVIEWED = sample_floor_layer(0, level_id=LEVEL_ID)
CRITICAL: Mapping[str, object] = {"hasCritical": True, "criticalCount": 1, "lowConfidence": {}}
CLEAN: Mapping[str, object] = {"hasCritical": False, "criticalCount": 0, "lowConfidence": {}}


def _stored(family: ModelFamily) -> dict[str, object]:
    """Ref dạng storage (không cổ điển) của một họ, dạng JSONB như `pin_models` ghi."""
    version_id = new_id("mdl", SystemClock())
    return ModelRef(
        version_id=version_id,
        family=family,
        weights_key=f"{model_prefix(version_id)}model.onnx",
        pinned_name=None,
        checksum_sha256="a" * 64,
    ).model_dump(mode="json")


def _run(*, summary: Mapping[str, object] | None = CLEAN, classic: tuple[ModelFamily, ...] = ()) -> RunFacts:
    """Dữ kiện một lượt: họ trong `classic` ghim cổ điển, họ còn lại ghim bản storage."""
    pinned: dict[str, object] = {
        family: classic_ref(family).model_dump(mode="json") if family in classic else _stored(family)
        for family in MODEL_FAMILIES
    }
    return RunFacts(pinned=pinned, quality_summary=summary)


@pytest.mark.parametrize(
    ("run", "scale_source", "layer", "state", "reasons"),
    [
        pytest.param(None, "human", UNREVIEWED, "notEvaluated", (), id="no-run"),
        pytest.param(None, "pipeline", UNREVIEWED, "notEvaluated", ("scaleUnresolved",), id="no-run-scale"),
        pytest.param(_run(), "human", UNREVIEWED, "ready", (), id="ready"),
        pytest.param(_run(), "pipeline", REVIEWED, "needsReview", ("scaleUnresolved",), id="scale-pipeline"),
        pytest.param(
            _run(), "project_default", REVIEWED, "needsReview", ("scaleUnresolved",), id="scale-project-default"
        ),
        pytest.param(_run(), "none", UNREVIEWED, "ready", (), id="scale-none"),
        pytest.param(_run(summary=CRITICAL), "human", UNREVIEWED, "needsReview", ("criticalIssues",), id="critical"),
        pytest.param(_run(summary=None), "human", UNREVIEWED, "ready", (), id="summary-null"),
        pytest.param(
            _run(classic=("wallSegmentation",)), "human", UNREVIEWED, "needsReview", ("fallbackWallModel",), id="wall"
        ),
        pytest.param(
            _run(classic=("openingAndFurnitureDetection",)),
            "human",
            UNREVIEWED,
            "needsReview",
            ("fallbackObjectModel",),
            id="object",
        ),
        pytest.param(
            _run(classic=("dimensionReading",)), "human", UNREVIEWED, "needsReview", ("fallbackTextModel",), id="text"
        ),
        pytest.param(
            _run(summary=CRITICAL, classic=MODEL_FAMILIES),
            "pipeline",
            UNREVIEWED,
            "needsReview",
            ("scaleUnresolved", "criticalIssues", "fallbackWallModel", "fallbackObjectModel", "fallbackTextModel"),
            id="all-in-order",
        ),
        pytest.param(
            _run(summary=CRITICAL, classic=MODEL_FAMILIES), "human", REVIEWED, "ready", (), id="reviewed-clears-run"
        ),
        pytest.param(
            _run(summary=CRITICAL, classic=MODEL_FAMILIES),
            "pipeline",
            REVIEWED,
            "needsReview",
            ("scaleUnresolved", "criticalIssues", "fallbackWallModel", "fallbackObjectModel", "fallbackTextModel"),
            id="reviewed-but-scale-unresolved-keeps-all",
        ),
        pytest.param(RunFacts(pinned={}, quality_summary=None), "human", UNREVIEWED, "ready", (), id="no-pins-row"),
    ],
)
def test_readiness_of_table(
    run: RunFacts | None, scale_source: ScaleSource, layer: SpatialLayer, state: str, reasons: tuple[str, ...]
) -> None:
    """Mỗi lý do bật/tắt đúng luật; thứ tự lý do cố định; `level_reviewed` chỉ tắt lý do cấp lượt."""
    out = readiness_of(run=run, scale_source=scale_source, layer=layer)
    assert (out.state, out.reasons) == (state, reasons)


def test_readiness_of_human_scale_demoted_on_other_page() -> None:
    """Tỉ lệ `human` gắn trang P1, trang hiện tại P2 → hạ về `pipeline` → lại `scaleUnresolved`."""
    doc = replace(empty_document(1), layer=REVIEWED, scale_source="human", scale_page_key="P1")
    same = readiness_of(run=_run(), scale_source=effective_scale_source(doc, "P1"), layer=doc.layer)
    other = readiness_of(run=_run(), scale_source=effective_scale_source(doc, "P2"), layer=doc.layer)
    assert (same.state, same.reasons) == ("ready", ())
    assert (other.state, other.reasons) == ("needsReview", ("scaleUnresolved",))
