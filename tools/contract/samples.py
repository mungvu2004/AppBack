"""Mẫu golden trong `CONTRACT_SAMPLES_DIR` và luật ngày giờ W3 (B0-07 [2], [6].4).

Hai loại mẫu, cùng thư mục `<operationId>/` (bộ ghi ở `packages.testing.golden` viết ra):

- response HTTP, `<case>[_<hậu tố>]-<n>.json`: `operationId, case, method, pathTemplate,
  pathParams, query, status, contentType, body[, context]`;
- khung SSE, `<case>-event-<n>.json` (`record_stream_event`): `operationId, case, event`.

Bước 7 không xoá mẫu: thư mục mới mỗi lượt verify (ENV §2).
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

ISO_DATETIME_RE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
W3_SUFFIX_RE: Final = re.compile(r"\.\d{3}Z$")


class SampleError(ValueError):
    """Một file mẫu không đọc được — bước 7 hỏng thay vì bỏ qua mẫu đó."""


@dataclass(frozen=True, slots=True)
class HttpSample:
    """Một response đã ghi; `file` tương đối gốc thư mục mẫu, để in ra khi hỏng."""

    file: str
    operation_id: str
    status: int
    body: Any
    path_params: dict[str, str] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EventSample:
    """`data:` (đã `json.loads`) của một khung SSE nhận thật (H5)."""

    file: str
    operation_id: str
    body: Any


def _parse(rel: str, data: dict[str, Any]) -> HttpSample | EventSample:
    """Dựng mẫu từ JSON; thiếu khoá bắt buộc → `KeyError` (người gọi đổi thành `SampleError`)."""
    if "event" in data:
        return EventSample(rel, data["operationId"], data["event"])
    return HttpSample(
        rel,
        data["operationId"],
        int(data["status"]),
        data["body"],
        dict(data.get("pathParams", {})),
        dict(data.get("context", {})),
    )


def load_samples(root: Path | None) -> tuple[list[HttpSample], list[EventSample]]:
    """Mọi mẫu dưới `root` theo thứ tự đường; `root` vắng hay chưa có → không mẫu nào.

    File tạm của bộ ghi mang đuôi `.part`, nên `*.json` chỉ gặp file đã đổi tên xong.
    """
    http: list[HttpSample] = []
    events: list[EventSample] = []
    if root is None or not root.is_dir():
        return http, events
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        try:
            sample = _parse(rel, json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, KeyError, TypeError) as exc:
            raise SampleError(f"mẫu {rel} hỏng: {exc!r}") from exc
        if isinstance(sample, EventSample):
            events.append(sample)
        else:
            http.append(sample)
    return http, events


def bad_datetimes(value: Any, where: str = "body") -> list[str]:
    """Mọi chuỗi dạng ngày giờ ISO ở bất kỳ độ sâu nào mà không kết thúc `.sssZ` (W3).

    Schema cũ của FE nhận cả 6 chữ số và `+07:00` (`src/api/schemas/index.ts:4`), nên zod
    không bắt được; luật này bắt thay.
    """
    if isinstance(value, dict):
        return [bad for key, child in value.items() for bad in bad_datetimes(child, f"{where}.{key}")]
    if isinstance(value, list):
        return [bad for index, child in enumerate(value) for bad in bad_datetimes(child, f"{where}[{index}]")]
    if isinstance(value, str) and ISO_DATETIME_RE.match(value) and not W3_SUFFIX_RE.search(value):
        return [f"{where} = {value!r} không kết thúc .sssZ (W3)"]
    return []
