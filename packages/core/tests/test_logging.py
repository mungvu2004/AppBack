import asyncio
import base64
import io
import json
import logging
from collections.abc import Iterator

import pytest

from packages.core.logging import (
    MASK,
    JsonFormatter,
    bind_log_context,
    configure_logging,
    mask,
    request_id_var,
)
from packages.core.settings import CoreSettings

SENSITIVE = "hunter2-do-not-leak"


def _b64(data: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


# Dựng lúc chạy: literal dạng JWT trong mã test làm gitleaks của CI báo động.
JWT = f"{_b64({'alg': 'HS256', 'typ': 'JWT'})}.{_b64({'sub': 'usr_x', 'aud': 'access'})}.c2lnbmF0dXJl"


@pytest.fixture
def capture() -> Iterator[tuple[logging.Logger, io.StringIO]]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test.core.logging")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    yield logger, stream
    logger.removeHandler(handler)


def _records(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


MASKED_KEYS = [
    "password",
    "newPassword",
    "currentPassword",
    "token",
    "accessToken",
    "refreshToken",
    "authorization",
    "cookie",
    "set-cookie",
    "confirmEmail",
    "chunk",
    "contentBase64",
    # biến thể hoa thường và `-`/`_`
    "Set-Cookie",
    "set_cookie",
    "SETCOOKIE",
    "new_password",
    "Authorization",
    "ACCESS-TOKEN",
    "content_base64",
]


@pytest.mark.parametrize("key", MASKED_KEYS)
def test_mask_masks_key(key: str) -> None:
    assert mask({key: SENSITIVE, "email": "a@b.vn"}) == {key: MASK, "email": "a@b.vn"}


@pytest.mark.parametrize("key", ["tokenCount", "passwordPolicy", "cookies", "email", "chunkIndex"])
def test_mask_keeps_other_keys(key: str) -> None:
    assert mask({key: "visible"}) == {key: "visible"}


def test_mask_masks_container_values_under_masked_key() -> None:
    assert mask({"cookie": {"appback_refresh": SENSITIVE}, "chunk": [SENSITIVE]}) == {"cookie": MASK, "chunk": MASK}


def test_mask_nested_three_levels() -> None:
    data = {"a": [{"b": ({"password": SENSITIVE, "ok": 1}, "x")}], "n": None}
    assert mask(data) == {"a": [{"b": ({"password": MASK, "ok": 1}, "x")}], "n": None}


def test_mask_keeps_scalars() -> None:
    assert [mask(v) for v in (None, True, 3, 1.5)] == [None, True, 3, 1.5]


def test_mask_stringifies_unknown_objects() -> None:
    class Header:
        def __str__(self) -> str:
            return f"Bearer {SENSITIVE}"

    assert mask(Header()) == f"Bearer {MASK}"
    assert mask({1: "x"}) == {1: "x"}


def test_mask_jwt_in_string() -> None:
    assert mask(f"token là {JWT} nhé") == f"token là {MASK} nhé"


def test_mask_bearer_case_insensitive() -> None:
    assert mask(f"Authorization: bearer {SENSITIVE}") == f"Authorization: bearer {MASK}"


def test_mask_presigned_s3_url() -> None:
    url = (
        "https://s3.example.vn/bucket/plan.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256"
        "&X-Amz-Credential=minio%2F20260101%2Fus-east-1%2Fs3%2Faws4_request"
        "&X-Amz-Date=20260101T000000Z&X-Amz-Signature=0a1b2c3d4e5f&x=1"
    )
    masked = str(mask(url))
    assert "X-Amz-Credential=***&" in masked
    assert "X-Amz-Signature=***&x=1" in masked
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in masked
    assert "minio%2F" not in masked
    assert "0a1b2c3d4e5f" not in masked


def test_mask_token_query_param() -> None:
    assert mask(f"/api/files/x?token={SENSITIVE}#top") == f"/api/files/x?token={MASK}#top"


def test_mask_truncates_long_string() -> None:
    masked = str(mask("x" * 5000))
    assert masked.startswith("x" * 2000)
    assert "x" * 2001 not in masked
    assert "5000" in masked
    assert len(masked) < 2100


def test_record_fields(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture
    token = request_id_var.set("req-12345678")
    try:
        logger.warning("xin chào %s", "Ánh", extra={"projectId": "prj_1", "level": "giả"})
    finally:
        request_id_var.reset(token)
    [record] = _records(stream)
    assert record["msg"] == "xin chào Ánh"
    assert record["level"] == "WARNING"
    assert record["logger"] == "test.core.logging"
    assert record["requestId"] == "req-12345678"
    assert record["projectId"] == "prj_1"
    assert str(record["ts"]).endswith("Z")
    assert len(str(record["ts"])) == len("2026-01-01T00:00:00.000Z")
    assert "excType" not in record


def test_request_id_absent_is_null(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture
    logger.info("không có request")
    assert _records(stream)[0]["requestId"] is None


def test_jwt_in_msg_masked(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture
    logger.info("đăng nhập với %s", JWT)
    logger.info(f"đăng nhập với {JWT}")  # chuỗi đã ghép sẵn cũng bị che
    raw = stream.getvalue()
    assert JWT not in raw
    assert all(r["msg"] == f"đăng nhập với {MASK}" for r in _records(stream))


def test_msg_args_masked_before_formatting(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture
    logger.info("thân %s", {"password": SENSITIVE})
    logger.info("thân %(password)s", {"password": SENSITIVE})
    logger.info({"token": SENSITIVE})
    assert SENSITIVE not in stream.getvalue()
    assert [r["msg"] for r in _records(stream)] == [
        f"thân {{'password': '{MASK}'}}",
        f"thân {MASK}",
        f"{{'token': '{MASK}'}}",
    ]


def test_extra_fields_masked(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture
    logger.info("request", extra={"headers": {"Authorization": f"Bearer {SENSITIVE}", "Cookie": SENSITIVE}})
    assert SENSITIVE not in stream.getvalue()
    assert _records(stream)[0]["headers"] == {"Authorization": MASK, "Cookie": MASK}


def test_exception_has_stack_without_masked_values(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture

    def login(password: str) -> None:
        raise RuntimeError(f"hỏng khi kiểm token {JWT}")

    try:
        login(SENSITIVE)
    except RuntimeError:
        logger.exception("đăng nhập hỏng", extra={"password": SENSITIVE})
    raw = stream.getvalue()
    [record] = _records(stream)
    assert record["excType"] == "RuntimeError"
    assert "Traceback" in str(record["stack"])
    assert "RuntimeError: hỏng khi kiểm token ***" in str(record["stack"])
    assert record["password"] == MASK
    assert SENSITIVE not in raw
    assert JWT not in raw


def test_exception_logged_outside_except(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture
    logger.exception("không có ngoại lệ")
    assert "excType" not in _records(stream)[0]


def test_long_stack_not_truncated(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture
    try:
        raise ValueError("y" * 3000)
    except ValueError:
        logger.exception("dài")
    assert "y" * 3000 in str(_records(stream)[0]["stack"])


async def test_request_id_isolated_between_tasks(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture

    async def handle(request_id: str) -> None:
        request_id_var.set(request_id)
        bind_log_context(user=request_id)
        await asyncio.sleep(0)
        logger.info("bắt đầu")
        await asyncio.sleep(0)
        logger.info("xong")

    await asyncio.gather(handle("req-aaaaaaaa"), handle("req-bbbbbbbb"))
    records = _records(stream)
    assert len(records) == 4
    assert {r["requestId"] for r in records} == {"req-aaaaaaaa", "req-bbbbbbbb"}
    assert all(r["requestId"] == r["user"] for r in records)
    assert request_id_var.get() is None


def test_bind_log_context_accumulates_and_resets(capture: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = capture
    first = bind_log_context(jobId="job_1")
    second = bind_log_context(step="preprocess", token=SENSITIVE)
    logger.info("a")
    second.var.reset(second)
    first.var.reset(first)
    logger.info("b")
    a, b = _records(stream)
    assert (a["jobId"], a["step"], a["token"]) == ("job_1", "preprocess", MASK)
    assert "jobId" not in b


@pytest.fixture
def root_logger() -> Iterator[logging.Logger]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield root
    root.handlers[:] = handlers
    root.setLevel(level)


def _settings(*, log_json: bool) -> CoreSettings:
    return CoreSettings(
        app_env="test",
        public_base_url="https://appback.test",
        secret_key="k" * 32,
        log_level="DEBUG",
        log_json=log_json,
    )


def test_configure_logging_json(root_logger: logging.Logger, capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_settings(log_json=True))
    configure_logging(_settings(log_json=True))  # gọi lại không nhân đôi handler
    assert len(root_logger.handlers) == 1
    assert root_logger.level == logging.DEBUG
    logging.getLogger("app.test").debug("x %s", {"password": SENSITIVE})
    err = capsys.readouterr().err
    assert json.loads(err)["msg"] == f"x {{'password': '{MASK}'}}"


def test_configure_logging_text(root_logger: logging.Logger, capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_settings(log_json=False))
    log = logging.getLogger("app.test")
    log.info("xin chào", extra={"token": SENSITIVE})
    try:
        raise KeyError("k")
    except KeyError:
        log.exception("hỏng")
    lines = capsys.readouterr().err.splitlines()
    assert lines[0].endswith(f'INFO app.test xin chào {{"token": "{MASK}", "requestId": null}}')
    assert " ERROR app.test hỏng " in lines[1]
    assert lines[2] == "Traceback (most recent call last):"
    assert SENSITIVE not in "\n".join(lines)
