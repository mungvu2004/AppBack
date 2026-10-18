# UIFIX-B3 — review UI/UX, gói backend B3

Không sửa mã. Gói này chỉ điều tra, kết quả ở `F:/App/ui-review/fix/reports/B3.md`.

- G4b-17: chưa có đường ghi lưới trục và gốc toạ độ. Trục bị ghi cứng `axes: []` ở cả đường ghi lẫn đường đọc; gốc toạ độ chưa có chỗ lưu. Còn dở.
- G3-13: N4 đã chặn bằng `MEMBER_LAST_EDITOR` và có test. Đổi vai toàn cục (#41) chưa kiểm người sửa cuối của dự án (nằm ngoài phạm vi gói).
- N4-03: chưa có vai riêng theo dự án, vai là `users.role` toàn cục. Còn dở, đã ước lượng công sức.
- G3-35: `estimate_skew` chỉ đo góc xoay, không đo méo hình thang. Còn dở.
