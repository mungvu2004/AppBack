"""Bộ ghi golden và bộ đọc SSE của harness hợp đồng (B0-07).

Giao diện cho prompt sau: `attach_context(response, **ctx)` (H1 ngữ cảnh),
`record_stream_event(op, case, data)` (H5), `sse.parse_sse(raw)` (H5, B4-01).
"""

from packages.testing.golden.recorder import attach_context, record_stream_event

__all__ = ["attach_context", "record_stream_event"]
