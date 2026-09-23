"""Nhà cung cấp luồng **giả** của test B4-01 (prompt [8]: "bản giả khai ngay trong `tests/`").

Không phải file test (pytest bỏ qua, `coverage` bỏ qua theo `omit = */tests/*`): nó chỉ
đóng vai B2-04 và B4-02 để trung tâm SSE có gì mà kiểm. Cả hai cổng đều **tiêm được lúc
chạy** (`allowed`, `payload`) vì S07 cần đổi câu trả lời của `authorize` giữa chừng, còn
S03/S08 cần một ảnh chụp hỏng schema.

Không ai trong đây nhập `apps.api.drawings` hay `apps.api.notifications` — hai module đó
chưa tồn tại và B4-01 không được tạo chúng ([12]).
"""

from collections.abc import Callable, Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.auth import Principal
from apps.api.streams.providers import StreamProvider
from apps.api.streams.registry import NOTIFICATIONS, UPLOAD_PROGRESS
from packages.core.error_codes import NOT_FOUND
from packages.core.errors import AppError
from packages.testing.fixtures.streams import sample_progress

UPLOAD_ID_KEY: Final = "upload_id"
"""Khoá `params` mà router đặt cho id lượt tải (hợp đồng A → B2-04)."""


class FakeProgress(BaseModel):
    """Mẫu `Progress` tối thiểu, `extra="forbid"` để sự kiện lạ bị loại như bản thật."""

    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    id: str
    progress_percent: int
    status: str
    step: str


class FakeNotification(BaseModel):
    """Mẫu `Notification` tối thiểu: chỉ đòi ba khoá FE luôn có, cho phép khoá thêm."""

    id: str
    kind: str
    message: str


class FakePolicy:
    """`StreamAccessPolicy` bật/tắt được: `allowed=False` → 404 như người ngoài dự án (S06, S07)."""

    def __init__(self, *, allowed: bool = True, error: AppError | None = None) -> None:
        """Mặc định cho qua rồi ném 404; `error` đổi sang lỗi khác (503 dựng nhánh hạ tầng)."""
        self.allowed = allowed
        self.error = error if error is not None else NOT_FOUND.error(resource="upload")
        self.calls = 0

    async def authorize(
        self,
        principal: Principal,
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Đếm lượt gọi (để test thấy recheck có chạy) rồi cho qua hay ném `self.error`."""
        self.calls += 1
        if not self.allowed:
            raise self.error


class FakeSnapshot:
    """`SnapshotProvider` trả dữ liệu do test quyết định — kể cả dữ liệu hỏng schema."""

    def __init__(self, payload: Callable[[str], Mapping[str, object]] | None = None) -> None:
        """Mặc định là `sample_progress(upload_id)`; test truyền hàm khác để dựng ảnh chụp hỏng."""
        self._payload = payload if payload is not None else sample_progress

    async def snapshot(
        self,
        principal: Principal,
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> Mapping[str, object]:
        """Ảnh chụp của lượt tải trong `params`."""
        return self._payload(params[UPLOAD_ID_KEY])


def progress_provider(policy: FakePolicy | None = None, snapshot: FakeSnapshot | None = None) -> StreamProvider:
    """Nhà cung cấp `upload_progress` giả, mặc định cho qua và trả ảnh chụp hợp lệ."""
    return StreamProvider(
        kind=UPLOAD_PROGRESS,
        event_model=FakeProgress,
        policy=policy if policy is not None else FakePolicy(),
        snapshot=snapshot if snapshot is not None else FakeSnapshot(),
    )


def notifications_provider(policy: FakePolicy | None = None) -> StreamProvider:
    """Nhà cung cấp `notifications` giả: có mẫu sự kiện, **không** ảnh chụp (K32)."""
    return StreamProvider(kind=NOTIFICATIONS, event_model=FakeNotification, policy=policy)
