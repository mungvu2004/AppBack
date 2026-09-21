"""Điểm mở rộng giữa các module `apps/api/*` (BE-00 §2.2).

Module viết **sau** cắm vào module viết **trước** bằng một file có tên đã hẹn
(`stream_providers`, `view_parts`, `invite_sinks`, `drawing_scales`, …): chủ cổng
gọi `discover("<tên file>", "<TÊN HẰNG>")` và nhận đúng những module có file đó.
Nhờ vậy không ai phải sửa file của prompt trước (K27).

Luật quan trọng:

- **không bắt `ImportError`.** Module có thật mà nhập hỏng nghĩa là một điểm mở
  rộng biến mất im lặng; lỗi phải nổi lên lúc khởi động;
- thứ tự là thứ tự **tên module**, để kết quả tất định giữa các lần chạy;
- `override` chỉ dùng được khi `APP_ENV=test` — nó là lối tiêm của test, không
  phải cơ chế cấu hình.

Module này **không** nhập `fastapi`/`starlette` (BE-00 §7 "Hàm worker nhập"), nên
`app` chỉ là `object`.
"""

import importlib
import importlib.util
import pkgutil
from collections.abc import Sequence
from typing import Final

from packages.core.settings import get_core_settings

PACKAGE: Final = "apps.api"
_OVERRIDES_ATTR: Final = "_appback_extension_overrides"

type Extension = tuple[str, object]

_cache: Final[dict[tuple[str, str], list[Extension]]] = {}


def _submodule_names(submodule: str) -> list[str]:
    """Tên gói con một cấp của `apps.api` **có** file `<submodule>.py`, đã sắp theo tên."""
    root = importlib.import_module(PACKAGE)
    names: list[str] = []
    for info in sorted(pkgutil.iter_modules(root.__path__), key=lambda module: module.name):
        if not info.ispkg:
            continue
        full = f"{PACKAGE}.{info.name}.{submodule}"
        if importlib.util.find_spec(full) is not None:
            names.append(full)
    return names


def discover(submodule: str, attr: str) -> list[Extension]:
    """`[(tên module, giá trị `attr`)]` của mọi module một cấp có `<submodule>.py`.

    Thiếu `attr` trong một module đã có file → `RuntimeError`: khai nửa vời còn khó
    tìm hơn là không khai. Kết quả được nhớ theo tiến trình (mỗi lượt dò là một loạt
    `find_spec` trên đĩa).
    """
    key = (submodule, attr)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    found: list[Extension] = []
    for name in _submodule_names(submodule):
        module = importlib.import_module(name)
        if not hasattr(module, attr):
            raise RuntimeError(f"{name} thiếu {attr}")
        found.append((name, getattr(module, attr)))
    _cache[key] = found
    return found


def override(app: object, submodule: str, items: Sequence[Extension]) -> None:
    """Thay kết quả `resolve` của **một** app (chỉ `APP_ENV=test`)."""
    if get_core_settings().app_env != "test":
        raise RuntimeError("extensions.override chỉ dùng khi APP_ENV=test")
    overrides: dict[str, list[Extension]] = getattr(app, _OVERRIDES_ATTR, {})
    overrides[submodule] = list(items)
    setattr(app, _OVERRIDES_ATTR, overrides)


def resolve(app: object | None, submodule: str, attr: str) -> list[Extension]:
    """Bản `override` của `app` nếu có, còn lại là `discover` (`app=None` → `discover`)."""
    if app is not None:
        overrides: dict[str, list[Extension]] = getattr(app, _OVERRIDES_ATTR, {})
        if submodule in overrides:
            return overrides[submodule]
    return discover(submodule, attr)


def reset_cache() -> None:
    """Chỉ cho test: quên kết quả đã dò (test dựng module tạm rồi gỡ đi)."""
    _cache.clear()
