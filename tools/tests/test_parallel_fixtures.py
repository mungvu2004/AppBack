"""FIX-112 — phần fixture phải chịu được bước 5 chạy `pytest -n` (nhiều tiến trình).

Hai điểm dùng chung giữa các tiến trình xdist:

- `packages/testing/fixtures/db.py`: database mẫu là fixture **phiên**, mỗi tiến trình con dựng
  một lần → tên phải mang hậu tố tiến trình, không thì tiến trình sau `DROP … WITH (FORCE)` cái
  mà tiến trình trước đang nhân bản.
- `packages/testing/fixtures/api.py`: `CASE_TRACE_FILE` là **một** file cho mọi tiến trình
  (`case_gate` bước 5b/6 đọc nó). Mỗi vết là một `open("a")` + một `write()` của một dòng ngắn —
  ngắn hơn bộ đệm 8 KiB của `open()` nên ra đúng **một** `write(2)`, và Linux giữ khoá inode quanh
  một `write(2)` O_APPEND trên file thường nên hai dòng không xen vào nhau (PIPE_BUF 4 KiB là luật
  của pipe, không phải của file thường — NO-277). Dòng dài hơn bộ đệm có thể bị tách thành nhiều
  `write(2)` và xen được; vết case chỉ có tên test, op, status, code nên không chạm tới. Test dưới
  đo bằng tiến trình thật.
"""

from __future__ import annotations

import json
import multiprocessing
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx
import pytest

from packages.testing.fixtures import api as api_fixtures
from packages.testing.fixtures.db import TEMPLATE_DB, template_db_name
from packages.testing.fixtures.worker_id import XDIST_WORKER_ENV

# --- tên database mẫu theo tiến trình xdist -----------------------------------------


@pytest.mark.parametrize(
    ("worker", "expected"),
    [
        ("gw0", f"{TEMPLATE_DB}_gw0"),
        ("gw11", f"{TEMPLATE_DB}_gw11"),
        ("  gw2  ", f"{TEMPLATE_DB}_gw2"),
        ("", TEMPLATE_DB),
        ("   ", TEMPLATE_DB),
    ],
)
def test_tên_database_mẫu_theo_tiến_trình(monkeypatch: pytest.MonkeyPatch, worker: str, expected: str) -> None:
    """Tên database mẫu mang hậu tố mã tiến trình xdist."""
    monkeypatch.setenv(XDIST_WORKER_ENV, worker)
    assert template_db_name() == expected


def test_tên_database_mẫu_ngoài_xdist_giữ_nguyên(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chạy tay (không `-n`) không đổi hành vi: vẫn đúng một `appback_template`."""
    monkeypatch.delenv(XDIST_WORKER_ENV, raising=False)
    assert template_db_name() == TEMPLATE_DB


def test_hai_tiến_trình_xdist_không_dùng_chung_database_mẫu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hai tiến trình xdist khác nhau ra hai tên database mẫu khác nhau."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw0")
    first = template_db_name()
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw1")
    assert template_db_name() != first


# --- vết case: nhiều tiến trình nối vào cùng một file --------------------------------

LINES_PER_WRITER = 150
WRITERS = 6


@dataclass
class _FakeUrl:
    """URL tối thiểu mà `trace_case` đọc (`path`)."""

    path: str = "/v1/things"


@dataclass
class _FakeRequest:
    """Request tối thiểu mà `trace_case` đọc (`method`, `url`)."""

    method: str = "GET"
    url: _FakeUrl = field(default_factory=_FakeUrl)


@dataclass
class _FakeResponse:
    """Đủ những gì `trace_case` đọc: request, `status_code`, header và thân JSON."""

    status_code: int = 422
    request: _FakeRequest = field(default_factory=_FakeRequest)
    headers: dict[str, str] = field(default_factory=lambda: {"content-type": "application/json"})

    def json(self) -> dict[str, str]:
        """Thân W7 có `code` — `_error_code` lấy nó ra."""
        return {"code": "VALIDATION_ERROR"}


@dataclass
class _FakeItem:
    """Chỗ `trace_case` chỉ dùng `.name`; tên dài để dòng JSON không ngắn giả tạo."""

    name: str


def _item(name: str) -> pytest.Item:
    """`trace_case` chỉ đọc `.name` của item — cast để mypy strict thấy đúng chữ ký thật."""
    return cast(pytest.Item, _FakeItem(name))


def _response() -> httpx.Response:
    """Cast tương tự cho response: chỉ `request`, `status_code`, `headers`, `json()` được đọc."""
    return cast(httpx.Response, _FakeResponse())


def _append_traces(path: str, worker: str) -> None:
    """Trong một tiến trình con: ghi `LINES_PER_WRITER` vết như một worker xdist (module-level: picklable)."""
    os.environ[api_fixtures.TRACE_ENV] = path
    with patch.object(api_fixtures, "operation_of", return_value=f"listThings_{worker}"):
        for index in range(LINES_PER_WRITER):
            api_fixtures.trace_case(_item(f"test_listThings__C02_{worker}_{index:04d}"), _response())


def test_vết_case_nhiều_tiến_trình_không_xen_dòng(tmp_path: Path) -> None:
    """`WRITERS` tiến trình thật nối vào một `CASE_TRACE_FILE`: đủ dòng, mỗi dòng còn là JSON đúng.

    Dòng xen nhau sẽ hiện ra ở `json.loads` (hỏng) hay ở số dòng (thiếu/thừa), là đúng cái
    `case_gate` sẽ thấy. Tiến trình thật chứ không luồng: xdist dựng tiến trình, và chỉ tiến trình
    mới đi qua O_APPEND của kernel.
    """
    trace = tmp_path / "case-trace.jsonl"
    context = multiprocessing.get_context("spawn")  # cùng cách xdist dựng worker ở mọi nền
    processes = [context.Process(target=_append_traces, args=(str(trace), f"gw{i}")) for i in range(WRITERS)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=120)
    assert [p.exitcode for p in processes] == [0] * WRITERS

    lines = trace.read_text(encoding="utf-8").splitlines()
    assert len(lines) == WRITERS * LINES_PER_WRITER
    records = [json.loads(line) for line in lines]
    assert {r["op"] for r in records} == {f"listThings_gw{i}" for i in range(WRITERS)}
    assert len({r["test"] for r in records}) == WRITERS * LINES_PER_WRITER
    assert all(r["status"] == 422 and r["code"] == "VALIDATION_ERROR" for r in records)


def test_vết_case_không_có_biến_môi_trường_thì_không_ghi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Không đặt `CASE_TRACE_FILE` (chạy ngoài cổng) → không tạo file, dù chạy song song."""
    monkeypatch.delenv(api_fixtures.TRACE_ENV, raising=False)
    with patch.object(api_fixtures, "operation_of", return_value="listThings"):
        api_fixtures.trace_case(_item("test_listThings__C02"), _response())
    assert list(tmp_path.iterdir()) == []
