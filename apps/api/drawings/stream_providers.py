"""Nhà cung cấp luồng SSE `upload_progress` — luồng S1 của hợp đồng (B2-04 [6]).

Trung tâm SSE (B4-01) dò file này qua `extensions.discover("stream_providers", "PROVIDERS")`;
không ai phải sửa `apps/api/streams` để cắm tiến độ vào (K27).

Một lớp đóng cả hai vai (`StreamAccessPolicy` và `SnapshotProvider`) vì cả hai trả lời
cùng một câu hỏi DB: "lượt tải này còn thuộc dự án mà người kia đang là thành viên
không". Mỗi lượt gọi mở **phiên ngắn** riêng từ `sessionmaker` của app rồi đóng ngay: một
luồng SSE sống hàng giờ và trung tâm gọi lại `authorize` mỗi `STREAM_RECHECK_S`, giữ
kết nối của request suốt thời gian đó là đúng cái K36 cấm.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.progress import progress_wire
from apps.api.drawings.schemas import ProgressOut
from apps.api.projects.memberships import is_member
from apps.api.streams.providers import StreamProvider
from packages.core.error_codes import NOT_FOUND
from packages.db.models.drawings import UploadRow
from packages.db.models.floors import FloorRow

if TYPE_CHECKING:
    from apps.api.core.auth import Principal

PROJECT_ID_KEY: Final = "project_id"
UPLOAD_ID_KEY: Final = "upload_id"


class UploadProgressStream:
    """Quyền mở và ảnh chụp đầu luồng của `upload_progress` (S06, S08)."""

    async def authorize(
        self,
        principal: "Principal",
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Thành viên của dự án chưa xoá **và** lượt tải thuộc dự án đó, tầng chưa xoá.

        Mọi trường hợp còn lại → 404 `resource:"upload"`, không 403: người ngoài không được
        phân biệt "không có quyền" với "không có thật" ([7], S06).
        """
        project_id, upload_id = params[PROJECT_ID_KEY], params[UPLOAD_ID_KEY]
        async with sessionmaker() as session:
            if not await is_member(session, project_id, principal.user_id):
                raise NOT_FOUND.error(resource="upload")
            stmt = (
                select(UploadRow.id)
                .join(FloorRow, FloorRow.pk == UploadRow.floor_pk)
                .where(
                    UploadRow.id == upload_id,
                    UploadRow.project_id == project_id,
                    FloorRow.deleted_at.is_(None),
                )
            )
            if (await session.execute(stmt)).first() is None:
                raise NOT_FOUND.error(resource="upload")

    async def snapshot(
        self,
        principal: "Principal",
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> Mapping[str, object]:
        """`Progress` hiện tại làm khung đầu; `authorize` đã chạy trước nên dòng chắc chắn có."""
        async with sessionmaker() as session:
            return await progress_wire(session, params[UPLOAD_ID_KEY])


_PROVIDER: Final = UploadProgressStream()

PROVIDERS: Final = (
    StreamProvider(kind="upload_progress", event_model=ProgressOut, policy=_PROVIDER, snapshot=_PROVIDER),
)
"""Sổ của module; `apps/api/streams/registry.py` đòi `upload_progress` có **cả hai** cổng."""
