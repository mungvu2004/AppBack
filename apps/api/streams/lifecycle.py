"""Hẹn giờ xoá stream tiến độ sau trạng thái cuối (B4-01 [2], BE-00 §7 "Sự kiện").

Bên **phát** gọi hai hàm này (B2-04, B5-06a), không phải trung tâm SSE, nên module
không nhập `fastapi`/`starlette`: nó chạy được cả trong tiến trình worker.

Hai bản cho hai đường: bản async cho mã trong request/task, bản đồng bộ cho callback
`on_after_commit` chạy ngoài vòng sự kiện (K17). Cả hai idempotent — gọi lại chỉ dời
hạn, không tạo thêm gì.
"""

from typing import Final

from packages.messaging.streams import EventBus, SyncEventBus, upload_stream

UPLOAD_STREAM_TTL_S: Final = 86_400
"""24 giờ sau trạng thái cuối (BE-00 §7): đủ cho FE nối lại sau một đêm, không giữ mãi."""


async def finalize_upload_stream(bus: EventBus, upload_id: str) -> None:
    """`EXPIRE events:upload:{id}` — lượt tải đã vào trạng thái cuối, không còn sự kiện mới."""
    await bus.expire(upload_stream(upload_id), UPLOAD_STREAM_TTL_S)


def finalize_upload_stream_sync(bus: SyncEventBus, upload_id: str) -> None:
    """Bản đồng bộ của `finalize_upload_stream`, dùng trong callback sau commit."""
    bus.expire(upload_stream(upload_id), UPLOAD_STREAM_TTL_S)
