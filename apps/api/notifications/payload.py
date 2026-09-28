"""Dạng dây của một thông báo, một nguồn cho REST (#19, #22) và SSE (B4-02 [6]).

Trả `dict` khoá dây chứ không pydantic (module worker nhập được); khoá rỗng thì **vắng** (W2, K01/K02):
`floorId`, `excerpt`; không bao giờ có `userId`, `dedupeKey`, `streamId`.
"""

from packages.core.instants import to_wire
from packages.db.models.notifications import NotificationRow


def notification_wire(row: NotificationRow) -> dict[str, object]:
    """Đúng các khoá của `NotificationSchema` (FE); `createdAt` qua `to_wire`."""
    wire: dict[str, object] = {
        "id": row.id,
        "kind": row.kind,
        "place": row.place,
        "projectId": row.project_id,
        "projectName": row.project_name,
        "objectLabel": row.object_label,
        "message": row.message,
        "isRead": row.is_read,
        "createdAt": to_wire(row.created_at),
    }
    if row.floor_level_id is not None:
        wire["floorId"] = row.floor_level_id
    if row.excerpt is not None:
        wire["excerpt"] = row.excerpt
    return wire
