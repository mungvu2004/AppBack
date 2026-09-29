"""Khoá object của bước dựng lớp không gian (B5-05 [2]).

`run_prefix` tới từ `BuildStepPayload` (đã kiểm dạng `projects/…/runs/{run_id}/`), nên hai
hàm ở đây chỉ nối chuỗi — không tự dựng lại tiền tố như `packages.storage.keys.run_artifact`
vì payload chưa có đủ id dự án/tầng/lượt tải để gọi nó (B5-05 [1], chưa có bảng lượt chạy).
"""

from typing import Final

from packages.ml_contracts.artifacts import STEP_ARTIFACTS
from packages.ml_contracts.families import ModelFamily

_LAYER_NAME: Final = "spatialDataBuild/layer.json"


def _first_json_name(step: ModelFamily) -> str:
    """Tên `.json` đầu tiên của `STEP_ARTIFACTS[step]` (một số bước còn ghi thêm `.png`)."""
    return next(name for name in STEP_ARTIFACTS[step] if name.endswith(".json"))


def input_key(run_prefix: str, step: ModelFamily) -> str:
    """Khoá artifact JSON đầu vào của bước `step`, khớp `keys.run_artifact` (B5-05 [2])."""
    return f"{run_prefix}{step}/{_first_json_name(step)}"


def layer_key(run_prefix: str) -> str:
    """Khoá `layer.json` mà `build_pipeline_layer` ghi ra (B5-05 [2])."""
    return f"{run_prefix}{_LAYER_NAME}"
