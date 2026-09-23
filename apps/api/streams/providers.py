"""Cổng nhà cung cấp luồng SSE (B4-01 [2], BE-00 §7 "SSE").

B2-04 (tiến độ) và B4-02 (thông báo) cắm vào trung tâm SSE bằng một file
`stream_providers.py` trong module của **họ**, export `PROVIDERS: tuple[StreamProvider, ...]`;
không ai phải sửa file của B4-01 (K27). `apps/api/streams/registry.py` dò chúng.

Hai cổng tách nhau vì chúng trả lời hai câu khác nhau: `StreamAccessPolicy` nói
"người này có được mở luồng không" (không được → `AppError` 404, **không** 403, S06),
`SnapshotProvider` nói "trạng thái hiện tại là gì" khi luồng mở mới (S08).

`params` là tham số đường của route, khoá đúng tên tham số Python (`project_id`,
`upload_id`); luồng thông báo không có tham số nào. `sessionmaker` là của app: nhà
cung cấp mở **phiên ngắn** rồi đóng trước khi trả, không giữ session của request (K36).

Module này không nhập `apps.api.core.auth` lúc chạy: `Principal` chỉ cần cho kiểu,
và một cổng thuần khai báo thì không nên kéo theo cả cây xác thực.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from apps.api.core.auth import Principal

StreamKind = Literal["upload_progress", "notifications"]
"""Hai loại luồng của hợp đồng S1, S2 — mỗi loại đúng một nhà cung cấp."""


class StreamAccessPolicy(Protocol):
    """Quyền mở và **giữ** một luồng; trung tâm SSE gọi lại mỗi `STREAM_RECHECK_S` (S07)."""

    async def authorize(
        self,
        principal: "Principal",
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Không được phép → ném `AppError` 404 (người ngoài không biết tài nguyên có thật hay không)."""


class SnapshotProvider(Protocol):
    """Trạng thái hiện tại của luồng, gửi làm khung đầu khi mở mới hoặc đã bị cắt (S08)."""

    async def snapshot(
        self,
        principal: "Principal",
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> Mapping[str, object]:
        """Dữ liệu dây của ảnh chụp; phải giải được bằng `event_model` của chính nhà cung cấp."""


@dataclass(frozen=True, slots=True)
class StreamProvider:
    """Khai báo của một loại luồng: mẫu sự kiện, quyền, ảnh chụp.

    `policy = None` nghĩa là không có gì để kiểm ngoài chính phiên (luồng thông báo
    chỉ đọc stream của `principal.user_id`, không có tham số chọn người khác).
    `snapshot = None` chỉ hợp lệ cho luồng **không** ảnh chụp (K32).
    """

    kind: StreamKind
    event_model: type[BaseModel]
    policy: StreamAccessPolicy | None = None
    snapshot: SnapshotProvider | None = None
