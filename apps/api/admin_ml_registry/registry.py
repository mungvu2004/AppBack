"""Hàm registry cho worker: bản nào đang kích hoạt, ghi kết quả đánh giá (B6-01 [2], BE-00 §7).

`apps/worker` và `apps/ml` nhập module này, nên nó chỉ được nhập `packages.*` — không
`fastapi`, `starlette`, `jwt`, `argon2`, và không nhập `schemas.py` (thứ kéo theo
`apps.api.core`). Mọi hàm nhận `db` và **không** commit: người gọi (route hay task) sở hữu
giao dịch.

Task đánh giá luôn gửi **sau** commit (`on_after_commit`, K17): worker `ml` đọc bản trong DB
ngay khi nhận thông điệp, nên gửi trong giao dịch là gửi một id chưa tồn tại.
"""

import re
from typing import Final, cast

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import Clock
from packages.core.ids import check_id
from packages.core.object_keys import model_prefix
from packages.core.text import nfc
from packages.db.hooks import on_after_commit
from packages.db.models.admin_ml_registry import (
    CREATOR_MAX,
    ERROR_CODE_PATTERN,
    LABEL_MAX,
    SHA256_PATTERN,
    WEIGHTS_FORMATS,
    ModelFamilyRow,
    ModelVersionRow,
)
from packages.messaging import send_task
from packages.ml_contracts.families import FAMILY_METRIC, MODEL_FAMILIES, TRAINABLE_FAMILIES, ModelFamily
from packages.ml_contracts.payloads import EvaluateVersionPayload, ModelRef, check_metrics
from packages.storage.keys import model_artifact

EVALUATE_TASK: Final = "ml.infer.ml_eval.evaluate_version"
"""Tên task đánh giá (B6-04b chạy); tiền tố `ml.infer` chọn hàng đợi (BE-00 §7)."""

TRANSIENT_ERROR_CODES: Final = frozenset({"RETRY_EXHAUSTED", "DEPENDENCY_UNAVAILABLE"})
"""Mã `failed` tạm: việc của lịch gửi lại, `set_evaluation` không ghi chúng."""

_SETTABLE: Final = frozenset({"running", "completed", "failed"})
_OPEN: Final = ("pending", "running")
_SHA256: Final = re.compile(SHA256_PATTERN)
_ERROR_CODE: Final = re.compile(ERROR_CODE_PATTERN)


def _classic_ref(family: ModelFamily) -> ModelRef:
    """`ModelRef` dạng cổ điển: họ chưa kích hoạt bản nào (đường lùi của pipeline)."""
    return ModelRef(version_id=None, family=family, weights_key=None, pinned_name=None, checksum_sha256="")


async def _locked(db: AsyncSession, version_id: str) -> ModelVersionRow | None:
    """Bản `version_id` dưới `FOR UPDATE`, đọc lại từ DB (không tin identity map)."""
    stmt = select(ModelVersionRow).where(ModelVersionRow.id == version_id).with_for_update()
    return (await db.execute(stmt.execution_options(populate_existing=True))).scalar_one_or_none()


def model_ref_of(row: ModelVersionRow) -> ModelRef:
    """`ModelRef` của một bản đã có trọng số — dạng **ghim** hay dạng **storage**.

    CHECK `weights_location` của bảng bảo đảm đúng một trong `pinned_name`, `weights_key` có
    giá trị, nên không dòng nào ra được dạng "cổ điển" (dạng ấy chỉ dùng cho họ chưa kích
    hoạt bản nào, xem `active_versions`). `ModelRef` tự kiểm bản ghim có ONNX cùng họ và
    `weights_key` nằm dưới `ml/models/{id}/`, nên dòng DB hỏng thành `ValueError` tại đây.
    """
    return ModelRef(
        version_id=row.id,
        family=cast("ModelFamily", row.family),
        weights_key=row.weights_key,
        pinned_name=row.pinned_name,
        checksum_sha256=row.checksum_sha256,
    )


def enqueue_evaluation(db: AsyncSession, row: ModelVersionRow) -> None:
    """Đăng ký gửi `ml_eval.evaluate_version` cho `row` sau khi giao dịch của `db` commit.

    Dùng chung cho N26 (bản vừa tải lên) và `request_evaluation` (lịch gửi lại), để chỉ có
    **một** chỗ dựng payload: hai chỗ dựng riêng là hai cách sai khác nhau khi `ModelRef` đổi.
    `send_task` chạy ngoài giao dịch nên broker hỏng không làm mất dòng đã ghi (J02).
    """
    payload = EvaluateVersionPayload(version_id=row.id, model=model_ref_of(row))
    on_after_commit(db, lambda: send_task(EVALUATE_TASK, payload))


async def active_versions(db: AsyncSession) -> dict[ModelFamily, ModelRef]:
    """Bản đang kích hoạt của **đủ ba** họ; họ chưa kích hoạt → `ModelRef` dạng cổ điển.

    Một truy vấn `model_families LEFT JOIN model_versions`: pipeline ghim model ở đầu lượt
    chạy (BE-00 §9) nên không được N lượt đọc theo bước.
    """
    stmt = select(ModelFamilyRow.family, ModelVersionRow).outerjoin(
        ModelVersionRow, ModelFamilyRow.active_version_id == ModelVersionRow.id
    )
    refs = {family: _classic_ref(family) for family in MODEL_FAMILIES}
    for family, version in (await db.execute(stmt)).all():
        if version is not None:
            refs[cast("ModelFamily", family)] = model_ref_of(version)
    return refs


async def register_trained_version(
    db: AsyncSession,
    *,
    version_id: str,
    family: str,
    label: str,
    weights_key: str,
    weights_format: str,
    checksum_sha256: str,
    training_job_id: str,
    dataset_version_id: str,
    creator_id: str,
    clock: Clock,
) -> str:
    """Ghi bản do job huấn luyện sinh; trả id bản (id cũ nếu đã ghi rồi, J06).

    Tham số sai luật (id sai tiền tố, `weights_key` ngoài `ml/models/{version_id}/`, họ không
    huấn luyện được, định dạng, checksum, nhãn) → `ValueError`: người gọi là task của chính
    repo, không phải người dùng, nên đây là lỗi lập trình chứ không phải 422.

    Không có "đọc rồi chèn": `INSERT … ON CONFLICT DO NOTHING` (PK và unique một phần
    `training_job_id`) để hai lượt chạy song song không tạo hai dòng, cũng không bắt
    `IntegrityError`; lượt thua chờ lượt thắng commit rồi đọc lại dòng để phân xử.
    """
    clean_label = _check_registration(
        version_id=version_id,
        family=family,
        label=label,
        weights_key=weights_key,
        weights_format=weights_format,
        checksum_sha256=checksum_sha256,
        training_job_id=training_job_id,
        dataset_version_id=dataset_version_id,
        creator_id=creator_id,
    )
    now = clock.now()
    insert_stmt = (
        insert(ModelVersionRow)
        .values(
            id=version_id,
            family=family,
            label=clean_label,
            weights_format=weights_format,
            checksum_sha256=checksum_sha256,
            weights_key=weights_key,
            training_job_id=training_job_id,
            dataset_version_id=dataset_version_id,
            evaluation_status="pending",
            evaluation_attempts=0,
            creator_id=creator_id,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing()
        .returning(ModelVersionRow.id)
    )
    if (await db.execute(insert_stmt)).scalar_one_or_none() is None:
        await _resolve_conflict(db, version_id=version_id, training_job_id=training_job_id)
    return version_id


def clean_label(value: str) -> str:
    """`nfc(strip)` rồi kiểm 1-`LABEL_MAX` ký tự; khoảng trắng hai đầu không tính là nhãn.

    Sống ở đây chứ không ở `schemas.py` vì `registry.py` bị `apps/worker` nhập và không được
    nhập `schemas.py` (nó kéo theo `apps.api.core`): `register_trained_version` và validator
    `Label` của dây phải dùng **một** bộ luật, hai bản chép là hai cách lệch nhau.
    """
    cleaned = nfc(value.strip())
    if not 1 <= len(cleaned) <= LABEL_MAX:
        raise ValueError(f"label phải có 1-{LABEL_MAX} ký tự sau khi bỏ khoảng trắng hai đầu")
    return cleaned


def _check_registration(
    *,
    version_id: str,
    family: str,
    label: str,
    weights_key: str,
    weights_format: str,
    checksum_sha256: str,
    training_job_id: str,
    dataset_version_id: str,
    creator_id: str,
) -> str:
    """Kiểm tham số của `register_trained_version`; trả nhãn đã `nfc(strip)`. Sai → `ValueError`."""
    check_id("mdl", version_id)
    check_id("job", training_job_id)
    check_id("dsv", dataset_version_id)
    if family not in TRAINABLE_FAMILIES:
        raise ValueError(f"họ không huấn luyện được: {family!r}")
    if weights_format not in WEIGHTS_FORMATS:
        raise ValueError(f"định dạng trọng số lạ: {weights_format!r}")
    if _SHA256.fullmatch(checksum_sha256) is None:
        raise ValueError("checksum_sha256 phải là 64 ký tự hex thường")
    prefix = model_prefix(version_id)
    if not weights_key.startswith(prefix) or model_artifact(version_id, weights_key[len(prefix) :]) != weights_key:
        raise ValueError(f"weights_key phải nằm dưới {prefix}: {weights_key!r}")
    if not 1 <= len(creator_id) <= CREATOR_MAX:
        raise ValueError(f"creator_id phải có 1-{CREATOR_MAX} ký tự")
    return clean_label(label)


async def _resolve_conflict(db: AsyncSession, *, version_id: str, training_job_id: str) -> None:
    """`INSERT` bị bỏ qua: cùng `version_id` **và** cùng job là lặp (J06), còn lại là `ValueError`."""
    stmt = select(ModelVersionRow.id, ModelVersionRow.training_job_id).where(
        or_(ModelVersionRow.id == version_id, ModelVersionRow.training_job_id == training_job_id)
    )
    if (version_id, training_job_id) not in {(row.id, row.training_job_id) for row in (await db.execute(stmt)).all()}:
        raise ValueError("version_id hoặc training_job_id đã thuộc một bản khác")


async def set_evaluation(
    db: AsyncSession,
    *,
    version_id: str,
    status: str,
    metrics: dict[str, float] | None,
    error_code: str | None,
    clock: Clock,
) -> bool:
    """Ghi kết quả đánh giá dưới khoá dòng; `True` khi có ghi, `False` khi bỏ qua.

    Bỏ qua khi: bản không có, bản đã `completed` (kết quả là bất biến, M06), hay `failed` mang
    mã tạm (`RETRY_EXHAUSTED`, `DEPENDENCY_UNAVAILABLE`) — mã tạm là việc của lịch gửi lại,
    không phải trạng thái cuối. `metrics` sai khoá hay ngoài dải → `ValueError`.

    Bản `failed` nhận `completed` (object bất biến, M06) nhưng không nhận `running` — một
    thông điệp cũ tới muộn không được kéo bản đã chốt lỗi về "đang chạy".
    """
    if status not in _SETTABLE:
        raise ValueError(f"trạng thái đánh giá không ghi được: {status!r}")
    if error_code is not None and (status != "failed" or _ERROR_CODE.fullmatch(error_code) is None):
        raise ValueError(f"mã lỗi đánh giá sai: {error_code!r}")
    row = await _locked(db, version_id)
    if row is None or row.evaluation_status == "completed":
        return False
    if status == "failed" and error_code in TRANSIENT_ERROR_CODES:
        return False
    if status == "running" and row.evaluation_status == "failed":
        return False
    if status == "completed":
        _check_family_metrics(cast("ModelFamily", row.family), metrics)
    row.evaluation_status = status
    row.evaluation_error_code = error_code
    row.metrics = dict(metrics) if status == "completed" and metrics is not None else None
    row.updated_at = clock.now()
    await db.flush()
    return True


def _check_family_metrics(family: ModelFamily, metrics: dict[str, float] | None) -> None:
    """`completed` cần đúng một số đo, đúng khoá của họ, trong dải; sai → `ValueError`."""
    if metrics is None:
        raise ValueError("completed cần metrics")
    check_metrics(metrics)
    if set(metrics) != {FAMILY_METRIC[family]}:
        raise ValueError(f"họ {family} chỉ có số đo {FAMILY_METRIC[family]}")


async def request_evaluation(db: AsyncSession, *, version_id: str, clock: Clock) -> bool:
    """Xin đánh giá lại một bản `pending|running`: `attempts + 1`, `requested_at = now`.

    Đăng ký gửi task sau commit qua `enqueue_evaluation`. Bản không có, hay đã `completed`
    hoặc `failed` → `False`, không ghi và không gửi gì.
    """
    row = await _locked(db, version_id)
    if row is None or row.evaluation_status not in _OPEN:
        return False
    now = clock.now()
    row.evaluation_attempts += 1
    row.evaluation_requested_at = now
    row.updated_at = now
    await db.flush()
    enqueue_evaluation(db, row)
    return True
