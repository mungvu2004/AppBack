"""Metric của #9, #37 — khai một lần lúc nhập (B7-01 [5])."""

from typing import Final

from packages.observability.metrics import Counter, Histogram, counter, histogram

DURATION_BUCKETS_MS: Final = (10.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0, 30000.0, 86_400_000.0)

FEATURE_FLAGS_READS_TOTAL: Final[Counter] = counter(
    "appback_feature_flags_reads_total", help="Số lượt đọc GET /api/feature-flags"
)
TELEMETRY_BATCHES_TOTAL: Final[Counter] = counter(
    "appback_telemetry_batches_total",
    help="Số lô #37 nhận được, theo lý do gửi và kết quả",
    labels=("reason", "result"),
)
TELEMETRY_EVENTS_TOTAL: Final[Counter] = counter(
    "appback_telemetry_events_total", help="Số sự kiện chấp nhận, theo tên", labels=("name",)
)
TELEMETRY_EVENTS_DROPPED_TOTAL: Final[Counter] = counter(
    "appback_telemetry_events_dropped_total", help="Số mục sự kiện bị bỏ, theo lý do", labels=("cause",)
)
TELEMETRY_CLIENT_DROPPED_TOTAL: Final[Counter] = counter(
    "appback_telemetry_client_dropped_total", help="Số sự kiện client tự bỏ trước khi gửi (droppedCount)"
)
TELEMETRY_DURATION_MS: Final[Histogram] = histogram(
    "appback_telemetry_duration_ms",
    help="Phân bố durationMs/latencyMs, theo tên sự kiện",
    labels=("name",),
    buckets=DURATION_BUCKETS_MS,
)
TELEMETRY_LOG_SUPPRESSED_TOTAL: Final[Counter] = counter(
    "appback_telemetry_log_suppressed_total", help="Số dòng log telemetry_batch bị bỏ vì hết xô token mỗi phút"
)
