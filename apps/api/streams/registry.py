"""Sổ nhà cung cấp luồng: dò `apps/api/*/stream_providers.py` (B4-01 [2]).

Kiểm **lúc `lifespan` của router**, không lúc request đầu: hai module cùng khai một
`kind`, hay luồng tiến độ thiếu `SnapshotProvider`, là sai cấu hình — API thà không
khởi động còn hơn phục vụ nửa vời rồi 500 cho người dùng đầu tiên (R-17).

Khi nhà cung cấp thật chưa hợp nhất, sổ vẫn đầy đủ bằng bản mặc định **fail-closed**
cho tiến độ (mọi yêu cầu 404) và bản thả lỏng cho thông báo (stream của chính mình,
sự kiện là object JSON bất kỳ) — B4-02 chỉ siết mẫu sự kiện lại chứ không mở thêm quyền.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core import extensions
from apps.api.streams.providers import StreamKind, StreamProvider
from packages.core.error_codes import NOT_FOUND

if TYPE_CHECKING:
    from apps.api.core.auth import Principal

PROVIDERS_SUBMODULE: Final = "stream_providers"
PROVIDERS_ATTR: Final = "PROVIDERS"

UPLOAD_PROGRESS: Final[StreamKind] = "upload_progress"
NOTIFICATIONS: Final[StreamKind] = "notifications"


class AnyEvent(BaseModel):
    """Mẫu mặc định của luồng thông báo: object JSON bất kỳ (B4-02 thay bằng `Notification`)."""

    model_config = ConfigDict(extra="allow")


class DenyUploads:
    """Nhà cung cấp tiến độ mặc định khi B2-04 chưa hợp nhất: mọi yêu cầu → 404 (S06).

    Cùng một đối tượng đóng cả hai vai `StreamAccessPolicy` và `SnapshotProvider`:
    `authorize` đã chặn nên `snapshot` không bao giờ chạy trong một request thật, nhưng
    nó phải tồn tại để sổ thoả luật "luồng tiến độ luôn có ảnh chụp".
    """

    async def authorize(
        self,
        principal: "Principal",
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Luôn 404 `resource="upload"`."""
        raise NOT_FOUND.error(resource="upload")

    async def snapshot(
        self,
        principal: "Principal",
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> Mapping[str, object]:
        """Luôn 404; chỉ có mặt để `StreamProvider.snapshot` không rỗng."""
        raise NOT_FOUND.error(resource="upload")


def default_providers() -> dict[StreamKind, StreamProvider]:
    """Bản mặc định của cả hai loại luồng, dùng cho `kind` chưa ai cắm vào."""
    deny = DenyUploads()
    return {
        UPLOAD_PROGRESS: StreamProvider(kind=UPLOAD_PROGRESS, event_model=AnyEvent, policy=deny, snapshot=deny),
        NOTIFICATIONS: StreamProvider(kind=NOTIFICATIONS, event_model=AnyEvent),
    }


def _declared(name: str, value: object) -> tuple[StreamProvider, ...]:
    """`PROVIDERS` của một module, đã kiểm kiểu; sai kiểu → `RuntimeError` nêu tên module."""
    if not isinstance(value, tuple | list) or not all(isinstance(item, StreamProvider) for item in value):
        raise RuntimeError(f"{name}.{PROVIDERS_ATTR} phải là tuple[StreamProvider, ...]")
    return tuple(value)


def _check(name: str, provider: StreamProvider, found: Mapping[StreamKind, StreamProvider]) -> None:
    """Luật của một khai báo: `kind` chưa ai lấy, và tiến độ bắt buộc có **cả** quyền lẫn ảnh chụp.

    `policy` bắt buộc đúng như `snapshot` (SEC-02): luồng tiến độ mang id của lượt tải trên
    đường, nên nếu nhà cung cấp quên khai chính sách thì mọi người đã đăng nhập đọc được tiến
    độ của mọi lượt tải (IDOR) và không cổng nào kêu. Luồng thông báo **được** phép `policy=None`
    vì stream của nó khoá cứng theo `principal.user_id`, không có tham số chọn người khác.
    """
    if provider.kind in found:
        raise RuntimeError(f"{name}: hai nhà cung cấp cùng kind {provider.kind!r}")
    if provider.kind != UPLOAD_PROGRESS:
        return
    if provider.policy is None:
        raise RuntimeError(f"{name}: nhà cung cấp {UPLOAD_PROGRESS!r} bắt buộc có policy (S06, SEC-02)")
    if provider.snapshot is None:
        raise RuntimeError(f"{name}: nhà cung cấp {UPLOAD_PROGRESS!r} bắt buộc có snapshot (S08)")


def build_registry(app: object | None) -> Mapping[StreamKind, StreamProvider]:
    """Sổ đầy đủ cho một app: khai báo đã dò, cộng bản mặc định cho `kind` còn trống.

    `app` cho phép test thay sổ bằng `extensions.override` (chỉ `APP_ENV=test`), nên
    chính sách quyền thật không thay được ở môi trường thật.

    Bản mặc định (`default_providers()`) cũng đi qua `_check` (NO-158 Nit 2): luật "luồng
    tiến độ bắt buộc có `policy` và `snapshot`" trước đây chỉ áp cho khai báo dò được, nên
    nếu ai sửa `default_providers()` mà quên một trong hai, sổ vẫn "đầy đủ" lặng lẽ thay vì
    hỏng ngay lúc `lifespan` (R-17).
    """
    found: dict[StreamKind, StreamProvider] = {}
    for name, value in extensions.resolve(app, PROVIDERS_SUBMODULE, PROVIDERS_ATTR):
        for provider in _declared(name, value):
            _check(name, provider, found)
            found[provider.kind] = provider
    defaults = default_providers()
    for provider in defaults.values():
        _check("default_providers", provider, {})
    return {**defaults, **found}
