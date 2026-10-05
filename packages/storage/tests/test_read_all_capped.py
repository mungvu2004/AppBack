"""`read_all_capped` — một đường duy nhất gom `open_read` thành `bytes` có trần (NO-225, R-02)."""

import ast
from pathlib import Path

import pytest

from packages.core.errors import AppError
from packages.storage.local import LocalDiskStorage
from packages.storage.port import read_all_capped

KEY = "projects/prj_01ARZ3NDEKTSV4RRFFQ69G5FAV/blob.bin"
REPO = Path(__file__).resolve().parents[3]
CAP = 10


class _TooBigError(Exception):
    """Lỗi giả của người gọi: chứng minh mã lỗi do người gọi chọn."""


async def _put(storage: LocalDiskStorage, data: bytes) -> None:
    """Ghi `data` vào `KEY` bằng kho thật."""
    await storage.put(KEY, data, content_type="application/octet-stream", max_bytes=1024)


async def test_read_all_capped__under_and_at_the_cap_return_the_bytes(local_storage: LocalDiskStorage) -> None:
    """Đúng `max_bytes` byte vẫn qua; trần là "vượt", không phải "chạm"."""
    await _put(local_storage, b"x" * CAP)

    assert await read_all_capped(local_storage, KEY, max_bytes=CAP, too_large=_TooBigError) == b"x" * CAP


async def test_read_all_capped__over_the_cap_raises_the_callers_error(local_storage: LocalDiskStorage) -> None:
    """Vượt trần một byte → đúng ngoại lệ người gọi đưa, không trả bản cắt cụt."""
    await _put(local_storage, b"x" * (CAP + 1))

    with pytest.raises(_TooBigError):
        await read_all_capped(local_storage, KEY, max_bytes=CAP, too_large=_TooBigError)


async def test_read_all_capped__missing_key_without_on_missing_keeps_not_found(local_storage: LocalDiskStorage) -> None:
    """Không khai `on_missing`: 404 `NOT_FOUND` của kho lan nguyên (API trả 404)."""
    with pytest.raises(AppError, match="NOT_FOUND"):
        await read_all_capped(local_storage, KEY, max_bytes=CAP, too_large=_TooBigError)


async def test_read_all_capped__missing_key_with_on_missing_is_replaced(local_storage: LocalDiskStorage) -> None:
    """`on_missing` chỉ thay `NOT_FOUND`; mã lỗi kho khác (503) không bao giờ bị đổi."""
    with pytest.raises(KeyError):
        await read_all_capped(
            local_storage, KEY, max_bytes=CAP, too_large=_TooBigError, on_missing=lambda: KeyError("m")
        )


def _collects(stmt: ast.AST, name: str) -> bool:
    """`buf += name` hoặc `chunks.append(name)`: hai dạng gom khúc đọc được vào bộ nhớ."""
    if isinstance(stmt, ast.AugAssign):
        return isinstance(stmt.value, ast.Name) and stmt.value.id == name
    return (
        isinstance(stmt, ast.Call)
        and isinstance(stmt.func, ast.Attribute)
        and stmt.func.attr == "append"
        and any(isinstance(arg, ast.Name) and arg.id == name for arg in stmt.args)
    )


def _accumulates_open_read(tree: ast.AST) -> list[int]:
    """Dòng của mọi `async for x in <..>.open_read(..)` có thân `buf += x` hay `chunks.append(x)`."""
    hits: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFor) and isinstance(node.target, ast.Name)):
            continue
        call = node.iter
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "open_read"):
            continue
        if any(_collects(stmt, node.target.id) for stmt in ast.walk(node)):
            hits.append(node.lineno)
    return hits


def test_read_all_capped__no_other_module_reimplements_the_accumulate_loop() -> None:
    """Ngoài `packages/storage`, không `apps/**` nào tự viết lại vòng `buf += chunk` quanh `open_read`."""
    offenders = [
        f"{path.relative_to(REPO).as_posix()}:{line}"
        for path in sorted((REPO / "apps").rglob("*.py"))
        if "tests" not in path.parts
        for line in _accumulates_open_read(ast.parse(path.read_text(encoding="utf-8")))
    ]

    assert offenders == []
