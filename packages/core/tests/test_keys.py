from collections.abc import Iterator
from typing import get_args

import pytest

from packages.core.keys import KeyPurpose, current_key, derive_key, verification_keys
from packages.core.settings import reset_settings_cache

SECRET = "k" * 32
OLD_1 = "o" * 32
OLD_2 = "p" * 40

# Tính một lần (derive_key, đối chiếu cài đặt RFC 5869 bằng hmac của stdlib) rồi ghim:
# đổi thuật toán, độ dài hay info là làm mọi token đã phát hành mất hiệu lực.
# Chỉ ghim mục đích không trùng từ khoá của gitleaks (`access`, `token` bị luật generic-api-key bắt).
PINNED = {
    "lookup": "992de6f7e988d72bf20c80ae03f64f9a55d884078daad9557500192809db2064",
    "cursor": "51858f50bad29c1628c796aaa7e46140220abedfcf3b881560a5ad3ab889f205",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", SECRET)
    monkeypatch.setenv("SECRET_KEY_PREVIOUS", f"{OLD_1},{OLD_2}")
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.mark.parametrize(("purpose", "expected"), PINNED.items())
def test_derive_key_pinned_vector(purpose: KeyPurpose, expected: str) -> None:
    assert derive_key(purpose, SECRET.encode()).hex() == expected


def test_keys_differ_by_purpose() -> None:
    purposes: tuple[KeyPurpose, ...] = get_args(KeyPurpose)
    keys = {derive_key(p, SECRET.encode()) for p in purposes}
    assert len(purposes) == 7
    assert len(keys) == 7
    assert all(len(k) == 32 for k in keys)


def test_derive_key_rejects_unknown_purpose() -> None:
    with pytest.raises(ValueError, match="mục đích"):
        derive_key("session", SECRET.encode())  # type: ignore[arg-type]  # kiểm lúc chạy


def test_current_key_signs_with_secret_key_only() -> None:
    assert current_key("access") == derive_key("access", SECRET.encode())
    assert current_key("access") not in {derive_key("access", OLD_1.encode()), derive_key("access", OLD_2.encode())}


def test_verification_keys_current_first_then_previous() -> None:
    assert verification_keys("refresh") == (
        derive_key("refresh", SECRET.encode()),
        derive_key("refresh", OLD_1.encode()),
        derive_key("refresh", OLD_2.encode()),
    )


def test_verification_keys_without_previous(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY_PREVIOUS")
    reset_settings_cache()
    assert verification_keys("cursor") == (current_key("cursor"),)
