"""`artifacts.input_key`, `artifacts.layer_key` khớp `keys.run_artifact` (B5-05 [2])."""

from apps.worker.pipeline_build.artifacts import input_key, layer_key
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.storage.keys import run_artifact

_PROJECT, _UPLOAD, _RUN = new_id("prj", SystemClock()), new_id("upl", SystemClock()), new_id("run", SystemClock())
_FLOOR = "L-ABCDEFGHIJ"
_RUN_PREFIX = f"projects/{_PROJECT}/floors/{_FLOOR}/uploads/{_UPLOAD}/runs/{_RUN}/"


def test_input_key_matches_run_artifact_for_walls() -> None:
    """`input_key` của `wallSegmentation` = tên `.json` đầu tiên (`walls.json`), khớp `run_artifact`."""
    expected = run_artifact(_PROJECT, _FLOOR, _UPLOAD, _RUN, "wallSegmentation", "walls.json")
    assert input_key(_RUN_PREFIX, "wallSegmentation") == expected


def test_input_key_matches_run_artifact_for_objects() -> None:
    """`input_key` của `openingAndFurnitureDetection` = `objects.json`."""
    expected = run_artifact(_PROJECT, _FLOOR, _UPLOAD, _RUN, "openingAndFurnitureDetection", "objects.json")
    assert input_key(_RUN_PREFIX, "openingAndFurnitureDetection") == expected


def test_input_key_matches_run_artifact_for_text() -> None:
    """`input_key` của `dimensionReading` = `text.json`."""
    expected = run_artifact(_PROJECT, _FLOOR, _UPLOAD, _RUN, "dimensionReading", "text.json")
    assert input_key(_RUN_PREFIX, "dimensionReading") == expected


def test_layer_key_matches_run_artifact() -> None:
    """`layer_key` = artifact `layer.json` của bước `spatialDataBuild`, khớp `run_artifact`."""
    expected = run_artifact(_PROJECT, _FLOOR, _UPLOAD, _RUN, "spatialDataBuild", "layer.json")
    assert layer_key(_RUN_PREFIX) == expected
