"""apps.api.core — khung mà mọi module `apps/api/<module>/` cắm vào (B0-06).

Chỉ docstring: `wire` và `extensions` phải nhập được trong tiến trình worker (nơi
`fastapi`, `starlette` bị chặn, BE-00 §7), nên gói không được kéo theo thứ gì.
"""
