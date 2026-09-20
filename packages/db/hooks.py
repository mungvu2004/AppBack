"""Callback sau commit (J09, BE-00 §7).

`on_after_commit(session, fn)` chạy `fn` **sau** khi giao dịch ngoài cùng commit
thành công, đúng một lần, theo thứ tự đăng ký. Rollback (kể cả rollback SAVEPOINT
mà callback đăng ký bên trong) bỏ callback đang chờ.

Nơi chạy:

- **Có vòng sự kiện** (API): lên lịch **một** việc chạy tuần tự các callback bằng
  `run_in_executor` trên executor riêng có trần `DB_AFTER_COMMIT_WORKERS`. Không
  dùng executor mặc định: băm mật khẩu và xử lý ảnh cũng nằm ở đó, còn `send_task`
  hay `XADD` là I/O chặn — broker treo thì cả API treo. `AppRoute` (B0-06) và lõi
  task gọi `await after_commit_idle(session)` để chờ chúng xong.
- **Tiến trình worker** (`DB_AFTER_COMMIT_INLINE=1`, `create_celery` của B0-05 đặt)
  hoặc **không có vòng sự kiện**: chạy tại chỗ, tuần tự, xong trước khi `commit` trả.
  Vòng `asyncio.Runner` của worker nghỉ ngay sau khi task trả, việc đã lên lịch chỉ
  chạy ở task kế tiếp.

Callback ném lỗi hoặc quá `CALLBACK_TIMEOUT_S` → log `after_commit_failed`, **không**
ném lại: thay đổi đã bền vững. Việc buộc phải tới nơi thì module chủ phải có lịch
quét bù (J07/J10), và nên gửi bằng `apply_async(retry=False)`.

`DB_DROP_AFTER_COMMIT=1` (fixture `drop_after_commit()` của test, J10) bỏ mọi callback
và log `after_commit_dropped`. Cả hai cờ đọc lại ở **mỗi** lần commit.
"""

import asyncio
import inspect
import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field
from typing import Final

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

from packages.db.settings import get_database_settings

CALLBACK_TIMEOUT_S: Final = 2.0
INLINE_ENV: Final = "DB_AFTER_COMMIT_INLINE"
DROP_ENV: Final = "DB_DROP_AFTER_COMMIT"
_INFO_KEY: Final = "appback_after_commit"

_log = logging.getLogger(__name__)
_executor: ThreadPoolExecutor | None = None


@dataclass(slots=True)
class _Pending:
    entries: list[tuple[SessionTransaction | None, Callable[[], None]]] = field(default_factory=list)
    tasks: list[asyncio.Task[None]] = field(default_factory=list)


def _sync_session(session: Session | AsyncSession) -> Session:
    return session.sync_session if isinstance(session, AsyncSession) else session


def _state(session: Session) -> _Pending | None:
    state = session.info.get(_INFO_KEY)
    return state if isinstance(state, _Pending) else None


def _ensure_state(session: Session) -> _Pending:
    state = _state(session)
    if state is None:
        state = _Pending()
        session.info[_INFO_KEY] = state
    return state


def _executor_of() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=get_database_settings().db_after_commit_workers,
            thread_name_prefix="after-commit",
        )
    return _executor


def _name_of(fn: Callable[[], None]) -> str:
    return getattr(fn, "__qualname__", None) or repr(fn)


def on_after_commit(session: Session | AsyncSession, fn: Callable[[], None]) -> None:
    """Đăng ký `fn` chạy sau commit ngoài cùng. Chỉ nhận hàm đồng bộ."""
    if inspect.iscoroutinefunction(fn) or inspect.isawaitable(fn):
        raise TypeError("on_after_commit chỉ nhận hàm đồng bộ; bọc coroutine lại trước khi đăng ký")
    sync = _sync_session(session)
    state = _ensure_state(sync)
    state.entries.append((sync.get_nested_transaction() or sync.get_transaction(), fn))


async def after_commit_idle(session: Session | AsyncSession) -> None:
    """Chờ các callback đã lên lịch. Gọi được sau khi session đã đóng."""
    state = _state(_sync_session(session))
    if state is None:
        return
    pending = [task for task in state.tasks if not task.done()]
    state.tasks.clear()
    if pending:
        await asyncio.gather(*pending)


def _belongs_to(registered: SessionTransaction | None, ended: SessionTransaction) -> bool:
    if registered is None:  # đăng ký khi chưa có giao dịch → chỉ rollback ngoài cùng mới bỏ
        return ended.parent is None
    node: SessionTransaction | None = registered
    while node is not None:
        if node is ended:
            return True
        node = node.parent
    return False


def _log_failed(fn: Callable[[], None], exc: BaseException) -> None:
    _log.warning("after_commit_failed", extra={"callback": _name_of(fn), "error": repr(exc)})


def _run_inline(callbacks: list[Callable[[], None]]) -> None:
    executor = _executor_of()
    for fn in callbacks:
        future = executor.submit(copy_context().run, fn)
        try:
            future.result(timeout=CALLBACK_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 — callback của module khác; hỏng thì log, không ném lại
            _log_failed(fn, exc)


async def _run_scheduled(callbacks: list[Callable[[], None]]) -> None:
    loop = asyncio.get_running_loop()
    executor = _executor_of()
    for fn in callbacks:
        try:
            await asyncio.wait_for(loop.run_in_executor(executor, copy_context().run, fn), CALLBACK_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 — như trên; TimeoutError cũng vào đây
            _log_failed(fn, exc)


@event.listens_for(Session, "after_commit")
def _on_commit(session: Session) -> None:
    state = _state(session)
    if state is None or not state.entries:
        return
    callbacks = [fn for _, fn in state.entries]
    state.entries.clear()
    if os.environ.get(DROP_ENV) == "1":
        for fn in callbacks:
            _log.warning("after_commit_dropped", extra={"callback": _name_of(fn)})
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _run_inline(callbacks)
        return
    if os.environ.get(INLINE_ENV) == "1":
        _run_inline(callbacks)
        return
    state.tasks.append(loop.create_task(_run_scheduled(callbacks)))


@event.listens_for(Session, "after_soft_rollback")
def _on_rollback(session: Session, previous_transaction: SessionTransaction) -> None:
    state = _state(session)
    if state is None:
        return
    state.entries = [entry for entry in state.entries if not _belongs_to(entry[0], previous_transaction)]
