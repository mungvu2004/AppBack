# QA-04c — gắn mã hàng catalog phase 04 vào docstring pytest

- 13 tệp test dưới `apps/api/{core,floors,project_settings,quality,spatial_read,spatial_write}/tests/`: thêm dòng
  `Hàng catalog: [BE4-G-xxx]` / `[BE5-G-xxx]` vào docstring của 55 test đã chứng minh hàng đó, để
  `AppFront/qa/tools/coverage-gate.mjs --appback` thấy hàng ở tầng `be`.
- Chỉ docstring: không đổi phép kiểm, fixture, tên test, mã nguồn, route, schema, migration, openapi — bước 6, 7, 8
  không có gì mới để kiểm.
