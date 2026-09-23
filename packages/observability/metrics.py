"""Registry metric kiểu Prometheus text 0.0.4 — thư viện chuẩn (BE-00 §11).

Không có `prometheus_client`: tên/nhãn, khai lại, hạn mức chuỗi nhãn và định dạng
`render()` tự viết, để `packages.observability` không kéo thư viện ngoài (BE-00 §13.1).
Một `threading.RLock` bọc mọi thay đổi registry — exporter (BE-00 §11) đọc `render()`
từ luồng nền của `ThreadingHTTPServer` trong khi request ghi metric từ luồng chính, và
`_bump_dropped` gọi lại chính registry nên khoá phải tái nhập được (không dùng `Lock`).
"""

import math
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Final

from packages.observability.settings import get_observability_settings

NAME_RE: Final = re.compile(r"^appback_[a-z][a-z0-9_]*$")
LABEL_RE: Final = re.compile(r"^[a-z][a-z0-9_]*$")
RESERVED_LABEL: Final = "le"
MAX_LABEL_VALUE_LEN: Final = 64

DEFAULT_BUCKETS: Final = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

_SERIES_DROPPED_NAME: Final = "appback_metrics_series_dropped_total"
_INF_LABEL: Final = "+Inf"


@dataclass(frozen=True, slots=True)
class _Def:
    kind: str
    help: str
    labels: tuple[str, ...]
    buckets: tuple[float, ...] = ()


@dataclass(slots=True)
class _HistState:
    bucket_counts: list[float]
    sum: float = 0.0
    count: float = 0.0


class _Registry:
    """Định nghĩa + mẫu của mọi metric của tiến trình; `reset_registry()` chỉ xoá mẫu."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.defs: dict[str, _Def] = {}
        self.counter_series: dict[str, dict[tuple[str, ...], float]] = {}
        self.hist_series: dict[str, dict[tuple[str, ...], _HistState]] = {}

    def define(
        self, name: str, *, kind: str, help_text: str, labels: tuple[str, ...], buckets: tuple[float, ...]
    ) -> None:
        """Khai một metric; khai lại cùng định nghĩa là no-op, khác định nghĩa là `ValueError`."""
        _validate_name(name, kind)
        for label in labels:
            _validate_label(label)
        with self.lock:
            existing = self.defs.get(name)
            new = _Def(kind=kind, help=help_text, labels=labels, buckets=buckets)
            if existing is not None:
                if existing != new:
                    raise ValueError(f"metric {name!r} đã khai với định nghĩa khác")
                return
            self.defs[name] = new
            self.counter_series[name] = {}
            self.hist_series[name] = {}

    def _require(self, name: str, kind: str) -> _Def:
        definition = self.defs.get(name)
        if definition is None or definition.kind != kind:
            raise ValueError(f"metric {kind} chưa khai: {name!r}")
        return definition

    def record_counter(self, name: str, amount: float, labels: dict[str, str]) -> None:
        """`Counter.inc`: cộng `amount` vào đúng tổ hợp nhãn, hoặc bỏ mẫu nếu vượt hạn mức."""
        definition = self._require(name, "counter")
        _validate_amount(amount)
        key = _label_key(definition.labels, labels)
        with self.lock:
            series = self.counter_series[name]
            if key not in series:
                if not self._admit(len(series)):
                    self._bump_dropped(name)
                    return
                series[key] = 0.0
            series[key] += amount

    def record_histogram(self, name: str, value: float, labels: dict[str, str]) -> None:
        """`Histogram.observe`: tích luỹ vào các `_bucket{le}` (kèm `+Inf`), `_sum`, `_count`."""
        definition = self._require(name, "histogram")
        _validate_amount(value)
        key = _label_key(definition.labels, labels)
        with self.lock:
            series = self.hist_series[name]
            state = series.get(key)
            if state is None:
                if not self._admit(len(series)):
                    self._bump_dropped(name)
                    return
                state = _HistState(bucket_counts=[0.0] * (len(definition.buckets) + 1))
                series[key] = state
            for i, bound in enumerate(definition.buckets):
                if value <= bound:
                    state.bucket_counts[i] += 1.0
            state.bucket_counts[-1] += 1.0
            state.sum += value
            state.count += 1.0

    def _admit(self, series_len: int) -> bool:
        return series_len < get_observability_settings().metrics_max_series

    def _bump_dropped(self, metric: str) -> None:
        self.record_counter(_SERIES_DROPPED_NAME, 1.0, {"metric": metric})

    def reset(self) -> None:
        """Đặt mọi mẫu về 0, giữ nguyên định nghĩa và tập tổ hợp nhãn đã thấy."""
        with self.lock:
            for counter_map in self.counter_series.values():
                for key in counter_map:
                    counter_map[key] = 0.0
            for hist_map in self.hist_series.values():
                for state in hist_map.values():
                    for i in range(len(state.bucket_counts)):
                        state.bucket_counts[i] = 0.0
                    state.sum = 0.0
                    state.count = 0.0

    def render(self) -> str:
        lines: list[str] = []
        with self.lock:
            for name in sorted(self.defs):
                definition = self.defs[name]
                lines.append(f"# HELP {name} {_escape(definition.help, quote=False)}")
                lines.append(f"# TYPE {name} {definition.kind}")
                if definition.kind == "counter":
                    lines.extend(self._render_counter(name, definition))
                else:
                    lines.extend(self._render_histogram(name, definition))
        return "\n".join(lines) + "\n"

    def _render_counter(self, name: str, definition: _Def) -> list[str]:
        return [
            f"{name}{_labels(definition.labels, key)} {value!r}"
            for key, value in sorted(self.counter_series[name].items())
        ]

    def _render_histogram(self, name: str, definition: _Def) -> list[str]:
        lines: list[str] = []
        for key, state in sorted(self.hist_series[name].items()):
            for bound, count in zip(definition.buckets, state.bucket_counts[:-1], strict=True):
                extra = (("le", repr(float(bound))),)
                lines.append(f"{name}_bucket{_labels(definition.labels, key, extra=extra)} {count!r}")
            extra_inf = (("le", _INF_LABEL),)
            lines.append(f"{name}_bucket{_labels(definition.labels, key, extra=extra_inf)} {state.bucket_counts[-1]!r}")
            lines.append(f"{name}_sum{_labels(definition.labels, key)} {state.sum!r}")
            lines.append(f"{name}_count{_labels(definition.labels, key)} {state.count!r}")
        return lines


def _validate_name(name: str, kind: str) -> None:
    if not NAME_RE.fullmatch(name):
        raise ValueError(f"tên metric sai mẫu {NAME_RE.pattern}: {name!r}")
    if kind == "counter" and not name.endswith("_total"):
        raise ValueError(f"counter phải kết thúc '_total': {name!r}")


def _validate_label(label: str) -> None:
    if not LABEL_RE.fullmatch(label):
        raise ValueError(f"nhãn sai mẫu {LABEL_RE.pattern}: {label!r}")
    if label == RESERVED_LABEL:
        raise ValueError("nhãn 'le' dành riêng cho bucket histogram")


def _validate_amount(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"giá trị phải là số: {value!r}")
    if math.isnan(value):
        raise ValueError("giá trị không được NaN")
    if value < 0:
        raise ValueError(f"giá trị phải ≥ 0: {value!r}")


def _label_key(names: tuple[str, ...], given: dict[str, str]) -> tuple[str, ...]:
    if set(given) != set(names):
        raise ValueError(f"nhãn không khớp: cần {names}, nhận {tuple(given)}")
    for value in given.values():
        if not isinstance(value, str) or len(value) > MAX_LABEL_VALUE_LEN:
            raise ValueError(f"giá trị nhãn sai (chuỗi ≤ {MAX_LABEL_VALUE_LEN} ký tự): {value!r}")
    return tuple(given[name] for name in names)


def _escape(value: str, *, quote: bool) -> str:
    out = value.replace("\\", "\\\\").replace("\n", "\\n")
    return out.replace('"', '\\"') if quote else out


def _labels(names: tuple[str, ...], values: tuple[str, ...], extra: tuple[tuple[str, str], ...] = ()) -> str:
    pairs = [*zip(names, values, strict=True), *extra]
    if not pairs:
        return ""
    body = ",".join(f'{n}="{_escape(v, quote=True)}"' for n, v in pairs)
    return "{" + body + "}"


_REGISTRY: Final = _Registry()
_REGISTRY.define(
    _SERIES_DROPPED_NAME,
    kind="counter",
    help_text="Số mẫu bị bỏ vì vượt METRICS_MAX_SERIES, theo metric",
    labels=("metric",),
    buckets=(),
)


@dataclass(frozen=True, slots=True)
class Counter:
    """Bộ đếm một chiều; `inc` không bao giờ giảm."""

    name: str
    _registry: _Registry = field(default=_REGISTRY, repr=False, compare=False)

    def inc(self, amount: float = 1, **labels: str) -> None:
        self._registry.record_counter(self.name, amount, labels)


@dataclass(frozen=True, slots=True)
class Histogram:
    """Phân bố giá trị theo bucket cố định lúc khai."""

    name: str
    _registry: _Registry = field(default=_REGISTRY, repr=False, compare=False)

    def observe(self, value: float, **labels: str) -> None:
        self._registry.record_histogram(self.name, value, labels)


def counter(name: str, *, help: str, labels: tuple[str, ...] = ()) -> Counter:
    """Khai (hay lấy lại) một counter; tên phải kết thúc `_total`."""
    _REGISTRY.define(name, kind="counter", help_text=help, labels=labels, buckets=())
    return Counter(name)


def histogram(
    name: str,
    *,
    help: str,
    labels: tuple[str, ...] = (),
    buckets: tuple[float, ...] = DEFAULT_BUCKETS,
) -> Histogram:
    """Khai (hay lấy lại) một histogram với bucket cố định."""
    _REGISTRY.define(name, kind="histogram", help_text=help, labels=labels, buckets=buckets)
    return Histogram(name)


def render() -> str:
    """Toàn bộ registry ở định dạng Prometheus text 0.0.4."""
    return _REGISTRY.render()


def reset_registry() -> None:
    """Đặt mọi mẫu về 0 (giữ định nghĩa); chỉ dùng được khi `APP_ENV=test`."""
    if os.environ.get("APP_ENV") != "test":
        raise RuntimeError("reset_registry() chỉ dùng khi APP_ENV=test")
    _REGISTRY.reset()
