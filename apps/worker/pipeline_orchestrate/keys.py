"""Tiền tố artifact của một lượt chạy pipeline (B5-06a [2]).

`run_prefix` chỉ dựng phần chung của mọi bước (`keys.run_artifact` của B0-04 dựng khoá đầy
đủ một artifact); nguồn khoá thật nằm ở `packages.storage.keys`/`packages.core.object_keys`
(NO-081), hàm ở đây chỉ ghép lại theo đúng bố cục để `dispatch.queue_infer` dùng.
"""

from packages.storage.keys import upload_prefix


def run_prefix(*, project_id: str, level_id: str, upload_id: str, run_id: str) -> str:
    """Tiền tố mọi artifact của lượt `run_id`: `upload_prefix(...) + f"runs/{run_id}/"`."""
    return f"{upload_prefix(project_id, level_id, upload_id)}runs/{run_id}/"
