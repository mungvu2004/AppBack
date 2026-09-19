# REPORT — Khuôn báo cáo của worker

> Bản 1 · 2026-09-17.
> Dán **nguyên** khuôn dưới đây vào tin nhắn `worker_done`, điền mọi mục. Mục không áp dụng thì ghi `không áp dụng — <lý do>`.
> Người điều phối **từ chối** báo cáo thiếu mục, có bước "đạt" mà không có mã thoát, hoặc chưa commit.

```
## Báo cáo <mã prompt>  (FIX: <mã FIX hoặc "không">)

### Nhánh
- repo: AppBack | AppFront
- nhánh / commit cuối: <nhánh> @ <sha 12 ký tự>
- trạng thái cây: sạch (git status --porcelain rỗng) | KHÔNG sạch — <vì sao>

### Cổng
| bước | lệnh | mã thoát | ghi chú |
|---|---|---|---|
| 1 định dạng | … | 0 | |
| …           | … | … | |
(bước không chạy tới: mã thoát "—", ghi chú "chưa chạy — <lý do>")

### Độ phủ (AppBack)
- tổng: dòng x,x% · nhánh y,y%
- từng gói bị chạm: <gói> dòng · nhánh

### Hợp đồng
- golden sinh ra: <n> · giải mã đạt bằng zod FE @ <APPFRONT_SHA 12 ký tự>: <m>/<n>
- endpoint không có schema FE: <danh sách hoặc "không">

### Case
- bắt buộc theo khối [8]: <n> · test tìm thấy (case_gate): <m> · miễn: <danh sách + lý do>

### Dữ liệu
- migration mới: <revision id + tên> | không
- alembic heads trên nhánh: <số>

### Lệch khỏi prompt
- <điểm lệch> — <vì sao> — <phương án lùi đã dùng>
(không có thì ghi "không")

### Nợ và việc chưa làm
- <việc> — <prompt nên sở hữu>
(không có thì ghi "không")

### Thay đổi file (tóm tắt)
- tạo: <n> file · sửa: <m> file · ngoài cột "Sở hữu": <danh sách hoặc "không">
```
