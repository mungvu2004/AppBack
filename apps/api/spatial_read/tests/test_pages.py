"""Khai cổng `drawing_pages` (`apps.api.spatial_read.pages`) — B3-02 [8] "drawing_pages".

Cổng thật do B2-04 cài (`apps/api/drawings/drawing_pages.py`), nên `discover` phải thấy
đúng **một** phần tử; phần còn lại kiểm bằng `extensions.override` trên một app test
(`FakePages`, `use_pages` ở `_read_helpers.py` — ba file test cùng dùng).
"""

from collections.abc import Sequence
from typing import cast

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import extensions
from apps.api.projects.tests.sql_count import count_sql
from apps.api.spatial_read import pages
from apps.api.spatial_read.tests._read_helpers import FakePages, use_pages


def test_gate_is_installed_exactly_once() -> None:
    """B2-04 là module duy nhất cài `PAGES`; hai bản cài sẽ làm `load_pages` ném."""
    found = [
        item
        for _, value in extensions.discover(pages.SUBMODULE, pages.ATTR)
        for item in cast("Sequence[object]", value)
    ]
    assert len(found) == 1


async def test_load_pages_returns_known_floors(db_session: AsyncSession, api_app: FastAPI) -> None:
    """Cổng biết tầng nào thì trả tầng ấy; tầng lạ vắng khoá chứ không mang chuỗi rỗng."""
    use_pages(api_app, FakePages({1: "P1"}))
    assert await pages.load_pages(db_session, [1, 2], app=api_app) == {1: "P1"}


async def test_load_pages_without_gate(db_session: AsyncSession, api_app: FastAPI) -> None:
    """Không ai cài cổng → `{}`, và không truy vấn nào."""
    use_pages(api_app)
    with count_sql() as counter:
        assert await pages.load_pages(db_session, [1], app=api_app) == {}
    assert counter.count == 0


async def test_load_pages_empty_batch_skips_gate(db_session: AsyncSession, api_app: FastAPI) -> None:
    """Lô rỗng không gọi cổng: không có gì để hỏi."""
    use_pages(api_app, FakePages({1: "P1"}))
    assert await pages.load_pages(db_session, [], app=api_app) == {}


async def test_load_pages_rejects_two_gates(db_session: AsyncSession, api_app: FastAPI) -> None:
    """Hai phần tử cùng cổng → `RuntimeError` (BE-00 §2.2: tối đa 1)."""
    use_pages(api_app, FakePages({}), FakePages({}))
    with pytest.raises(RuntimeError, match="tối đa 1"):
        await pages.load_pages(db_session, [1], app=api_app)
