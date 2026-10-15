# QA-06b — phase 06: `field` dừng ở khoá dict, nhãn phiên bản nhận emoji ZWJ

- `apps/api/core/errors.py` (BUG-720, hàng catalog B06-G-046): `field_of` nhận thêm kiểu thân của route
  (`request.scope["route"].body_field`) và cắt đường lỗi ở khoá đầu tiên của mọi trường `dict`/`Mapping`,
  kể cả khoá chỉ gồm chữ-số (`overrides.GENERAL` → `overrides`), đúng BE-00 §4 và docstring cũ của hàm.
  Không biết kiểu (route không có thân, union nhiều nhánh) → giữ luật cũ (dừng ở đoạn không phải chữ-số).
- `apps/api/versions/service.py` (BUG-721, B06-G-228): nhãn phiên bản chỉ cấm ký tự điều khiển (Cc) và ký tự
  đảo chiều (U+200E, U+200F, U+061C, U+202A-U+202E, U+2066-U+2069); ZWJ (U+200D) và ký tự định dạng khác của
  emoji hợp lệ — khớp câu FE "ký tự điều khiển hoặc đảo chiều" (`versionHistoryModel.ts:452`).
- Test mới: `test_pydantic_error_on_alnum_dict_key_stops_at_the_dict[GENERAL]`,
  `test_normalize_label__zwj_allowed_bidi_and_control_rejected`; docstring pytest gắn id catalog phase 06.
- Không đổi route, schema, migration, openapi; hợp đồng N20 (`label` trim 0–60) không đổi.
