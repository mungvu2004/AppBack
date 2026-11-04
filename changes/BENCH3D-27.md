# BENCH3D-27 — tải lại bản vẽ làm mất tỉ lệ người đặt, lớp trộn lệch hai tỉ lệ

- Gốc: `page_key` chứa id lượt tải nên đổi ở mọi lần tải, kể cả đúng tệp cũ. `write_layer` so khoá, coi tỉ lệ người đặt là
  "của trang khác": hạng về `none`, tỉ lệ AI thắng, và nền không được quy đổi. Mục giữ lại ở tỉ lệ cũ, mục AI ở tỉ lệ mới.
  f-22: human 34,7 bị thay bằng AI 35,57 (lệch 2,5 %), cùng SHA tệp, nên tường và ô mở chồng lên nhau.
- Cùng trang: `apps/api/drawings/drawings.py` `_carry_scale_page`, gọi trong `upsert_drawing`, đường duy nhất đổi bản vẽ sang
  lượt tải khác. Cùng `content_sha256`, `page_index`, `crop_corners` và cùng khổ ảnh → `floor_documents.scale_page_key` theo
  sang khoá mới, trong cùng giao dịch. `write_layer` và `effective_scale_source` đều so khoá nên cả hai đúng mà không phải sửa;
  tỉ lệ `human` không bị hạ hạng cả lúc lượt đang chạy hay khi lượt hỏng. Không tăng `revision` vì lớp và tỉ lệ không đổi.
  Thiếu SHA (dữ liệu cũ) hoặc tỉ lệ vốn gắn trang khác → không làm gì. Nắn lại trên cùng lượt tải vẫn là trang khác, như trước.
- Trang khác thật: `apps/api/spatial_write/writer.py` `_target_scale` quy nền về tỉ lệ mới (`factor`), kể cả mục đã duyệt
  (`include_reviewed`), giống luật tỉ lệ tạm H4: tỉ lệ cũ không nói gì về trang mới. Toạ độ pixel của mục giữ lại không đổi, nên
  cả lớp chỉ còn một tỉ lệ và `_WallMatcher` khớp được mục AI trùng thay vì để chồng. Mở rộng so với K21 ("mục đã duyệt không đổi")
  chỉ cho đúng ca này.
- Tỉ lệ mới là `project_default` thì không phải số đo: nền giữ nguyên mm như trước; cờ đã có (`scaleStatus`, FE tô đỏ, chặn bước
  phụ thuộc số đo).
- Giới hạn đã chấp nhận (ghi `ponytail:` trong `_target_scale`): giữ pixel chỉ đúng khi hai tệp cùng độ phân giải. Tệp khác độ
  phân giải thì mm mục giữ lại lệch theo tỉ số hai tỉ lệ; hoàn tác bằng phiên bản "trạng thái trước khi ghi kết quả AI" (N19).
- Không đổi API/OpenAPI/migration. Tầng đã mất tỉ lệ người đặt không tự khôi phục: phải đặt lại hoặc phục hồi phiên bản.
- Test: `test_drawings.py` (cùng tệp chuyển khoá; khác tệp, khác khổ giữ khoá), `test_writer_scale.py` (trang khác quy cả mục đã
  duyệt về tỉ lệ mới; `project_default` giữ nguyên). `test_persist_keeps_human_scale_on_same_page` phủ phần còn lại sau khi chuyển khoá.
- Chưa kiểm trên f14: chưa chạy lại f-22 thật, vì đợt này không vá nóng container.
