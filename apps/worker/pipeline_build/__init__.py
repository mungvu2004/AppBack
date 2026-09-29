"""Bước dựng lớp không gian của pipeline (`spatialDataBuild`, B5-05).

Biến ba artifact ML (px) thành `SpatialLayer` + `Dimension` (mm) mà FE giải mã được
(`build.build_layer`, hàm thuần) và task `pipeline.build.run` (`tasks`) đọc artifact, ghi
`layer.json`, báo kết quả cho B5-06c. `celery_main` nạp `tasks` qua `discover_submodules`,
nên gói không nhập lại `tasks` ở đây (sổ task chỉ nhận mỗi tên một lần).
"""

from apps.worker.pipeline_build.artifacts import input_key, layer_key
from apps.worker.pipeline_build.build import BuiltLayer, build_layer
from apps.worker.pipeline_build.ids import new_spatial_id

__all__ = ["BuiltLayer", "build_layer", "input_key", "layer_key", "new_spatial_id"]
