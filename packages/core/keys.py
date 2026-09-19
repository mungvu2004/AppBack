"""Khoá con HKDF-SHA256 từ `SECRET_KEY` (BE-00 §5). Nơi duy nhất đọc `SECRET_KEY`.

Ký bằng `current_key`; kiểm bằng `verification_keys` (khoá hiện tại trước, khoá cũ
sau). Khoá cũ không bao giờ dùng để ký. Không log khoá (K11).
"""

from typing import Final, Literal, get_args

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from packages.core.settings import get_core_settings

KeyPurpose = Literal["access", "stream", "refresh", "file", "token", "cursor", "lookup"]

_PURPOSES: Final = frozenset(get_args(KeyPurpose))


def derive_key(purpose: KeyPurpose, secret: bytes) -> bytes:
    if purpose not in _PURPOSES:
        raise ValueError(f"mục đích khoá lạ: {purpose!r}")
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"appback/" + purpose.encode())
    return hkdf.derive(secret)


def current_key(purpose: KeyPurpose) -> bytes:
    secret = get_core_settings().secret_key.get_secret_value()
    return derive_key(purpose, secret.encode("utf-8"))


def verification_keys(purpose: KeyPurpose) -> tuple[bytes, ...]:
    previous = get_core_settings().secret_key_previous
    return (
        current_key(purpose),
        *(derive_key(purpose, item.get_secret_value().encode("utf-8")) for item in previous),
    )
