"""Lõi `ingest()` gọi thẳng, không qua route (B7-01 [6], [8]).

Case chung của route (#9/#37) không lo tới đây; đây là những nhánh mà chỉ gọi lõi
mới thử được trong trần thời gian hợp lý: 2.000 lô cho `series_dropped_total`, 1.000
lô cho xô token log — cả hai đều cần hàng nghìn lượt gọi, quá chậm nếu đi qua ASGI.
"""

import json
import logging
import random
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from apps.api.telemetry import ingest as ingest_module
from apps.api.telemetry.ingest import ERROR_KINDS, EVENT_NAMES, ingest, reset_log_bucket
from apps.api.telemetry.settings import get_telemetry_settings, reset_telemetry_settings_cache
from packages.core.error_codes import MALFORMED_JSON, VALIDATION
from packages.core.errors import AppError
from packages.observability.metrics import render, reset_registry

_TS_ARRAY_RE = re.compile(r"export const (\w+) = \[(.*?)\] as const", re.DOTALL)


def _read_ts_array(path: Path, name: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    for match_name, block in _TS_ARRAY_RE.findall(text):
        if match_name == name:
            return re.findall(r"'([^']*)'", block)
    pytest.fail(f"không tìm thấy khối 'export const {name} = [...] as const' trong {path}")


def test_event_names_mirror_appfront(appfront_dir: Path) -> None:
    fe_names = _read_ts_array(appfront_dir / "src/lib/telemetry/events.ts", "TELEMETRY_EVENT_NAMES")
    assert len(fe_names) == 12
    assert set(fe_names) == EVENT_NAMES


def test_error_kinds_mirror_appfront(appfront_dir: Path) -> None:
    fe_kinds = _read_ts_array(appfront_dir / "src/lib/errors/kinds.ts", "APP_ERROR_KINDS")
    assert len(fe_kinds) == 13
    assert set(fe_kinds) == ERROR_KINDS


def _batch(**overrides: object) -> bytes:
    body = {
        "schemaVersion": 1,
        "sessionId": "sess-abc123",
        "sentAtMs": 1_700_000_000_000,
        "reason": "manual",
        "events": [],
        "droppedCount": 0,
        **overrides,
    }
    return json.dumps(body).encode("utf-8")


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    reset_registry()
    reset_log_bucket()
    yield
    reset_telemetry_settings_cache()
    reset_registry()


def test_accepted_batch_is_silent() -> None:
    ingest(_batch(), "application/json")


def test_text_plain_with_json_body_is_accepted() -> None:
    """Beacon lùi gửi `text/plain` chứa JSON."""
    ingest(_batch(), "text/plain; charset=UTF-8")


def test_missing_content_type_is_accepted() -> None:
    ingest(_batch(), None)


def test_unsupported_content_type_is_422() -> None:
    with pytest.raises(AppError) as excinfo:
        ingest(_batch(), "application/xml")
    assert excinfo.value.code is VALIDATION


def test_malformed_json_is_400() -> None:
    with pytest.raises(AppError) as excinfo:
        ingest(b"[" * 40_000, "application/json")
    assert excinfo.value.code is MALFORMED_JSON


def test_non_utf8_body_is_400() -> None:
    with pytest.raises(AppError) as excinfo:
        ingest(b"\xff\xfe\x00\x01", "application/json")
    assert excinfo.value.code is MALFORMED_JSON


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"schemaVersion": 2}, "schemaVersion"),
        ({"sessionId": "SESS-CAPS"}, "sessionId"),
        ({"sessionId": ""}, "sessionId"),
        ({"sentAtMs": -1}, "sentAtMs"),
        ({"sentAtMs": True}, "sentAtMs"),
        ({"reason": "unknown-reason"}, "reason"),
        ({"events": [{}] * 21}, "events"),
        ({"events": "not-a-list"}, "events"),
        ({"droppedCount": -1}, "droppedCount"),
        ({"droppedCount": 1_000_001}, "droppedCount"),
        ({"droppedCount": True}, "droppedCount"),
    ],
    ids=[
        "schema-version",
        "session-id-hoa",
        "session-id-rong",
        "sent-at-am",
        "sent-at-bool",
        "reason-la",
        "events-qua-21",
        "events-khong-phai-mang",
        "dropped-am",
        "dropped-qua-tran",
        "dropped-bool",
    ],
)
def test_envelope_violations_are_422_with_field(overrides: dict[str, object], field: str) -> None:
    with pytest.raises(AppError) as excinfo:
        ingest(_batch(**overrides), "application/json")
    assert excinfo.value.code is VALIDATION
    assert excinfo.value.params["field"] == field


def test_unknown_top_level_keys_are_ignored() -> None:
    ingest(_batch(**{"extra": "bo qua"}), "application/json")


def test_rejected_batch_with_valid_reason_uses_that_label() -> None:
    with pytest.raises(AppError):
        ingest(_batch(sessionId="BAD"), "application/json")
    assert 'appback_telemetry_batches_total{reason="manual",result="rejected"} 1.0' in render()


def test_rejected_batch_with_invalid_reason_uses_invalid_label() -> None:
    with pytest.raises(AppError):
        ingest(_batch(reason="bogus"), "application/json")
    assert 'appback_telemetry_batches_total{reason="invalid",result="rejected"} 1.0' in render()


def test_accepted_batch_counts_result_accepted() -> None:
    ingest(_batch(reason="size"), "application/json")
    assert 'appback_telemetry_batches_total{reason="size",result="accepted"} 1.0' in render()


def test_real_frontend_batch_is_accepted_and_counted() -> None:
    """C01 #37: 3 sự kiện hợp lệ, `droppedCount: 2`."""
    events = [
        {"sequence": 0, "atMs": 1, "event": {"name": "ai.started", "screen": "viewer"}},
        {"sequence": 1, "atMs": 2, "event": {"name": "ai.finished", "durationMs": 120.6}},
        {"sequence": 2, "atMs": 3, "event": {"name": "wall.edit"}},
    ]
    ingest(_batch(events=events, droppedCount=2), "application/json")
    text = render()
    assert 'appback_telemetry_events_total{name="ai.started"} 1.0' in text
    assert "appback_telemetry_client_dropped_total 2.0" in text


def test_malformed_item_is_dropped_and_counted() -> None:
    events = [
        "not-a-dict",
        {"sequence": True, "atMs": 1, "event": {"name": "ai.started"}},
        {"sequence": 1, "atMs": 1},
        {"sequence": 1, "atMs": 1, "event": "not-a-dict"},
    ]
    ingest(_batch(events=events), "application/json")
    assert 'appback_telemetry_events_dropped_total{cause="malformed"} 4.0' in render()


def test_unknown_event_name_is_dropped_and_does_not_create_series() -> None:
    events = [{"sequence": 0, "atMs": 0, "event": {"name": "totally.unknown"}}]
    ingest(_batch(events=events), "application/json")
    text = render()
    assert 'appback_telemetry_events_dropped_total{cause="unknown_name"} 1.0' in text
    assert 'name="totally.unknown"' not in text


def test_error_kind_field_accepts_only_the_thirteen_values() -> None:
    events = [
        {"sequence": 0, "atMs": 0, "event": {"name": "screen.error", "errorKind": "notFound"}},
        {"sequence": 1, "atMs": 0, "event": {"name": "screen.error", "errorKind": "rateLimited"}},
        {"sequence": 2, "atMs": 0, "event": {"name": "screen.error", "errorKind": "RateLimited"}},
    ]
    ingest(_batch(events=events), "application/json")
    assert 'appback_telemetry_events_total{name="screen.error"} 3.0' in render()


def test_fields_with_personal_data_are_dropped_and_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    events = [
        {
            "sequence": 0,
            "atMs": 0,
            "event": {
                "name": "wall.edit",
                "fileName": "Bản vẽ nhà anh Ba.pdf",
                "email": "nguoi@example.com",
                "negative": -1,
                "tooBig": 1e9,
                "array": [1, 2, 3],
                "okCode": "wall-01",
                "okFlag": True,
                "durationMs": 250.4,
            },
        }
    ]
    with caplog.at_level(logging.INFO, logger="apps.api.telemetry.ingest"):
        ingest(_batch(events=events), "application/json")
    joined = " ".join(record.getMessage() + str(record.__dict__) for record in caplog.records)
    assert "Bản vẽ nhà anh Ba.pdf" not in joined
    assert "nguoi@example.com" not in joined
    assert "appback_telemetry_duration_ms" in render()


def test_fields_beyond_the_cap_are_dropped_in_order() -> None:
    event: dict[str, object] = {"name": "wall.edit", "a": "x", "b": "y", "c": "z"}
    kept = ingest_module._sanitize_fields(event, 2)
    assert kept == {"a": "x", "b": "y"}


def test_content_type_field_before_body_is_read() -> None:
    with pytest.raises(AppError) as excinfo:
        ingest(b"", "application/xml")
    assert excinfo.value.params["field"] == "contentType"


def test_two_thousand_batches_do_not_drop_batches_series() -> None:
    """2.000 lô `reason` ngẫu nhiên → `series_dropped_total` 0 (4 giá trị `reason` x 2 `result`)."""
    rng = random.Random(7)  # noqa: S311
    for _ in range(2_000):
        reason = rng.choice(["size", "interval", "manual", "close"])
        if rng.random() < 0.5:
            ingest(_batch(reason=reason), "application/json")
        else:
            with pytest.raises(AppError):
                ingest(_batch(reason=reason, sessionId="BAD"), "application/json")
    assert 'appback_metrics_series_dropped_total{metric="appback_telemetry_batches_total"}' not in render()


def test_one_thousand_batches_respect_the_log_rate_limit(caplog: pytest.LogCaptureFixture) -> None:
    """1.000 lô x 20 sự kiện: dòng log ≤ `TELEMETRY_LOG_MAX_PER_MIN`, `log_suppressed_total` > 0."""
    events = [{"sequence": i, "atMs": i, "event": {"name": "wall.edit"}} for i in range(20)]
    body = _batch(events=events)
    with caplog.at_level(logging.INFO, logger="apps.api.telemetry.ingest"):
        for _ in range(1_000):
            ingest(body, "application/json")
    batch_logs = [r for r in caplog.records if r.getMessage() == "telemetry_batch"]
    limit = get_telemetry_settings().telemetry_log_max_per_min
    assert len(batch_logs) <= limit
    match = re.search(r"appback_telemetry_log_suppressed_total (\d+\.\d+)", render())
    assert match is not None
    assert float(match.group(1)) > 0
