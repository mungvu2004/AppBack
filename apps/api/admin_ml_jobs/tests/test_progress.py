"""Hai route tiến trình N36, N37 (B6-03a [6], [8]) — luật bước chưa trọn và cửa sổ muộn.

C07 nằm ở `test_contract.py`. Hai luật khó nhất của module đều ở đây:

- **bước cuối chờ đủ `split`**: N36 chỉ trả `step <` bước lớn nhất khi job còn có thể ghi
  thêm `split` cho bước ấy — nếu không, lượt sau (`since` = bước cuối, loại trừ) mất
  `validation` vĩnh viễn;
- **`nextCursor` còn tới hết cửa sổ muộn**: vòng polling của FE dừng khi tab ẩn, nên cursor
  vắng sớm là FE không bao giờ đọc lại. Cửa sổ tính từ `ended_at` theo `Clock` của app, nên
  `fake_clock` lái được.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.admin_ml_jobs.settings import get_training_settings
from apps.api.admin_ml_jobs.tests._helpers import (
    MISSING_JOB_ID,
    OPENING,
    add_logs,
    add_metrics,
    logs_path,
    metrics_path,
)
from apps.api.core.auth import Principal
from packages.db.models.admin_ml_jobs import TrainingJobRow
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.factories.admin_ml_jobs import make_training_job
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock


async def _get(client: httpx.AsyncClient, principal: Principal, path: str, **params: str | int) -> httpx.Response:
    """GET có token admin."""
    return await client.get(path, headers=auth_headers(principal), params=params)


async def _job(
    db: AsyncSession, *, status: str = "running", started_at: datetime | None = None, ended_at: datetime | None = None
) -> TrainingJobRow:
    """Một job họ cửa/nội thất ở `status`, kèm bản dataset `ready` cho FK.

    Hai mốc chỉ truyền khi test cần cửa sổ muộn: mặc định của factory là giờ **thật**, lệch
    hẳn với `fake_clock` mà app dùng, nên `ended_at` giả sẽ nhỏ hơn `started_at` thật và
    CHECK `ended_after_started` chặn ngay lượt test tự kết thúc job.
    """
    dataset = await make_dataset(db, family=OPENING)
    version = await make_dataset_version(db, dataset=dataset, status="ready")
    return await make_training_job(
        db,
        dataset_version_id=version.id,
        family=OPENING,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
    )


def _steps(body: dict[str, object]) -> list[tuple[int, str]]:
    """`(step, split)` của một trang N36, giữ nguyên thứ tự trả về."""
    items = body["items"]
    assert isinstance(items, list)
    return [(item["step"], item["split"]) for item in items]


# ---------------------------------------------------------------------------
# N36 — ml_list_job_metrics
# ---------------------------------------------------------------------------


async def test_ml_list_job_metrics__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """200, `step` tăng rồi `split`; `since` loại trừ; `nextCursor` là chuỗi số của bước cuối."""
    job = await _job(db_session)
    await add_metrics(
        db_session,
        job_id=job.id,
        at=fake_clock.now(),
        points=[(1, "train"), (1, "validation"), (2, "train"), (2, "validation"), (3, "train")],
    )

    first = await _get(api_client, fake_principal, metrics_path(job.id))
    after_one = await _get(api_client, fake_principal, metrics_path(job.id), since=1)

    assert first.status_code == 200
    assert _steps(first.json()) == [(1, "train"), (1, "validation"), (2, "train"), (2, "validation")]
    assert first.json()["nextCursor"] == "2"
    assert _steps(after_one.json()) == [(2, "train"), (2, "validation")]


async def test_ml_list_job_metrics__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`since` < -1 và `limit` ngoài [1, 200] → 422 của khung (query đã kiểm biên)."""
    job = await _job(db_session)

    bad_since = await _get(api_client, fake_principal, metrics_path(job.id), since=-2)
    bad_limit = await _get(api_client, fake_principal, metrics_path(job.id), limit=201)
    zero_limit = await _get(api_client, fake_principal, metrics_path(job.id), limit=0)

    assert bad_since.status_code == 422
    assert bad_limit.status_code == 422
    assert zero_limit.status_code == 422


async def test_ml_list_job_metrics__C08(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Job không có → 404 `trainingJob`, đọc **trước** mọi hàng ([6])."""
    response = await _get(api_client, fake_principal, metrics_path(MISSING_JOB_ID))

    assert response.status_code == 404
    assert response.json()["resource"] == "trainingJob"


async def test_ml_list_job_metrics__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """0 điểm; 1 bước; 5 bước với `limit=2` → `nextCursor` rồi trang 2; cửa sổ muộn giữ cursor, quá thì vắng."""
    job = await _job(db_session, started_at=fake_clock.now())
    empty = await _get(api_client, fake_principal, metrics_path(job.id))
    assert empty.json() == {"items": [], "nextCursor": "-1"}

    await add_metrics(db_session, job_id=job.id, at=fake_clock.now(), points=[(0, "train"), (0, "validation")])
    one = await _get(api_client, fake_principal, metrics_path(job.id))
    assert one.json()["items"] == [], "bước 0 là bước cuối của job đang chạy: còn chờ split"
    assert one.json()["nextCursor"] == "-1"

    points = [(step, split) for step in range(5) for split in ("train", "validation")]
    await add_metrics(db_session, job_id=job.id, at=fake_clock.now(), points=[p for p in points if p[0] > 0])
    first = await _get(api_client, fake_principal, metrics_path(job.id), limit=2)
    second = await _get(
        api_client, fake_principal, metrics_path(job.id), limit=2, since=int(first.json()["nextCursor"])
    )

    assert _steps(first.json()) == [(0, "train"), (0, "validation")]
    assert first.json()["nextCursor"] == "0"
    assert _steps(second.json()) == [(1, "train"), (1, "validation")]

    # Job kết thúc trong cửa sổ muộn: đọc hết nhưng `nextCursor` vẫn còn (FE còn polling).
    job.status = "cancelled"
    job.ended_at = fake_clock.now()
    await db_session.commit()
    inside = await _get(api_client, fake_principal, metrics_path(job.id), since=3)
    assert _steps(inside.json()) == [(4, "train"), (4, "validation")]
    assert inside.json()["nextCursor"] == "4"

    fake_clock.advance(timedelta(seconds=get_training_settings().training_late_window_s + 1))
    outside = await _get(api_client, fake_principal, metrics_path(job.id), since=3)
    assert _steps(outside.json()) == [(4, "train"), (4, "validation")]
    assert "nextCursor" not in outside.json()


async def test_ml_list_job_metrics__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Điểm chỉ có `loss` (họ cửa/nội thất): `iou`, `map50` **vắng khoá**, không `null` (W2)."""
    job = await _job(db_session)
    await add_metrics(
        db_session, job_id=job.id, at=fake_clock.now(), points=[(1, "train"), (1, "validation"), (2, "train")]
    )

    item = (await _get(api_client, fake_principal, metrics_path(job.id))).json()["items"][0]

    assert set(item) == {"epoch", "loss", "recordedAt", "split", "step"}
    assert {"iou", "map50"}.isdisjoint(item)


async def test_ml_list_job_metrics_holds_the_last_step_until_both_splits_arrive(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Bước 3 mới một `split` → chưa trả; thêm bước 4 → bước 3 ra đủ hai `split` ([8] N36)."""
    job = await _job(db_session)
    await add_metrics(db_session, job_id=job.id, at=fake_clock.now(), points=[(3, "train"), (3, "validation")])
    held = await _get(api_client, fake_principal, metrics_path(job.id), since=2)

    await add_metrics(db_session, job_id=job.id, at=fake_clock.now(), points=[(4, "train")])
    released = await _get(api_client, fake_principal, metrics_path(job.id), since=2)

    assert held.json()["items"] == []
    assert held.json()["nextCursor"] == "2", "trang rỗng trả lại chính `since`"
    assert _steps(released.json()) == [(3, "train"), (3, "validation")]


async def test_ml_list_job_metrics_releases_the_last_step_after_the_job_ends(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Job kết thúc trong cửa sổ, bước cuối mới có `train` → chưa trả; `validation` tới → trả."""
    job = await _job(db_session, status="cancelled", ended_at=fake_clock.now())
    await add_metrics(db_session, job_id=job.id, at=fake_clock.now(), points=[(5, "train")])

    held = await _get(api_client, fake_principal, metrics_path(job.id))
    await add_metrics(db_session, job_id=job.id, at=fake_clock.now(), points=[(5, "validation")])
    released = await _get(api_client, fake_principal, metrics_path(job.id))

    assert held.json()["items"] == []
    assert _steps(released.json()) == [(5, "train"), (5, "validation")]


async def test_ml_list_job_metrics_releases_the_last_step_past_the_late_window(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Quá cửa sổ muộn, bước cuối thiếu `validation` vẫn phải ra (sẽ không còn ai ghi nữa)."""
    job = await _job(db_session, status="failed", ended_at=fake_clock.now())
    await add_metrics(db_session, job_id=job.id, at=fake_clock.now(), points=[(5, "train")])

    held = await _get(api_client, fake_principal, metrics_path(job.id))
    fake_clock.advance(timedelta(seconds=get_training_settings().training_late_window_s + 1))
    released = await _get(api_client, fake_principal, metrics_path(job.id))

    assert held.json()["items"] == []
    assert _steps(released.json()) == [(5, "train")]
    assert "nextCursor" not in released.json()


async def test_ml_list_job_metrics_never_cuts_a_step_in_half(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """`limit=1` trên bước đủ hai `split` vẫn trả **cả hai**: `since=<bước>` sẽ bỏ qua bước ấy."""
    job = await _job(db_session)
    await add_metrics(
        db_session,
        job_id=job.id,
        at=fake_clock.now(),
        points=[(1, "train"), (1, "validation"), (2, "train"), (2, "validation")],
    )

    page = await _get(api_client, fake_principal, metrics_path(job.id), limit=1)

    assert _steps(page.json()) == [(1, "train"), (1, "validation")]
    assert page.json()["nextCursor"] == "1"


# ---------------------------------------------------------------------------
# N37 — ml_list_job_logs
# ---------------------------------------------------------------------------


async def test_ml_list_job_logs__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """200, `seq` tăng, `since` loại trừ; `nextCursor` là `seq` cuối trang."""
    job = await _job(db_session)
    await add_logs(db_session, job_id=job.id, at=fake_clock.now(), seqs=[0, 1, 2])

    all_lines = await _get(api_client, fake_principal, logs_path(job.id))
    after_one = await _get(api_client, fake_principal, logs_path(job.id), since=1)

    assert all_lines.status_code == 200
    assert [item["seq"] for item in all_lines.json()["items"]] == [0, 1, 2]
    assert all_lines.json()["nextCursor"] == "2"
    assert [item["seq"] for item in after_one.json()["items"]] == [2]
    assert all_lines.json()["items"][0]["message"] == "dong log 0"


async def test_ml_list_job_logs__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`since` < -1 và `limit` ngoài [1, 200] → 422 của khung."""
    job = await _job(db_session)

    bad_since = await _get(api_client, fake_principal, logs_path(job.id), since=-2)
    bad_limit = await _get(api_client, fake_principal, logs_path(job.id), limit=201)

    assert bad_since.status_code == 422
    assert bad_limit.status_code == 422


async def test_ml_list_job_logs__C08(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Job không có → 404 `trainingJob`, trước khi đọc `training_logs`."""
    response = await _get(api_client, fake_principal, logs_path(MISSING_JOB_ID))

    assert response.status_code == 404
    assert response.json()["resource"] == "trainingJob"


async def test_ml_list_job_logs__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """0 dòng; 1 dòng; 5 dòng `limit=2` → hai trang; cửa sổ muộn giữ `nextCursor`, quá thì vắng."""
    job = await _job(db_session, started_at=fake_clock.now())
    empty = await _get(api_client, fake_principal, logs_path(job.id))
    assert empty.json() == {"items": [], "nextCursor": "-1"}

    await add_logs(db_session, job_id=job.id, at=fake_clock.now(), seqs=[0])
    one = await _get(api_client, fake_principal, logs_path(job.id))
    assert [item["seq"] for item in one.json()["items"]] == [0]

    await add_logs(db_session, job_id=job.id, at=fake_clock.now(), seqs=[1, 2, 3, 4])
    first = await _get(api_client, fake_principal, logs_path(job.id), limit=2)
    second = await _get(api_client, fake_principal, logs_path(job.id), limit=2, since=int(first.json()["nextCursor"]))

    assert [item["seq"] for item in first.json()["items"]] == [0, 1]
    assert [item["seq"] for item in second.json()["items"]] == [2, 3]

    job.status = "cancelled"
    job.ended_at = fake_clock.now()
    await db_session.commit()
    inside = await _get(api_client, fake_principal, logs_path(job.id), since=3)
    assert [item["seq"] for item in inside.json()["items"]] == [4]
    assert inside.json()["nextCursor"] == "4"

    fake_clock.advance(timedelta(seconds=get_training_settings().training_late_window_s + 1))
    outside = await _get(api_client, fake_principal, logs_path(job.id), since=3)
    assert [item["seq"] for item in outside.json()["items"]] == [4]
    assert "nextCursor" not in outside.json()


async def test_ml_list_job_logs__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Dòng log chỉ có bốn khoá dây: không `jobId`, không `dedupeSha` (K01)."""
    job = await _job(db_session)
    await add_logs(db_session, job_id=job.id, at=fake_clock.now(), seqs=[0])

    item = (await _get(api_client, fake_principal, logs_path(job.id))).json()["items"][0]

    assert set(item) == {"at", "level", "message", "seq"}


@pytest.mark.parametrize("path_of", [metrics_path, logs_path])
async def test_ml_training_progress_rejects_a_malformed_job_id(
    api_client: httpx.AsyncClient, fake_principal: Principal, path_of: Callable[[str], str]
) -> None:
    """Id sai mẫu trên đường của cả N36 và N37 → 404, không 422 (id là tài nguyên)."""
    response = await _get(api_client, fake_principal, path_of("khong-phai-id"))

    assert response.status_code == 404
    assert response.json()["resource"] == "trainingJob"
