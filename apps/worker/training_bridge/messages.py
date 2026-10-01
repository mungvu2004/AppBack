"""Chuỗi hiển thị cho người của cầu nối huấn luyện (BE-00 §10).

Chỉ `trained_version_label`: nhãn bản model mà `finish_training_job` gắn khi gọi
`registry.register_trained_version` (B6-03a [6]). Qua `clean_label` để chung một luật nhãn
với validator `Label` của dây (`apps.api.admin_ml_registry.registry`).
"""

from datetime import datetime

from apps.api.admin_ml_registry.registry import clean_label


def trained_version_label(*, base_model: str, epochs: int, finished_at: datetime) -> str:
    """Nhãn tiếng Việt viết thường ≤ 80 ký tự: `"huấn luyện {base_model} · {epochs} epoch · {ngày giờ UTC}"`.

    `finished_at` được định dạng `YYYY-MM-DD HH:MM` theo giờ của giá trị truyền vào (người gọi
    chịu trách nhiệm truyền UTC, K05); qua `clean_label` để đảm bảo cùng luật 1-80 ký tự với dây.
    """
    label = f"huấn luyện {base_model} · {epochs} epoch · {finished_at:%Y-%m-%d %H:%M}"
    return clean_label(label)
