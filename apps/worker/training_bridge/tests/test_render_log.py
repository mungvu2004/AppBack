"""Test `render_log`, `LOG_TEMPLATES`: che dữ liệu, khoá/tham số lệch, cắt 2000 ký tự (B6-03a [8]).

`LOG_TEMPLATE_KEYS` chép tay từ BE-00 §9 "Mẫu log huấn luyện" để phát hiện lệch bảng khi ai
đó đổi `LOG_TEMPLATES` mà quên cập nhật hiến chương (hay ngược lại).
"""

import pytest

from packages.messaging.payloads.training import LOG_TEMPLATES, render_log

LOG_TEMPLATE_KEYS = frozenset(
    {
        "training_gpu_waiting",
        "training_started",
        "training_dataset_ready",
        "training_epoch_finished",
        "training_metric_skipped",
        "training_exported",
        "training_parity",
        "training_cancelled",
        "training_failed",
        "training_warning",
    }
)

_SAMPLE_PARAMS: dict[str, dict[str, str | int | float | bool]] = {
    "training_gpu_waiting": {},
    "training_started": {"base_model": "yolov8n", "device": "cpu", "train": 100, "validation": 20, "batch_size": 8},
    "training_dataset_ready": {"train_tiles": 100, "validation_tiles": 20, "skipped_boxes": 3},
    "training_epoch_finished": {"epoch": 1, "loss": 0.85, "metric": "iou", "value": 0.5},
    "training_metric_skipped": {"epoch": 1, "metric": "map50"},
    "training_exported": {"size_mib": 12.5},
    "training_parity": {"agreement": 0.99},
    "training_cancelled": {"epoch": 2},
    "training_failed": {"code": "DATASET_SPLIT_EMPTY"},
    "training_warning": {"code": "TRAINING_METRICS_MISSING"},
}


def test_log_template_keys_match_charter() -> None:
    """Tập khoá của `LOG_TEMPLATES` đúng bảng BE-00 §9, không thừa không thiếu."""
    assert frozenset(LOG_TEMPLATES) == LOG_TEMPLATE_KEYS


@pytest.mark.parametrize("key", sorted(LOG_TEMPLATE_KEYS))
def test_render_log_every_template_with_sample_params(key: str) -> None:
    """Mọi khoá của bảng với tham số mẫu → khác `None`."""
    assert render_log(key, _SAMPLE_PARAMS[key]) is not None


@pytest.mark.parametrize("key", sorted(LOG_TEMPLATE_KEYS))
def test_log_template_text_is_lowercase(key: str) -> None:
    """Câu mẫu (phần văn bản tĩnh, chưa thế tham số) viết thường (BE-00 §10)."""
    assert LOG_TEMPLATES[key].text == LOG_TEMPLATES[key].text.lower()


def test_render_log_unknown_key_returns_none() -> None:
    """Khoá lạ không có trong `LOG_TEMPLATES` → `None`."""
    assert render_log("training_does_not_exist", {}) is None


def test_render_log_dotted_key_returns_none() -> None:
    """Khoá dạng chấm (`training.started`) không khớp mẫu → `None`."""
    assert render_log("training.started", _SAMPLE_PARAMS["training_started"]) is None


def test_render_log_missing_param_returns_none() -> None:
    """Thiếu một tham số bắt buộc → `None`."""
    params = dict(_SAMPLE_PARAMS["training_started"])
    del params["device"]
    assert render_log("training_started", params) is None


def test_render_log_extra_param_returns_none() -> None:
    """Thừa tham số ngoài `line` → `None`."""
    params = dict(_SAMPLE_PARAMS["training_cancelled"])
    params["unexpected"] = "x"
    assert render_log("training_cancelled", params) is None


def test_render_log_extra_line_param_is_allowed() -> None:
    """Thừa tham số `line` → vẫn dựng câu (không bị coi là thừa)."""
    params = dict(_SAMPLE_PARAMS["training_cancelled"])
    params["line"] = 42
    assert render_log("training_cancelled", params) is not None


def test_render_log_masks_url_with_query() -> None:
    """URL có query trong tham số chuỗi → `[url]`."""
    text_url = render_log("training_parity", {"agreement": "see https://example.com/x?y=1 for detail"})
    assert text_url is not None
    assert "https://" not in text_url
    assert "[url]" in text_url


def test_render_log_masks_posix_absolute_path() -> None:
    """`/etc/passwd` → `[đường dẫn]`."""
    text = render_log("training_parity", {"agreement": "leaked /etc/passwd here"})
    assert text is not None
    assert "/etc/passwd" not in text
    assert "[đường dẫn]" in text


def test_render_log_masks_windows_absolute_path() -> None:
    """`C:\\Users\\x` → `[đường dẫn]`."""
    text = render_log("training_parity", {"agreement": r"path C:\Users\x broke"})
    assert text is not None
    assert r"C:\Users\x" not in text
    assert "[đường dẫn]" in text


def test_render_log_masks_env_var_dollar() -> None:
    """`$HOME` → `[biến môi trường]`."""
    text = render_log("training_parity", {"agreement": "home is $HOME now"})
    assert text is not None
    assert "$HOME" not in text
    assert "[biến môi trường]" in text


def test_render_log_masks_key_value_env_before_url() -> None:
    """`DATABASE_URL=postgres://…` che thành MỘT `[biến môi trường]`, không tách URL riêng."""
    text = render_log("training_parity", {"agreement": "conn DATABASE_URL=postgres://u:p@host/db failed"})
    assert text is not None
    assert "postgres://" not in text
    assert "[biến môi trường]" in text
    assert "[url]" not in text


def test_render_log_code_param_lowercase_masked() -> None:
    """`code` không UPPER_SNAKE → `[mã]`."""
    text = render_log("training_warning", {"code": "dataset_split_empty"})
    assert text is not None
    assert "[mã]" in text
    assert "dataset_split_empty" not in text


def test_render_log_code_param_upper_snake_kept() -> None:
    """`code` đúng UPPER_SNAKE → giữ nguyên."""
    text = render_log("training_warning", {"code": "DATASET_SPLIT_EMPTY"})
    assert text == "cảnh báo: DATASET_SPLIT_EMPTY"


def test_render_log_float_uses_comma_decimal() -> None:
    """Số thực in dấu phẩy thập phân (`0,85`)."""
    text = render_log("training_epoch_finished", {"epoch": 1, "loss": 0.85, "metric": "iou", "value": 0.5})
    assert text is not None
    assert "0,85" in text
    assert "0.85" not in text


def test_render_log_bool_rendered_as_vietnamese_word() -> None:
    """`bool` tham số → `có`/`không` (dùng `code` giả làm cờ để kiểm bool, không qua luật `[mã]`)."""
    text_true = render_log("training_parity", {"agreement": True})
    text_false = render_log("training_parity", {"agreement": False})
    assert text_true == "đối chiếu độ khớp: có"
    assert text_false == "đối chiếu độ khớp: không"


def test_render_log_truncates_to_2000_chars() -> None:
    """Kết quả cắt ≤ 2000 ký tự dù tham số chuỗi rất dài."""
    long_value = "a" * 3000
    text = render_log("training_parity", {"agreement": long_value})
    assert text is not None
    assert len(text) == 2000
