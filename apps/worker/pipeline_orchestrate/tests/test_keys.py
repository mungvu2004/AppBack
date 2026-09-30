"""`keys.run_prefix` (B5-06a [8] mục "Khoá"): phần chung của mọi artifact một lượt chạy."""

from apps.worker.pipeline_orchestrate.keys import run_prefix
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.storage.keys import run_artifact


def test_run_prefix_matches_run_artifact_layout() -> None:
    """`run_prefix(...) + "spatialDataBuild/layer.json"` bằng đúng `keys.run_artifact` cùng tham số."""
    clock = SystemClock()
    kwargs = {
        "project_id": new_id("prj", clock),
        "level_id": "L-ABCDEFGHIJ",
        "upload_id": new_id("upl", clock),
        "run_id": new_id("run", clock),
    }
    prefix = run_prefix(**kwargs)
    expected = run_artifact(
        kwargs["project_id"],
        kwargs["level_id"],
        kwargs["upload_id"],
        kwargs["run_id"],
        "spatialDataBuild",
        "layer.json",
    )
    assert prefix + "spatialDataBuild/layer.json" == expected
