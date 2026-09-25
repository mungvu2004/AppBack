"""Sổ nhà cung cấp luồng: dò, luật khai báo, bản mặc định (B4-01 [2], [8])."""

import re
from collections.abc import Iterator, Mapping
from types import SimpleNamespace
from typing import Final, cast

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core import extensions
from apps.api.core.auth import Principal
from apps.api.streams import registry as registry_module
from apps.api.streams.providers import StreamProvider
from apps.api.streams.registry import (
    NOTIFICATIONS,
    UPLOAD_PROGRESS,
    AnyEvent,
    DenyUploads,
    build_registry,
)
from packages.core.error_codes import NOT_FOUND
from packages.core.errors import AppError
from packages.core.settings import reset_settings_cache

CORE_KEY: Final = "khoa-bi-mat-du-32-byte-cho-test-ok"
PRINCIPAL: Final = Principal(user_id="usr_01ARZ3NDEKTSV4RRFFQ69G5FAV", session_id="sid", role="admin")
NO_MAKER: Final = cast("async_sessionmaker[AsyncSession]", None)
"""Nhà cung cấp mặc định từ chối trước khi chạm DB, nên `sessionmaker` không bao giờ được dùng."""


@pytest.fixture
def core_test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`APP_ENV=test` — điều kiện duy nhất để `extensions.override` dùng được (B0-06 [2])."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://testserver")
    monkeypatch.setenv("SECRET_KEY", CORE_KEY)
    reset_settings_cache()
    yield
    reset_settings_cache()


class FakeEvent(BaseModel):
    """Mẫu sự kiện của nhà cung cấp giả."""

    kind: str


class FakePolicy:
    """`StreamAccessPolicy` giả luôn cho qua."""

    async def authorize(
        self,
        principal: Principal,
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Không ném gì."""


class FakeSnapshot:
    """`SnapshotProvider` giả trả một ảnh chụp cố định."""

    async def snapshot(
        self,
        principal: Principal,
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> Mapping[str, object]:
        """Ảnh chụp hợp lệ theo `FakeEvent`."""
        return {"kind": "progress"}


def _app_with(*modules: tuple[str, object]) -> object:
    """Một "app" giả chỉ mang bảng `extensions.override` — `resolve` không cần gì hơn."""
    app = SimpleNamespace()
    extensions.override(app, "stream_providers", modules)
    return app


def test_real_repo_discovery_yields_both_kinds() -> None:
    """Dò repo thật không lỗi và sổ luôn đủ hai loại luồng, kể cả khi chưa ai cắm vào."""
    registry = build_registry(None)
    assert set(registry) == {UPLOAD_PROGRESS, NOTIFICATIONS}


def test_missing_progress_provider_defaults_to_closed(core_test_env: None) -> None:
    """Không module nào cắm `upload_progress` → sổ vẫn có ảnh chụp, nhưng chính sách từ chối hết.

    Dựng sổ từ một bảng `extensions.override` **rỗng** chứ không từ lượt dò repo thật: từ khi
    B2-04 cắm `apps.api.drawings.stream_providers` vào, lượt dò thật không còn dựng nổi cảnh
    "chưa ai cắm" (FIX-107). Cảnh ấy vẫn phải kiểm — nó là mặc định fail-closed của S06, và
    nó phải đúng cả trong một repo không có `apps/api/drawings`.
    """
    provider = build_registry(_app_with())[UPLOAD_PROGRESS]
    assert isinstance(provider.policy, DenyUploads)
    assert provider.snapshot is provider.policy


def test_missing_notifications_provider_defaults_to_open_schema() -> None:
    """Chưa có B4-02 → luồng thông báo nhận object JSON bất kỳ, không có ảnh chụp (K32)."""
    provider = build_registry(None)[NOTIFICATIONS]
    assert provider.event_model is AnyEvent
    assert provider.policy is None
    assert provider.snapshot is None


async def test_default_progress_provider_rejects_authorize() -> None:
    """Mặc định fail-closed: mở luồng tiến độ khi chưa có nhà cung cấp → 404 (S06)."""
    with pytest.raises(AppError) as caught:
        await DenyUploads().authorize(PRINCIPAL, {}, NO_MAKER)
    assert caught.value.code is NOT_FOUND


async def test_default_progress_provider_rejects_snapshot() -> None:
    """Ảnh chụp mặc định cũng 404 — nó chỉ tồn tại để sổ thoả luật "tiến độ luôn có ảnh chụp"."""
    with pytest.raises(AppError) as caught:
        await DenyUploads().snapshot(PRINCIPAL, {}, NO_MAKER)
    assert caught.value.code is NOT_FOUND


def test_override_replaces_the_default(core_test_env: None) -> None:
    """Nhà cung cấp khai qua `stream_providers` thắng bản mặc định."""
    mine = StreamProvider(kind=NOTIFICATIONS, event_model=FakeEvent, policy=FakePolicy())
    registry = build_registry(_app_with(("apps.api.fake.stream_providers", (mine,))))
    assert registry[NOTIFICATIONS] is mine
    assert isinstance(registry[UPLOAD_PROGRESS].policy, DenyUploads)


def test_duplicate_kind_is_rejected(core_test_env: None) -> None:
    """Hai module cùng khai một `kind` → `RuntimeError` lúc dò, không phải lúc request đầu."""
    first = StreamProvider(kind=NOTIFICATIONS, event_model=FakeEvent)
    second = StreamProvider(kind=NOTIFICATIONS, event_model=AnyEvent)
    app = _app_with(("apps.api.a.stream_providers", (first,)), ("apps.api.b.stream_providers", (second,)))
    with pytest.raises(RuntimeError, match="cùng kind"):
        build_registry(app)


def test_progress_provider_without_policy_is_rejected(core_test_env: None) -> None:
    """`upload_progress` bắt buộc có `StreamAccessPolicy` (SEC-02); thiếu → `RuntimeError`.

    Đối xứng với luật `snapshot`: quên chính sách nghĩa là mọi người đã đăng nhập đọc được
    tiến độ của mọi lượt tải, và lỗ đó chỉ lộ ra khi B2-04 hợp nhất nếu không chặn ở đây.
    """
    broken = StreamProvider(kind=UPLOAD_PROGRESS, event_model=FakeEvent, snapshot=FakeSnapshot())
    with pytest.raises(RuntimeError, match="policy"):
        build_registry(_app_with(("apps.api.a.stream_providers", (broken,))))


def test_notifications_provider_without_policy_is_accepted(core_test_env: None) -> None:
    """Luồng thông báo **được** phép `policy=None`: stream khoá cứng theo `principal.user_id`."""
    mine = StreamProvider(kind=NOTIFICATIONS, event_model=FakeEvent)
    registry = build_registry(_app_with(("apps.api.a.stream_providers", (mine,))))
    assert registry[NOTIFICATIONS].policy is None


def test_progress_provider_without_snapshot_is_rejected(core_test_env: None) -> None:
    """`upload_progress` bắt buộc có `SnapshotProvider` (S08); thiếu → `RuntimeError`."""
    broken = StreamProvider(kind=UPLOAD_PROGRESS, event_model=FakeEvent, policy=FakePolicy())
    with pytest.raises(RuntimeError, match="snapshot"):
        build_registry(_app_with(("apps.api.a.stream_providers", (broken,))))


def test_progress_provider_with_snapshot_is_accepted(core_test_env: None) -> None:
    """Khai đủ cả hai cổng thì được nhận, và bản mặc định biến mất khỏi sổ."""
    good = StreamProvider(kind=UPLOAD_PROGRESS, event_model=FakeEvent, policy=FakePolicy(), snapshot=FakeSnapshot())
    registry = build_registry(_app_with(("apps.api.a.stream_providers", (good,))))
    assert registry[UPLOAD_PROGRESS] is good


def test_default_providers_without_policy_is_rejected_by_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-158 Nit 2: `default_providers()` cũng đi qua `_check` — sổ mặc định hỏng không lọt qua lặng lẽ.

    Trên mã cũ, `build_registry` gộp thẳng `default_providers()` mà không kiểm, nên nếu ai
    sửa nó mà quên `policy` của `upload_progress`, sổ vẫn "đầy đủ" tới lúc request đầu mới lộ.
    """
    broken = {
        UPLOAD_PROGRESS: StreamProvider(kind=UPLOAD_PROGRESS, event_model=AnyEvent, snapshot=DenyUploads()),
        NOTIFICATIONS: StreamProvider(kind=NOTIFICATIONS, event_model=AnyEvent),
    }
    monkeypatch.setattr(registry_module, "default_providers", lambda: broken)
    with pytest.raises(RuntimeError, match="policy"):
        build_registry(None)


@pytest.mark.parametrize("value", ["khong-phai-tuple", (object(),), 42])
def test_bad_providers_attribute_is_rejected(core_test_env: None, value: object) -> None:
    """`PROVIDERS` không phải `tuple[StreamProvider, ...]` → `RuntimeError` nêu tên module."""
    with pytest.raises(RuntimeError, match=re.escape("apps.api.a.stream_providers")):
        build_registry(_app_with(("apps.api.a.stream_providers", value)))
