"""Cổng mời `ProjectInviteSink` (B2-02 [2] "Cổng mời"): nơi B4-02 cắm thông báo "được thêm vào dự án".

Module nhập được khi `fastapi`, `jwt`, `argon2` bị chặn (worker/B4-02 nhập nó), nên `extensions`
được nhập **muộn** trong thân `invite_sink` và kiểu `app` chỉ nằm dưới `TYPE_CHECKING`.
Sink chạy **trong** giao dịch của N3; việc gửi thật phải đăng ký sau commit (K17), sink tự lo.
"""

from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from packages.core.clock import Clock

SUBMODULE: Final = "invite_sinks"
ATTR: Final = "SINKS"


class ProjectInviteSink(Protocol):
    """Cổng "người này vừa được thêm vào dự án"; ném lỗi thì rollback cả lượt N3."""

    async def on_member_added(
        self,
        db: "AsyncSession",
        *,
        project_id: str,
        project_name: str,
        user_id: str,
        actor_id: str,
        clock: "Clock",
    ) -> None:
        """Gọi đúng một lần cho mỗi membership **mới**, trong giao dịch của người gọi."""
        ...


class _NoopSink:
    """Sink mặc định khi chưa module nào cắm (B4-02 chưa hợp nhất): không làm gì."""

    async def on_member_added(
        self,
        db: "AsyncSession",
        *,
        project_id: str,
        project_name: str,
        user_id: str,
        actor_id: str,
        clock: "Clock",
    ) -> None:
        """Không làm gì."""


def invite_sink(*, app: object | None = None) -> ProjectInviteSink:
    """Sink duy nhất của tiến trình: 0 → no-op, 1 → dùng, > 1 → `RuntimeError`.

    `SINKS` của mỗi module là một dãy; **tổng** số phần tử qua mọi module mới được đếm, vì hai
    sink cùng nhận một sự kiện sẽ gửi thông báo đôi. Không bắt `ImportError` (điểm mở rộng hỏng
    phải nổi lên lúc khởi động).
    """
    from apps.api.core import extensions  # muộn để module nhập được khi fastapi bị chặn

    sinks: list[ProjectInviteSink] = [
        sink for _name, group in extensions.resolve(app, SUBMODULE, ATTR) for sink in _as_sequence(group)
    ]
    if len(sinks) > 1:
        raise RuntimeError(f"chỉ được cắm một ProjectInviteSink, đang có {len(sinks)}")
    return sinks[0] if sinks else _NoopSink()


def _as_sequence(group: object) -> list[ProjectInviteSink]:
    """`SINKS` của một module → danh sách sink; không phải dãy → `RuntimeError` (khai sai)."""
    if not isinstance(group, (list, tuple)):
        raise RuntimeError("SINKS phải là list hoặc tuple")
    return list(group)
