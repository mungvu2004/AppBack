"""Test hợp đồng của #17 `measurements_create_record` (B2-07 [2], [6], [8]).

Ma trận case: G → C01 C02 C03 C06 C07 C08 C14 C16 C17 (C14 là case thêm cố định của #17), cộng các
test đặt tên theo việc: hoàn tác, tái dùng id, số/`NaN`/chuỗi/`bool`, id sai mẫu, U+202E, trần tổng
điểm, `touch_project`, CASCADE. Postgres thật, hai client thật cho C14 (K23).
"""

import asyncio
import unicodedata
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.measurements.settings import reset_measurements_settings_cache
from apps.api.measurements.tests._helpers import (
    FORBIDDEN_ROLE,
    LIMIT_TEST,
    floor_area_body,
    headers_of,
    measurement_path,
    measurement_rows,
    measurements_path,
    point_body,
    post_raw,
    project_updated_at,
    record_body,
    seed_project,
    with_env,
)
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.clock import FakeClock

# ---------------------------------------------------------------------------
# G: C01 C02 C03 C06 C07 C08 C14 C16 C17
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body", [record_body(), floor_area_body()], ids=["pointToPoint", "floorArea"])
async def test_measurements_create_record__C01(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    body: dict[str, Any],
) -> None:
    """Thân FE thật → 201, dây đúng năm khoá của schema FE; dòng ghi bằng `created_by` từ token (K05, K22)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(measurements_path(project.id), json=body, headers=headers_of(owner))
    assert response.status_code == 201
    assert response.json() == body

    rows = await measurement_rows(db_sessionmaker, project.id)
    assert [(row.measurement_id, row.created_by, row.raw_value) for row in rows] == [
        (body["id"], owner.id, body["rawValueMm"])
    ]
    assert len(rows[0].body_sha256) == 64


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"points": [point_body(0, 0)]}, "points"),
        ({"mode": "floorArea", "points": [point_body(0, 0), point_body(1, 1)]}, "points"),
        ({"points": [point_body(i, i) for i in range(201)]}, "points"),
        ({"rawValueMm": -1}, "rawValueMm"),
        ({"mode": "volume"}, "mode"),
    ],
    ids=["one-point", "floorArea-two-points", "201-points", "negative-raw", "unknown-mode"],
)
async def test_measurements_create_record__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, overrides: dict[str, Any], field: str
) -> None:
    """Số điểm ngoài dải, `rawValueMm` âm, mode lạ → 422 `VALIDATION` đúng `field`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(
        measurements_path(project.id), json=record_body() | overrides, headers=headers_of(owner)
    )
    assert response.status_code == 422
    assert (response.json()["code"], response.json()["field"]) == ("VALIDATION", field)


@pytest.mark.parametrize(
    "body",
    [
        record_body() | {"createdBy": "usr_x"},
        record_body(points=[point_body(0, 0) | {"w": 1}, point_body(1, 1)]),
        record_body() | {"body_sha256": "0" * 64},
    ],
    ids=["root", "points-0", "sha"],
)
async def test_measurements_create_record__C03(
    api_client: httpx.AsyncClient, db_session: AsyncSession, body: dict[str, Any]
) -> None:
    """Khoá lạ ở gốc hay trong `points[0]` → 422 `VALIDATION` (`extra="forbid"` mọi độ sâu)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(measurements_path(project.id), json=body, headers=headers_of(owner))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_measurements_create_record__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không là thành viên → 404 `resource:"project"` (K08)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    outsider = await make_user(db_session, role="admin")
    response = await api_client.post(measurements_path(project.id), json=record_body(), headers=headers_of(outsider))
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_measurements_create_record__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`viewer` (vai mạnh nhất thiếu `layer.edit`) → 403."""
    owner = await make_user(db_session, role="engineer")
    viewer = await make_user(db_session, role=FORBIDDEN_ROLE)
    project = await seed_project(db_session, owner=owner, members=[viewer])
    response = await api_client.post(measurements_path(project.id), json=record_body(), headers=headers_of(viewer))
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_measurements_create_record__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    response = await api_client.post(measurements_path(project.id), json=record_body(), headers=headers_of(owner))
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("second_name", "statuses", "rows"),
    [("Chiều rộng phòng khách", {201, 200}, 1), ("Tên khác", {201, 409}, 1)],
    ids=["same-body", "different-body"],
)
async def test_measurements_create_record__C14(
    api_app: FastAPI,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    second_name: str,
    statuses: set[int],
    rows: int,
) -> None:
    """Hai POST song song cùng id bằng hai client thật: cùng thân → {201, 200}; khác thân → {201, 409}; một dòng."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    async with make_api_client(api_app) as client_a, make_api_client(api_app) as client_b:
        first, second = await asyncio.gather(
            client_a.post(measurements_path(project.id), json=record_body(), headers=headers_of(owner)),
            client_b.post(measurements_path(project.id), json=record_body(name=second_name), headers=headers_of(owner)),
        )
    assert {first.status_code, second.status_code} == statuses
    if 409 in statuses:
        loser = first if first.status_code == 409 else second
        assert (loser.json()["code"], loser.json()["field"]) == ("MEASUREMENT_ID_TAKEN", "id")
    assert len(await measurement_rows(db_sessionmaker, project.id)) == rows


async def test_measurements_create_record__C16(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Tên NFD (và khoảng trắng thừa) → lưu và trả NFC; gửi lại bản NFC của cùng phép đo → 200."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    nfc_name = "Cửa Áp Mái"
    nfd_name = f"  {unicodedata.normalize('NFD', nfc_name)} "
    first = await api_client.post(
        measurements_path(project.id), json=record_body(name=nfd_name), headers=headers_of(owner)
    )
    assert first.status_code == 201
    assert first.json()["name"] == nfc_name
    assert (await measurement_rows(db_sessionmaker, project.id))[0].name == nfc_name

    again = await api_client.post(
        measurements_path(project.id), json=record_body(name=nfc_name), headers=headers_of(owner)
    )
    assert again.status_code == 200
    assert again.json()["name"] == nfc_name


async def test_measurements_create_record__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`z` vắng → response vắng `z`, không có `null` ở đâu cả; điểm có `z` giữ `z`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    points = [point_body(0, 0), point_body(1, 1, 5.5)]
    response = await api_client.post(
        measurements_path(project.id), json=record_body(points=points), headers=headers_of(owner)
    )
    assert response.status_code == 201
    assert response.json()["points"] == points
    assert "null" not in response.text


# ---------------------------------------------------------------------------
# Test đặt tên theo việc
# ---------------------------------------------------------------------------


async def test_measurements_create_record__undo_cycle(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Hoàn tác xoá: POST → DELETE 204 → POST lại nguyên bản ghi → 201; #16 thấy đúng một bản."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    body = floor_area_body()
    assert (await api_client.post(measurements_path(project.id), json=body, headers=headers)).status_code == 201
    deleted = await api_client.delete(measurement_path(project.id, body["id"]), headers=headers)
    assert (deleted.status_code, deleted.content) == (204, b"")
    assert (await api_client.post(measurements_path(project.id), json=body, headers=headers)).status_code == 201
    listed = await api_client.get(measurements_path(project.id), headers=headers)
    assert listed.json() == [body]


async def test_measurements_create_record__id_reuse_after_delete(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Có `MS-0001`, `MS-0002`; xoá `MS-0002`; POST `MS-0002` thân khác → 201 (id lớn nhất được tái dùng)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    for record_id in ("MS-0001", "MS-0002"):
        await api_client.post(measurements_path(project.id), json=record_body(record_id), headers=headers)
    await api_client.delete(measurement_path(project.id, "MS-0002"), headers=headers)
    other = record_body("MS-0002", name="Thân khác", raw_value_mm=1.0)
    response = await api_client.post(measurements_path(project.id), json=other, headers=headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Thân khác"


async def test_measurements_create_record__same_id_different_body_never_overwrites(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Cùng id khác thân (một điểm khác, một `z` thêm) → 409, bản đã lưu nguyên vẹn."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    await api_client.post(measurements_path(project.id), json=record_body(), headers=headers)
    moved = record_body(points=[point_body(0, 0, 1), point_body(3000.5, 0)])
    response = await api_client.post(measurements_path(project.id), json=moved, headers=headers)
    assert response.status_code == 409
    rows = await measurement_rows(db_sessionmaker, project.id)
    assert [row.points for row in rows] == [[{"x": 0.0, "y": 0.0}, {"x": 3000.5, "y": 0.0}]]


async def test_measurements_create_record__negative_zero_equals_zero(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`-0.0` chuẩn hoá thành `0.0`: gửi lại với `0` cho cùng dấu vân tay → 200, không phải 409."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    negative = record_body(points=[point_body(-0.0, -0.0), point_body(5, 5)])
    assert (await api_client.post(measurements_path(project.id), json=negative, headers=headers)).status_code == 201
    positive = record_body(points=[point_body(0, 0), point_body(5, 5)])
    assert (await api_client.post(measurements_path(project.id), json=positive, headers=headers)).status_code == 200


async def test_measurements_create_record__integer_coordinates_accepted(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`"x": 1000` (số nguyên mà FE gửi) → 201."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    body = record_body(points=[point_body(1000, 0), point_body(2000, 0)], raw_value_mm=1000)
    response = await api_client.post(measurements_path(project.id), json=body, headers=headers_of(owner))
    assert response.status_code == 201


@pytest.mark.parametrize(
    "raw_points",
    [
        '[{"x": NaN, "y": 0}, {"x": 1, "y": 1}]',
        '[{"x": Infinity, "y": 0}, {"x": 1, "y": 1}]',
        '[{"x": "1.5", "y": 0}, {"x": 1, "y": 1}]',
        '[{"x": true, "y": 0}, {"x": 1, "y": 1}]',
        '[{"x": 1, "y": 0, "z": null}, {"x": 1, "y": 1}]',
        '[{"x": 1}, {"x": 1, "y": 1}]',
    ],
    ids=["nan", "infinity", "string", "bool", "null-z", "missing-y"],
)
async def test_measurements_create_record__bad_numbers(
    api_client: httpx.AsyncClient, db_session: AsyncSession, raw_points: str
) -> None:
    """`NaN`/`Infinity` thô, chuỗi số, `bool`, `z: null`, thiếu `y` trong điểm → 422 `field` bắt đầu bằng `points`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    raw = '{"id": "MS-0001", "name": "n", "mode": "pointToPoint", "points": ' + raw_points + ', "rawValueMm": 2}'
    response = await post_raw(api_client, measurements_path(project.id), headers_of(owner), raw)
    assert response.status_code == 422
    assert response.json()["field"].startswith("points")


async def test_measurements_create_record__raw_value_not_finite(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`rawValueMm: NaN` thô và `"rawValueMm": "5"` → 422 `field:"rawValueMm"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    base = '{"id": "MS-0001", "name": "n", "mode": "pointToPoint", "points": [{"x":0,"y":0},{"x":1,"y":1}], '
    for tail in ('"rawValueMm": NaN}', '"rawValueMm": "5"}', '"rawValueMm": true}'):
        response = await post_raw(api_client, measurements_path(project.id), headers, base + tail)
        assert (response.status_code, response.json()["field"]) == (422, "rawValueMm")


@pytest.mark.parametrize("bad_id", ["MS-12", "MS-9999999999999999", "ms-0001", "MS-00A1", "0001", ""])
async def test_measurements_create_record__bad_id(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad_id: str
) -> None:
    """Id sai mẫu, kể cả 16 chữ số → 422 `field:"id"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(measurements_path(project.id), json=record_body(bad_id), headers=headers_of(owner))
    assert (response.status_code, response.json()["field"]) == (422, "id")


async def test_measurements_create_record__fifteen_digit_id_accepted(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Biên trên: `MS-` + 15 chữ số → 201."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(
        measurements_path(project.id), json=record_body("MS-999999999999999"), headers=headers_of(owner)
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    "bad_name",
    ["Gia‮mạo", "Điều\x07khiển", "   ", "", "a" * 121, "Ẩn⁦danh"],
    ids=["rlo", "bell", "blank", "empty", "121-chars", "isolate"],
)
async def test_measurements_create_record__bad_name(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad_name: str
) -> None:
    """Tên chứa ký tự đảo chiều/điều khiển, rỗng, chỉ khoảng trắng, quá 120 → 422 `field:"name"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(
        measurements_path(project.id), json=record_body(name=bad_name), headers=headers_of(owner)
    )
    assert (response.status_code, response.json()["field"]) == (422, "name")


async def test_measurements_create_record__name_120_chars_accepted(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Biên trên của tên: đúng 120 ký tự → 201."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.post(
        measurements_path(project.id), json=record_body(name="a" * 120), headers=headers_of(owner)
    )
    assert response.status_code == 201


async def test_measurements_create_record__count_limit(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`MEASUREMENTS_MAX` = 3: bản thứ 4 → 422 `MEASUREMENT_LIMIT_REACHED`, không ghi; gửi lại bản đã lưu → 200."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    with with_env(monkeypatch, reset_measurements_settings_cache, MEASUREMENTS_MAX=LIMIT_TEST):
        for number in range(1, LIMIT_TEST + 1):
            ok = await api_client.post(
                measurements_path(project.id), json=record_body(f"MS-{number:04d}"), headers=headers
            )
            assert ok.status_code == 201
        over = await api_client.post(measurements_path(project.id), json=record_body("MS-0004"), headers=headers)
        assert (over.status_code, over.json()["code"]) == (422, "MEASUREMENT_LIMIT_REACHED")
        again = await api_client.post(measurements_path(project.id), json=record_body("MS-0001"), headers=headers)
        assert again.status_code == 200
    assert len(await measurement_rows(db_sessionmaker, project.id)) == LIMIT_TEST


async def test_measurements_create_record__total_points_limit(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`MEASUREMENT_POINTS_TOTAL_MAX` = 5: có 3 điểm, thêm 3 điểm → 422, không ghi; gửi lại bản đã lưu vẫn 200."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    with with_env(monkeypatch, reset_measurements_settings_cache, MEASUREMENT_POINTS_TOTAL_MAX=5):
        first = floor_area_body("MS-0001")
        assert (await api_client.post(measurements_path(project.id), json=first, headers=headers)).status_code == 201
        over = await api_client.post(measurements_path(project.id), json=floor_area_body("MS-0002"), headers=headers)
        assert (over.status_code, over.json()["code"]) == (422, "MEASUREMENT_LIMIT_REACHED")
        assert (await api_client.post(measurements_path(project.id), json=first, headers=headers)).status_code == 200
        fits = record_body("MS-0003")
        assert (await api_client.post(measurements_path(project.id), json=fits, headers=headers)).status_code == 201
    assert [row.measurement_id for row in await measurement_rows(db_sessionmaker, project.id)] == ["MS-0001", "MS-0003"]


async def test_measurements_create_record__points_max_setting(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`MEASUREMENT_POINTS_MAX` đọc lười lúc chạy: đặt = 2 thì 3 điểm → 422 `field:"points"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    with with_env(monkeypatch, reset_measurements_settings_cache, MEASUREMENT_POINTS_MAX=2):
        response = await api_client.post(
            measurements_path(project.id), json=floor_area_body(), headers=headers_of(owner)
        )
    assert (response.status_code, response.json()["field"]) == (422, "points")


async def test_measurements_create_record__touch_project(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`touch_project` chạy khi tạo (201) và **không** chạy khi 200, 409 hay 422 (đo bằng `projects.updated_at`)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    path = measurements_path(project.id)
    fake_clock.advance(timedelta(hours=1))
    assert (await api_client.post(path, json=record_body(), headers=headers)).status_code == 201
    touched = await project_updated_at(db_sessionmaker, project.id)
    assert touched == fake_clock.now()

    fake_clock.advance(timedelta(hours=1))
    assert (await api_client.post(path, json=record_body(), headers=headers)).status_code == 200
    assert (await api_client.post(path, json=record_body(name="Khác"), headers=headers)).status_code == 409
    assert (
        await api_client.post(path, json=record_body("MS-0002", raw_value_mm=-1), headers=headers)
    ).status_code == 422
    with with_env(monkeypatch, reset_measurements_settings_cache, MEASUREMENTS_MAX=1):
        assert (await api_client.post(path, json=record_body("MS-0003"), headers=headers)).status_code == 422
    assert await project_updated_at(db_sessionmaker, project.id) == touched


async def test_measurements_create_record__second_session_and_project_cascade(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đọc lại qua session mới thấy dòng (K22); xoá cứng dòng `projects` → phép đo đi theo (CASCADE)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    await api_client.post(measurements_path(project.id), json=record_body(), headers=headers_of(owner))
    assert len(await measurement_rows(db_sessionmaker, project.id)) == 1

    await db_session.execute(delete(Project).where(Project.id == project.id))
    await db_session.commit()
    assert await measurement_rows(db_sessionmaker, project.id) == []
