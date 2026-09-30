"""Hằng nghiệp vụ của bước ghi kết quả pipeline (B5-06b [2]); mỗi hằng ghi nguồn."""

from typing import Final

SYSTEM_PIPELINE_NAME: Final = "hệ thống AI"
"""Tên người thực hiện hiển thị cho mọi ghi của pipeline (HOP-DONG-MOI §5); id là `SYSTEM_PIPELINE`."""

STEP: Final = "spatialDataBuild"
"""Bước của lượt chạy mà task này đẩy xong hoặc đánh hỏng (B5-06b [6])."""

LAYER_ARTIFACT: Final = "layer.json"
"""Tên object B5-05 ghi dưới `run_artifact(…, STEP, LAYER_ARTIFACT)` (B5-06b [5])."""

QUALITY_TASK: Final = "pipeline.quality.run"
"""Task bước kế tiếp (B5-07), gửi sau commit với `RunStepPayload(run_id)` (B5-06b [6] bước 10)."""
