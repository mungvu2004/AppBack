"""Đọc compose YAML và tự giải `extends`, không gọi `docker compose config` (container
verify không có Docker CLI — hợp đồng B0-08 §2).

Quy tắc gộp theo hợp đồng (đo trên compose v5.3.0, hợp-đồng B0-08 §2 bản CHỐT 1):
map gộp đệ quy; `environment` (list `K=V` hoặc map) chuẩn hoá thành map rồi gộp theo
khoá; `command`/`entrypoint`/`healthcheck`/`logging`/`image` của file con **thay
nguyên** bản của base (không gộp khoá con bên trong chúng); `ports`/`volumes`/
`profiles` (list) hợp theo thứ tự, bỏ phần tử trùng đã có; `networks` dạng list hợp
theo thứ tự, dạng map gộp map con.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_LIST_MERGE_KEYS = {"ports", "volumes", "profiles"}
_WHOLESALE_REPLACE_KEYS = {"command", "entrypoint", "image", "healthcheck", "logging"}


def load_yaml(path: Path) -> dict[str, Any]:
    """Nạp một file YAML compose bằng `safe_load`; trả `{}` nếu rỗng."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _normalize_environment(value: Any) -> dict[str, str | None]:
    """Chuẩn hoá `environment` (list `K=V`/`K` hoặc map) thành map theo khoá."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    normalized: dict[str, str | None] = {}
    for item in value:
        key, sep, val = str(item).partition("=")
        normalized[key] = val if sep else None
    return normalized


def _merge_networks(base: Any, override: Any) -> Any:
    """`networks`: dạng map gộp map con; dạng list hợp theo thứ tự, bỏ phần tử trùng."""
    if isinstance(base, dict) or isinstance(override, dict):
        merged: dict[str, Any] = {}
        for src in (base, override):
            if isinstance(src, dict):
                merged.update(src)
            elif isinstance(src, list):
                merged.update(dict.fromkeys(src))
        return merged
    merged_list = list(base or [])
    for item in override or []:
        if item not in merged_list:
            merged_list.append(item)
    return merged_list


def merge_service(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Gộp `override` (khai ở dev/ci/prod) lên `base` (đã giải qua `extends`).

    `command`/`entrypoint`/`image`/`healthcheck`/`logging` của `override` thay **nguyên**
    giá trị của `base` — kể cả khi cả hai đều là map (không gộp khoá con bên trong
    `healthcheck`/`logging`, đo thật trên compose v5.3.0)."""
    result = dict(base)
    for key, value in override.items():
        if key == "environment":
            merged_env = _normalize_environment(result.get("environment"))
            merged_env.update(_normalize_environment(value))
            result["environment"] = merged_env
        elif key == "networks":
            result["networks"] = _merge_networks(result.get("networks"), value)
        elif key in _WHOLESALE_REPLACE_KEYS:
            result[key] = value
        elif key in _LIST_MERGE_KEYS and isinstance(value, list) and isinstance(result.get(key), list):
            merged_list = list(result[key])
            for item in value:
                if item not in merged_list:
                    merged_list.append(item)
            result[key] = merged_list
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_service(result[key], value)
        else:
            result[key] = value
    return result


def resolve_service(path: Path, service_name: str, _seen: frozenset[Path] = frozenset()) -> dict[str, Any]:
    """Giải một dịch vụ tại `path` theo `extends` đệ quy (`extends.file` tương đối thư
    mục chứa `path`).

    Ném `ValueError` khi thiếu dịch vụ hoặc `extends` tạo vòng lặp — cả hai là lỗi cấu
    hình thật, không phải case cần bỏ qua.
    """
    resolved_path = path.resolve()
    if resolved_path in _seen:
        raise ValueError(f"vòng lặp extends quay lại {path}")
    doc = load_yaml(path)
    services = doc.get("services") or {}
    if service_name not in services:
        raise ValueError(f"thiếu dịch vụ {service_name!r} trong {path}")
    own = dict(services[service_name])
    extends = own.pop("extends", None)
    if not extends:
        return own
    base_path = (path.parent / extends["file"]).resolve()
    base_service = extends.get("service", service_name)
    base = resolve_service(base_path, base_service, _seen | {resolved_path})
    return merge_service(base, own)


def resolve_all_services(path: Path) -> dict[str, dict[str, Any]]:
    """Giải `extends` cho mọi dịch vụ khai trực tiếp trong file compose tại `path`."""
    doc = load_yaml(path)
    services = doc.get("services") or {}
    return {name: resolve_service(path, name) for name in services}
