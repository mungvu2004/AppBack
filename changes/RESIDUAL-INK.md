# RESIDUAL-INK — gợi ý đồ đạc từ mực dư (B4 vật sót)

- `pipeline_build/residual.py`: mực trang trừ tường, chữ OCR, hộp YOLO, cung cửa, chỉ trong căn hộ, lọc mảnh theo cỡ mét;
  chỉ trang nền trắng (≥ 50 % điểm ≥ 250); tối đa 15 hộp, bỏ hộp trùng phát hiện (IoU ≥ 0,3 / chứa ≥ 60 %).
- `build_layer(page=…)` thêm đồ `other` `suggested=True` (cờ B3); task dựng đọc trang + `walls.png`, vắng/hỏng → bỏ gợi ý, không hỏng bước.
- `BuildStepPayload.page_key` tuỳ chọn (mặc định `None`, thông điệp cũ vẫn giải được); `step_done` điền từ bản vẽ hiện hành.
- Không đổi API, DB, migration, hợp đồng FE–BE (`suggested` đã có từ B3-SUGGEST).
- Cổng áp dụng: lint/type, test apps/worker/pipeline_build, pipeline_steps. Migration/hợp đồng: không áp dụng.
