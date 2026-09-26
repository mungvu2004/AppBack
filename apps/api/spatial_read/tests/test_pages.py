"""Khai cổng `drawing_pages` (`apps.api.spatial_read.pages`) — B3-02 [8] "drawing_pages".

Cổng thật do B2-04 cài (`apps/api/drawings/drawing_pages.py`), nên `discover` phải thấy
đúng **một** phần tử; phần còn lại kiểm bằng `extensions.override` trên một app test.
"""

from collections.abc import Mapping, Sequence
from typing import cast

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import extensions
from apps.api.projects.tests.sql_count import count_sql
from apps.api.spatial_read import pages


class FakePages:
    """Cổng trang giả: chỉ biết những tầng test đưa vào, đúng hợp đồng `Mapping[int, str]`."""

    def __init__(self, known: Mapping[int, str]) -> None:
        """Ghi nhớ bảng trang; tầng ngoài bảng vắng khoá như cổng thật."""
        self.known = dict(known)

    async def load(self, db: object, floor_pks: Sequence[int]) -> Mapping[int, str]:
        """Chỉ trả những tầng cổng biết — không bịa khoá cho tầng lạ."""
        return {pk: self.known[pk] for pk in floor_pks if pk in self.known}


def use_pages(app: FastAPI, *sources: object) -> None:
    """Cài (hay gỡ) cổng `drawing_pages` cho **một** app test; không tham số = gỡ hẳn."""
    extensions.override(app, pages.SUBMODULE, [("apps.api.spatial_read.tests.test_pages", tuple(sources))])


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
