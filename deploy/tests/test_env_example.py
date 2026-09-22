"""Test tĩnh cho `deploy/compose/env.example` (prompt [2]/[8])."""

from __future__ import annotations

import re

from deploy.tests.support import require_path

# Nguyên văn danh sách biến của prompt B0-08 [2] — nguồn đúng sai duy nhất.
_REQUIRED_VARS = (
    "APP_ENV",
    "PUBLIC_BASE_URL",
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_BROKER_URL",
    "REDIS_CACHE_URL",
    "STORAGE_BACKEND",
    "S3_ENDPOINT",
    "S3_PUBLIC_ENDPOINT",
    "S3_BUCKET",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "S3_REGION",
    "S3_ML_ACCESS_KEY",
    "S3_ML_SECRET_KEY",
    "SMTP_URL",
    "FORWARDED_ALLOW_IPS",
    "ML_DEVICE",
    "IMAGE_REGISTRY",
    "IMAGE_TAG",
    "WORKER_CONCURRENCY",
    "WORKER_MEM_LIMIT",
    "ML_MEM_LIMIT",
)

_PLACEHOLDER_VALUES = {"", "change-me", "changeme", "CHANGE_ME"}
_SECRET_LOOKING_RE = re.compile(r"[A-Za-z0-9+/_-]{20,}")
_AWS_KEY_RE = re.compile(r"AKIA[0-9A-Z]{16}")


def _load_env_lines() -> dict[str, str]:
    """Nạp `env.example` thành `{tên: giá trị}`, bỏ dòng trống/comment (`#`)."""
    path = require_path("deploy/compose/env.example")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition("=")
        assert sep, f"env.example: dòng {line!r} không đúng dạng KEY=VALUE"
        values[key.strip()] = value.strip()
    return values


def test_env_example_has_every_required_variable() -> None:
    """Đủ mọi biến ở prompt [2] — thiếu một biến là hỏng bước 5."""
    values = _load_env_lines()
    missing = [name for name in _REQUIRED_VARS if name not in values]
    assert not missing, f"env.example thiếu biến: {missing}"


def test_env_example_no_value_looks_like_a_real_secret() -> None:
    """Không giá trị nào trông như bí mật thật: chuỗi base64/hex liên tục ≥ 20 ký tự,
    khoá AWS `AKIA…`, khối `-----BEGIN`; giữ chỗ (`change-me`, rỗng, hay `change-me-…`
    có hậu tố mô tả như `change-me-32-bytes-minimum-please`) và đường dẫn tuyệt đối
    (`/var/lib/...`, không phải bí mật) thì được (K cấm bí mật trong `env.example`)."""
    values = _load_env_lines()
    for name, raw in values.items():
        value = raw.strip("\"'")
        if value in _PLACEHOLDER_VALUES or value.lower().startswith("change-me") or value.startswith("/"):
            continue
        assert "-----BEGIN" not in value, f"{name}: chứa khối khoá PEM"
        assert not _AWS_KEY_RE.search(value), f"{name}: trông như AWS access key id thật"
        long_run = _SECRET_LOOKING_RE.search(value)
        assert not long_run, f"{name}: giá trị {value!r} trông như bí mật thật (chuỗi dài liên tục)"


_APP_ENV_ADDED_VARS = (
    "CELERY_VISIBILITY_TIMEOUT_S",
    "TASK_TIME_LIMIT_S",
    "TASK_SOFT_TIME_LIMIT_S",
    "TASK_RETRY_BACKOFF_S",
    "STREAM_MAXLEN",
)


def test_env_example_has_celery_task_stream_vars_from_app_env() -> None:
    """NO-021 phần còn lại (review 2026-09-22 #10): các biến tinh chỉnh Celery/task/
    stream đi qua `&app-env` (`base.yml`) phải khai ở đây kèm comment, đúng mặc định
    của `packages/messaging/settings.py`."""
    raw = require_path("deploy/compose/env.example").read_text(encoding="utf-8")
    assert "# --- Celery" in raw, "env.example: thiếu comment cho nhóm biến Celery/task/stream"
    values = _load_env_lines()
    missing = [name for name in _APP_ENV_ADDED_VARS if name not in values]
    assert not missing, f"env.example thiếu biến: {missing}"
    assert values["CELERY_VISIBILITY_TIMEOUT_S"] == "7200"
    assert values["TASK_TIME_LIMIT_S"] == "3600"
    assert values["TASK_SOFT_TIME_LIMIT_S"] == "3300"
    assert values["TASK_RETRY_BACKOFF_S"] == "10,60,300"
    assert values["STREAM_MAXLEN"] == "1000"


_DISTINCT_SECRET_VARS = (
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "S3_ML_ACCESS_KEY",
    "S3_ML_SECRET_KEY",
    "POSTGRES_PASSWORD",
    "SECRET_KEY",
)


def test_env_example_secrets_use_distinct_placeholders() -> None:
    """Mọi khoá/mật khẩu có placeholder RIÊNG (review 2026-09-22 #15, OPS-02 ·
    R-34): sao `env.example` nguyên xi trước đây làm `S3_ML_ACCESS_KEY` trùng
    `MINIO_ROOT_USER` (cùng `change-me`) → MinIO từ chối tạo user, `minio-init`
    thoát khác 0, `api`/`worker`/`ml` đứng chờ mãi (`service_completed_successfully`).
    Chỉ cấm bí mật thật (K), placeholder khác nhau vẫn là placeholder."""
    values = _load_env_lines()
    seen: dict[str, str] = {}
    for name in _DISTINCT_SECRET_VARS:
        value = values[name].strip("\"'")
        collision = seen.get(value)
        assert collision is None, f"{name} và {collision} dùng chung placeholder {value!r} — phải khác nhau"
        seen[value] = name


def test_env_example_worker_and_ml_default_sizes() -> None:
    """`WORKER_CONCURRENCY=2`, `WORKER_MEM_LIMIT=3g`, `ML_MEM_LIMIT=6g` (mặc định
    dùng lại trong `${…:-…}` của compose)."""
    values = _load_env_lines()
    assert values["WORKER_CONCURRENCY"].strip("\"'") == "2"
    assert values["WORKER_MEM_LIMIT"].strip("\"'") == "3g"
    assert values["ML_MEM_LIMIT"].strip("\"'") == "6g"
