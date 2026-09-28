"""Test hợp đồng của #28 `templates_list_templates` và #29 `templates_create_template` (B2-07 [2], [6], [8]).

Ma trận case: #28 Đ → C01 C06 C08 C15 C17; #29 G → C01 C02 C03 C06 C07 C08 C16 C17. Cộng test đặt tên
theo việc: không khử trùng, `created_by` từ token, cô lập theo dự án, thứ tự, `touch_project`, CASCADE,
khoá trước khi đếm trần.
"""

import asyncio
import re
import unicodedata
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.templates.settings import reset_templates_settings_cache
from apps.api.templates.tests._helpers import (
    FE_BODIES,
    FORBIDDEN_ROLE,
    LIMIT_TEST,
    headers_of,
    project_updated_at,
    seed_project,
    template_body,
    template_rows,
    templates_path,
    with_env,
)
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.clock import FakeClock

TEMPLATE_KEYS = {"id", "name", "projectId", "createdAt", "scope", "objectKind", "fields"}
ID_PATTERN = re.compile(r"^tpl_[0-9A-HJKMNP-TV-Z]{26}$")
INSTANT_PATTERN = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")

# ---------------------------------------------------------------------------
# #28 Đ: C01 C06 C08 C15 C17
# ---------------------------------------------------------------------------


async def test_templates_list_templates__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Bốn nhánh khuôn FE thật → mảng trần, cũ nhất trước, `fields` đúng như đã gửi."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    for kind in FE_BODIES:
        fake_clock.advance(timedelta(seconds=1))
        await api_client.post(
            templates_path(project.id), json=template_body(kind, name=f"Khuôn {kind}"), headers=headers
        )
    response = await api_client.get(templates_path(project.id), headers=headers)
    assert response.status_code == 200
    listed = response.json()
    assert [(item["objectKind"], item["fields"]) for item in listed] == list(FE_BODIES.items())
    assert all(set(item) == TEMPLATE_KEYS and item["scope"] == "project" for item in listed)


async def test_templates_list_templates__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không là thành viên → 404 `resource:"project"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    outsider = await make_user(db_session, role="admin")
    response = await api_client.get(templates_path(project.id), headers=headers_of(outsider))
    assert (response.status_code, response.json()["resource"]) == (404, "project")


async def test_templates_list_templates__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    response = await api_client.get(templates_path(project.id), headers=headers_of(owner))
    assert response.status_code == 404


@pytest.mark.parametrize("count", [0, 1, LIMIT_TEST])
async def test_templates_list_templates__C15(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    fake_clock: FakeClock,
    count: int,
) -> None:
    """Trần = 3: 0, 1, 3 mục trả trọn; khuôn thứ 4 → 422 `TEMPLATE_LIMIT_REACHED`, danh sách vẫn 3."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    with with_env(monkeypatch, reset_templates_settings_cache, TEMPLATES_MAX=LIMIT_TEST):
        for number in range(count):
            fake_clock.advance(timedelta(seconds=1))
            await api_client.post(
                templates_path(project.id), json=template_body(name=f"Khuôn {number}"), headers=headers
            )
        listed = await api_client.get(templates_path(project.id), headers=headers)
        assert [item["name"] for item in listed.json()] == [f"Khuôn {n}" for n in range(count)]
        if count == LIMIT_TEST:
            over = await api_client.post(templates_path(project.id), json=template_body(), headers=headers)
            assert (over.status_code, over.json()["code"]) == (422, "TEMPLATE_LIMIT_REACHED")
            assert len((await api_client.get(templates_path(project.id), headers=headers)).json()) == LIMIT_TEST


async def test_templates_list_templates__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Khuôn tường chỉ có `kind` → `fields` đúng một khoá; `fields: {}` → `{}`; không `null`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    await api_client.post(
        templates_path(project.id), json=template_body(fields={"kind": "loadBearing"}), headers=headers
    )
    fake_clock.advance(timedelta(seconds=1))  # cùng tích tắc thì thứ tự rơi về `id` ngẫu nhiên
    await api_client.post(templates_path(project.id), json=template_body("room", fields={}), headers=headers)
    response = await api_client.get(templates_path(project.id), headers=headers)
    assert [item["fields"] for item in response.json()] == [{"kind": "loadBearing"}, {}]
    assert "null" not in response.text


# ---------------------------------------------------------------------------
# #29 G: C01 C02 C03 C06 C07 C08 C16 C17
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(FE_BODIES))
async def test_templates_create_template__C01(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    kind: str,
) -> None:
    """Thân FE thật của từng nhánh → 201, đúng bảy khoá, `id` tpl_+ULID, `createdAt` `.sssZ`, dòng ghi (K05, K22)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(templates_path(project.id), json=template_body(kind), headers=headers_of(owner))
    assert response.status_code == 201
    out = response.json()
    assert set(out) == TEMPLATE_KEYS
    assert ID_PATTERN.match(out["id"])
    assert INSTANT_PATTERN.match(out["createdAt"])
    assert (out["projectId"], out["scope"], out["objectKind"], out["fields"]) == (
        project.id,
        "project",
        kind,
        FE_BODIES[kind],
    )
    rows = await template_rows(db_sessionmaker, project.id)
    assert [(row.id, row.created_by, row.fields) for row in rows] == [(out["id"], owner.id, FE_BODIES[kind])]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        (template_body("door"), None),
        (template_body("furniture", fields={"rotationDeg": 360}), "fields.rotationDeg"),
        (template_body("furniture", fields={"rotationDeg": -0.5}), "fields.rotationDeg"),
        (template_body("opening", fields={"sillHeightMm": -1}), "fields.sillHeightMm"),
        (template_body("wall", fields={"heightMm": 0}), "fields.heightMm"),
        (template_body("wall", fields={"thicknessMm": 1.5}), "fields.thicknessMm"),
        (template_body("wall", fields={"thicknessMm": "100"}), "fields.thicknessMm"),
        (template_body("wall", fields={"heightMm": True}), "fields.heightMm"),
        (template_body("wall", fields={"kind": "curtain"}), "fields.kind"),
        (template_body("room", fields={"usage": "attic"}), "fields.usage"),
        (template_body("wall", fields={"heightMm": None}), "fields"),
        (template_body("wall", name="Giả\u202emạo"), "name"),
        (template_body("wall", name="  "), "name"),
        (template_body("wall", name="a" * 121), "name"),
        ({"objectKind": "wall", "name": "Thiếu fields"}, "fields"),
    ],
    ids=[
        "unknown-kind",
        "rotation-360",
        "rotation-negative",
        "sill-negative",
        "height-zero",
        "mm-float",
        "mm-string",
        "mm-bool",
        "wall-kind-enum",
        "room-usage-enum",
        "null-field",
        "name-rlo",
        "name-blank",
        "name-121",
        "missing-fields",
    ],
)
async def test_templates_create_template__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, body: dict[str, Any], field: str | None
) -> None:
    """Giá trị ngoài dải, enum lạ, `objectKind` lạ, kiểu số sai, tên xấu, thiếu `fields` → 422 đúng `field`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(templates_path(project.id), json=body, headers=headers_of(owner))
    assert response.status_code == 422
    out = response.json()
    assert out["code"] == "VALIDATION"
    # Union phân biệt: pydantic đặt tên nhánh (`wall.fields.heightMm`) trước đường trường; kind lạ không có `field`.
    assert ("field" not in out) if field is None else out["field"].endswith(field)


@pytest.mark.parametrize(
    "body",
    [
        template_body() | {"id": "tpl_01J9ZZZZZZZZZZZZZZZZZZZZZZ"},
        template_body() | {"projectId": "prj_x"},
        template_body() | {"createdAt": "2026-01-01T00:00:00.000Z"},
        template_body() | {"scope": "project"},
        template_body("room", fields={"thicknessMm": 200}),
        template_body("wall", fields={"heightMm": 2800, "extra": 1}),
    ],
    ids=["id", "projectId", "createdAt", "scope", "room-foreign-key", "fields-extra"],
)
async def test_templates_create_template__C03(
    api_client: httpx.AsyncClient, db_session: AsyncSession, body: dict[str, Any]
) -> None:
    """Khoá lạ ở gốc (kể cả `id`/`projectId`/`createdAt`/`scope`) hay trong `fields` → 422 `VALIDATION`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(templates_path(project.id), json=body, headers=headers_of(owner))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_templates_create_template__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không là thành viên → 404 `resource:"project"` (K08)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    outsider = await make_user(db_session, role="admin")
    response = await api_client.post(templates_path(project.id), json=template_body(), headers=headers_of(outsider))
    assert (response.status_code, response.json()["resource"]) == (404, "project")


async def test_templates_create_template__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`viewer` → 403."""
    owner = await make_user(db_session, role="engineer")
    viewer = await make_user(db_session, role=FORBIDDEN_ROLE)
    project = await seed_project(db_session, owner=owner, members=[viewer])
    response = await api_client.post(templates_path(project.id), json=template_body(), headers=headers_of(viewer))
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")


async def test_templates_create_template__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    response = await api_client.post(templates_path(project.id), json=template_body(), headers=headers_of(owner))
    assert response.status_code == 404


async def test_templates_create_template__C16(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Tên NFD → lưu và trả NFC."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    nfc_name = "Cửa Áp Mái"
    body = template_body("opening", name=unicodedata.normalize("NFD", nfc_name))
    response = await api_client.post(templates_path(project.id), json=body, headers=headers_of(owner))
    assert (response.status_code, response.json()["name"]) == (201, nfc_name)
    assert (await template_rows(db_sessionmaker, project.id))[0].name == nfc_name


async def test_templates_create_template__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khuôn `wall` chỉ có `kind` → `fields` đúng một khoá, vắng vẫn vắng."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    body = template_body("wall", fields={"kind": "envelope"})
    response = await api_client.post(templates_path(project.id), json=body, headers=headers_of(owner))
    assert response.json()["fields"] == {"kind": "envelope"}


# ---------------------------------------------------------------------------
# Test đặt tên theo việc
# ---------------------------------------------------------------------------


async def test_templates_create_template__no_dedupe(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Hai lượt bấm cùng thân là hai khuôn khác id (không khử trùng)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    first = await api_client.post(templates_path(project.id), json=template_body(), headers=headers)
    second = await api_client.post(templates_path(project.id), json=template_body(), headers=headers)
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]
    assert len(await template_rows(db_sessionmaker, project.id)) == 2


async def test_templates_create_template__created_by_ignores_body(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`created_by` là người trong token; `createdBy` trong thân là khoá lạ → 422 (K05)."""
    owner = await make_user(db_session, role="engineer")
    editor = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, members=[editor])
    forged = await api_client.post(
        templates_path(project.id), json=template_body() | {"createdBy": owner.id}, headers=headers_of(editor)
    )
    assert forged.status_code == 422
    await api_client.post(templates_path(project.id), json=template_body(), headers=headers_of(editor))
    assert [row.created_by for row in await template_rows(db_sessionmaker, project.id)] == [editor.id]


async def test_templates_list_templates__order_and_isolation(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Cũ nhất trước theo `createdAt`; khuôn của dự án khác không lọt vào."""
    owner = await make_user(db_session, role="engineer")
    mine = await seed_project(db_session, owner=owner)
    other = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    await api_client.post(templates_path(other.id), json=template_body(name="Của dự án khác"), headers=headers)
    for name in ("Một", "Hai", "Ba"):
        fake_clock.advance(timedelta(seconds=1))
        await api_client.post(templates_path(mine.id), json=template_body(name=name), headers=headers)
    response = await api_client.get(templates_path(mine.id), headers=headers)
    assert [item["name"] for item in response.json()] == ["Một", "Hai", "Ba"]


async def test_templates_create_template__touch_project(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`touch_project` chạy khi tạo (201), không chạy khi 422 (đo bằng `projects.updated_at`)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    fake_clock.advance(timedelta(hours=1))
    assert (await api_client.post(templates_path(project.id), json=template_body(), headers=headers)).status_code == 201
    touched = await project_updated_at(db_sessionmaker, project.id)
    assert touched == fake_clock.now()

    fake_clock.advance(timedelta(hours=1))
    with with_env(monkeypatch, reset_templates_settings_cache, TEMPLATES_MAX=1):
        assert (
            await api_client.post(templates_path(project.id), json=template_body(), headers=headers)
        ).status_code == 422
    assert await project_updated_at(db_sessionmaker, project.id) == touched


async def test_templates_create_template__lock_before_count(
    api_app: FastAPI,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`TEMPLATES_MAX` = 1, hai POST song song (hai client thật) → {201, 422}, đúng một dòng: đếm trần sau khoá."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    with with_env(monkeypatch, reset_templates_settings_cache, TEMPLATES_MAX=1):
        async with make_api_client(api_app) as client_a, make_api_client(api_app) as client_b:
            first, second = await asyncio.gather(
                client_a.post(templates_path(project.id), json=template_body(), headers=headers_of(owner)),
                client_b.post(templates_path(project.id), json=template_body(), headers=headers_of(owner)),
            )
    assert {first.status_code, second.status_code} == {201, 422}
    assert len(await template_rows(db_sessionmaker, project.id)) == 1


async def test_templates_create_template__project_cascade(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Xoá cứng dòng `projects` → khuôn đi theo (CASCADE)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    await api_client.post(templates_path(project.id), json=template_body(), headers=headers_of(owner))
    assert len(await template_rows(db_sessionmaker, project.id)) == 1
    await db_session.execute(delete(Project).where(Project.id == project.id))
    await db_session.commit()
    assert await template_rows(db_sessionmaker, project.id) == []
