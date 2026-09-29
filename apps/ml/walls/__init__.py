"""Bước tách tường của worker `ml` (`wallSegmentation`): ghép lát SegFormer ONNX và task `ml.infer.walls.segment`.

**Không** xuất lại task ở đây: sổ task chỉ nhận mỗi tên một lần, và `celery_main` đã nhập
`apps.ml.walls.tasks` qua `discover_submodules` (cùng lý do như `apps.ml.text`).
"""
