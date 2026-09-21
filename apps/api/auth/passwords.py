"""Băm và kiểm mật khẩu argon2id (BE-00 §5, K36).

- **NFC trước khi băm và kiểm** ở mọi đường (đăng nhập, CLI, N9, N10, N13): cùng một mật
  khẩu gõ trên macOS (NFD) và Windows (NFC) phải là một (C16).
- argon2 tốn CPU và RAM nên chạy trên **executor riêng** `PASSWORD_HASH_CONCURRENCY`
  luồng, không trên vòng sự kiện, không chung executor mặc định (callback sau commit và xử
  lý ảnh ở đó). Chỗ trong executor giữ bằng semaphore **theo vòng sự kiện** (BE-00 §7);
  chờ chỗ quá `HASH_WAIT_S` → 503 `DEPENDENCY_UNAVAILABLE` thay vì xếp hàng vô hạn.
- `verify_password(None, …)` vẫn chạy trọn một lượt kiểm trên **băm giả** rồi trả `False`:
  email lạ và người `pending` tốn đúng thời gian như sai mật khẩu (C27). Băm giả dựng lười
  ở lượt gọi đầu — nhập module không đọc cấu hình, không băm.
"""

import asyncio
import logging
import secrets
import weakref
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import replace
from functools import cache
from typing import Final

from argon2 import PasswordHasher, profiles
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from apps.api.auth.settings import Argon2Profile, get_auth_settings
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.text import nfc

_log: Final = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH: Final = 8
"""Như `MIN_PASSWORD_LENGTH` của FE (`src/api/schemas/index.ts:56`)."""

HASH_WAIT_S: Final = 2.0
HASH_RETRY_AFTER_S: Final = 1

PARAMETERS: Final = {
    "rfc9106_low_memory": profiles.RFC_9106_LOW_MEMORY,
    # 1 MiB, 1 vòng: ~0,5 ms một lượt, để bộ test chạy hàng trăm lượt đăng nhập (chỉ APP_ENV=test).
    "test": replace(profiles.RFC_9106_LOW_MEMORY, memory_cost=1024, time_cost=1),
}

_executor: ThreadPoolExecutor | None = None
_slots: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = weakref.WeakKeyDictionary()


@cache
def _hasher(profile: Argon2Profile) -> PasswordHasher:
    """Bộ băm của một hồ sơ; `PasswordHasher` không giữ trạng thái nên dùng chung được giữa các luồng."""
    return PasswordHasher.from_parameters(PARAMETERS[profile])


@cache
def _dummy_hash(profile: Argon2Profile) -> str:
    """Băm của một mật khẩu ngẫu nhiên không ai biết — đích kiểm của email lạ và người `pending`."""
    return _hasher(profile).hash(secrets.token_urlsafe(32))


def _pool() -> ThreadPoolExecutor:
    """Executor riêng của băm, dựng lười ở lượt dùng đầu với số luồng của cấu hình."""
    global _executor  # một executor mỗi tiến trình, như executor sau commit của B0-03
    if _executor is None:
        workers = get_auth_settings().password_hash_concurrency
        _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="password-hash")
    return _executor


def _semaphore() -> asyncio.Semaphore:
    """Semaphore của vòng đang chạy; ở mức module nó gắn vào vòng đầu tiên phải chờ (BE-00 §7)."""
    loop = asyncio.get_running_loop()
    slots = _slots.get(loop)
    if slots is None:
        slots = asyncio.Semaphore(get_auth_settings().password_hash_concurrency)
        _slots[loop] = slots
    return slots


@asynccontextmanager
async def hash_slot() -> AsyncIterator[None]:
    """Giữ một chỗ của executor băm; chờ quá `HASH_WAIT_S` → 503 (không `wait_for` quanh executor)."""
    slots = _semaphore()
    try:
        await asyncio.wait_for(slots.acquire(), HASH_WAIT_S)
    except TimeoutError as exc:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=HASH_RETRY_AFTER_S) from exc
    try:
        yield
    finally:
        slots.release()


async def _offload[ResultT](fn: Callable[..., ResultT], *args: object) -> ResultT:
    """Chạy `fn` trên executor băm sau khi đã giữ chỗ."""
    async with hash_slot():
        return await asyncio.get_running_loop().run_in_executor(_pool(), fn, *args)


def _matches(profile: Argon2Profile, password_hash: str, password: str) -> bool:
    """Kiểm một mật khẩu (đã NFC) với một băm; băm hỏng coi như sai, có log để còn sửa dữ liệu."""
    try:
        return _hasher(profile).verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except (InvalidHashError, VerificationError):
        _log.warning("password_hash_unusable")
        return False


def _verify_sync(profile: Argon2Profile, password_hash: str | None, password: str) -> bool:
    """Thân chạy trong executor: không có băm thì kiểm trên băm giả rồi luôn trả `False`."""
    if password_hash is None:
        _matches(profile, _dummy_hash(profile), password)
        return False
    return _matches(profile, password_hash, password)


async def hash_password(password: str) -> str:
    """Băm argon2id của `nfc(password)` theo `ARGON2_PROFILE`."""
    profile = get_auth_settings().argon2_profile
    return await _offload(_hasher(profile).hash, nfc(password))


async def verify_password(password_hash: str | None, password: str) -> bool:
    """`True` khi `nfc(password)` khớp băm; `None` → một lượt kiểm trên băm giả, trả `False`."""
    profile = get_auth_settings().argon2_profile
    return await _offload(_verify_sync, profile, password_hash, nfc(password))


def needs_rehash(password_hash: str) -> bool:
    """Băm tạo bằng tham số khác hồ sơ hiện hành → nên băm lại khi đăng nhập đúng."""
    return _hasher(get_auth_settings().argon2_profile).check_needs_rehash(password_hash)
