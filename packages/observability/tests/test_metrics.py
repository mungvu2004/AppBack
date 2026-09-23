"""Registry metric: khai, khai lại, `render`, `reset_registry`, hạn mức (B7-01 [8])."""

import math
import threading
from collections.abc import Iterator

import pytest

from packages.observability.metrics import (
    DEFAULT_BUCKETS,
    Counter,
    Histogram,
    counter,
    histogram,
    render,
    reset_registry,
)
from packages.observability.settings import get_observability_settings, reset_observability_settings_cache


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Mỗi test bắt đầu từ mẫu 0, không rò sang test khác. `reset_registry` chỉ chạy được ở `APP_ENV=test`."""
    monkeypatch.setenv("APP_ENV", "test")
    reset_registry()
    yield
    reset_observability_settings_cache()
    reset_registry()


def test_counter_without_labels_renders_bare_name() -> None:
    """Counter không nhãn: không dấu `{}` trong `render()`."""
    hits = counter("appback_test_bare_total", help="đếm không nhãn")
    hits.inc()
    hits.inc(2)
    text = render()
    assert "appback_test_bare_total 3.0" in text
    assert "# HELP appback_test_bare_total đếm không nhãn" in text
    assert "# TYPE appback_test_bare_total counter" in text


def test_counter_with_labels_exact_render() -> None:
    """Chuỗi `render` khớp nguyên văn cho counter có nhãn, escape `"`, `\\`, xuống dòng."""
    help_text = 'trợ giúp "trích" và \\gạch\\'
    label_value = 'ổn"\\\nkhông'
    hits = counter("appback_test_labeled_total", help=help_text, labels=("reason",))
    hits.inc(reason=label_value)
    text = render()
    # HELP không có dấu ngoặc kép quanh nó: chỉ `\` và `\n` được escape, không escape `"`.
    assert r'# HELP appback_test_labeled_total trợ giúp "trích" và \\gạch\\' in text
    # Giá trị nhãn nằm trong dấu ngoặc kép: `\`, `"`, `\n` đều được escape.
    assert 'appback_test_labeled_total{reason="ổn\\"\\\\\\nkhông"} 1.0' in text


def test_histogram_buckets_are_cumulative_with_inf() -> None:
    """3 bucket: `_bucket{le}` tích luỹ, `+Inf`, `_sum`, `_count`."""
    hist = histogram("appback_test_duration", help="phân bố", buckets=(1.0, 5.0, 10.0))
    hist.observe(0.5)
    hist.observe(3.0)
    hist.observe(100.0)
    text = render()
    assert 'appback_test_duration_bucket{le="1.0"} 1.0' in text
    assert 'appback_test_duration_bucket{le="5.0"} 2.0' in text
    assert 'appback_test_duration_bucket{le="10.0"} 2.0' in text
    assert 'appback_test_duration_bucket{le="+Inf"} 3.0' in text
    assert "appback_test_duration_sum 103.5" in text
    assert "appback_test_duration_count 3.0" in text


def test_default_buckets_are_used_when_omitted() -> None:
    """Không truyền `buckets` → `DEFAULT_BUCKETS`."""
    hist = histogram("appback_test_default_buckets", help="mặc định")
    hist.observe(0.2)
    text = render()
    for bound in DEFAULT_BUCKETS:
        assert f'le="{bound!r}"' in text


@pytest.mark.parametrize(
    "name",
    ["not_appback_total", "appback_UPPER_total", "appback__total", "appback_x"],
    ids=["thieu-tien-to", "hoa", "khong-chu-cai-dau", "khong-ket-thuc-total"],
)
def test_counter_name_must_match_pattern_and_end_total(name: str) -> None:
    """Tên sai mẫu, hay counter không kết thúc `_total` → `ValueError` lúc khai."""
    with pytest.raises(ValueError, match=r"metric|counter"):
        counter(name, help="sai")


@pytest.mark.parametrize("label", ["Reason", "le", "1reason"], ids=["hoa", "le-cam", "so-dau"])
def test_label_name_must_match_pattern_and_not_le(label: str) -> None:
    """Nhãn sai mẫu hay `le` → `ValueError` lúc khai."""
    with pytest.raises(ValueError, match="nhãn"):
        counter("appback_test_bad_label_total", help="sai", labels=(label,))


def test_redeclare_same_definition_returns_working_handle() -> None:
    """Khai lại cùng tên/loại/help/nhãn → không lỗi, cùng registry."""
    first = counter("appback_test_redeclare_total", help="giữ", labels=("x",))
    second = counter("appback_test_redeclare_total", help="giữ", labels=("x",))
    first.inc(x="a")
    second.inc(x="a")
    assert 'appback_test_redeclare_total{x="a"} 2.0' in render()


def test_redeclare_with_different_definition_raises() -> None:
    """Khai lại khác `help`, nhãn hay loại → `ValueError`."""
    counter("appback_test_conflict_total", help="một", labels=("x",))
    with pytest.raises(ValueError, match="định nghĩa khác"):
        counter("appback_test_conflict_total", help="khác", labels=("x",))
    with pytest.raises(ValueError, match="định nghĩa khác"):
        counter("appback_test_conflict_total", help="một", labels=("y",))
    with pytest.raises(ValueError, match="định nghĩa khác"):
        histogram("appback_test_conflict_total", help="một", labels=("x",))


def test_inc_on_an_undeclared_name_raises_not_declared() -> None:
    """`Counter`/`Histogram` chỉ tồn tại sau `define()` thành công; gọi thẳng tên lạ → `ValueError`."""
    with pytest.raises(ValueError, match="chưa khai"):
        Counter("appback_test_never_declared_total").inc()
    with pytest.raises(ValueError, match="chưa khai"):
        Histogram("appback_test_never_declared_hist").observe(1.0)


def test_inc_rejects_missing_or_extra_labels() -> None:
    hits = counter("appback_test_labelcheck_total", help="kiểm nhãn", labels=("a", "b"))
    with pytest.raises(ValueError, match="nhãn không khớp"):
        hits.inc(a="1")
    with pytest.raises(ValueError, match="nhãn không khớp"):
        hits.inc(a="1", b="2", c="3")


def test_inc_rejects_negative_amount_and_nan() -> None:
    hits = counter("appback_test_amount_total", help="kiểm giá trị")
    with pytest.raises(ValueError, match="≥ 0"):
        hits.inc(-1)
    with pytest.raises(ValueError, match="NaN"):
        hits.inc(math.nan)
    with pytest.raises(ValueError, match="phải là số"):
        hits.inc(True)  # bool là subclass của int nhưng không phải giá trị hợp lệ


def test_label_value_over_64_chars_is_rejected() -> None:
    hits = counter("appback_test_longlabel_total", help="dài", labels=("x",))
    with pytest.raises(ValueError, match="≤ 64"):
        hits.inc(x="a" * 65)


def test_reset_registry_zeros_samples_but_keeps_definitions() -> None:
    hits = counter("appback_test_reset_total", help="reset", labels=("x",))
    hits.inc(x="a")
    reset_registry()
    assert 'appback_test_reset_total{x="a"} 0.0' in render()
    hits.inc(x="a")
    assert 'appback_test_reset_total{x="a"} 1.0' in render()


def test_reset_registry_outside_test_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    with pytest.raises(RuntimeError, match="APP_ENV=test"):
        reset_registry()
    monkeypatch.setenv("APP_ENV", "test")


def test_metrics_max_series_drops_extra_samples(monkeypatch: pytest.MonkeyPatch) -> None:
    """`METRICS_MAX_SERIES=2` → mẫu thứ 3 bị bỏ, `appback_metrics_series_dropped_total` tăng."""
    monkeypatch.setenv("METRICS_MAX_SERIES", "2")
    reset_observability_settings_cache()
    assert get_observability_settings().metrics_max_series == 2
    hits = counter("appback_test_capped_total", help="trần", labels=("x",))
    hits.inc(x="a")
    hits.inc(x="b")
    hits.inc(x="c")
    text = render()
    assert 'appback_test_capped_total{x="a"} 1.0' in text
    assert 'appback_test_capped_total{x="b"} 1.0' in text
    assert 'x="c"' not in text
    assert 'appback_metrics_series_dropped_total{metric="appback_test_capped_total"} 1.0' in text


def test_eight_threads_ten_thousand_increments_each_land_exactly() -> None:
    """`threading.Lock` quanh registry: 8 luồng x 10.000 `inc` → đúng 80.000."""
    hits = counter("appback_test_threaded_total", help="đua luồng")

    def worker() -> None:
        for _ in range(10_000):
            hits.inc()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert "appback_test_threaded_total 80000.0" in render()
