# FIX — Khối sửa lỗi dùng chung

> Bản 4 · 2026-09-19: [7] thông điệp commit theo Conventional Commits + trailer `Prompt:`, `Fix:` (BE-00 §13.2).
> Bản 3 · 2026-09-18 (phân xử phần 7, sửa lần hai): "Không dùng khi" bỏ vế `git revert` (K7-3); luật 4 ghi rõ file SHA và thêm F-00c (K7-15d).
> Bản 2 · 2026-09-17. Thêm luật 6–8 theo tranh luận lô 4c.
> **Dùng khi:** lỗi trên mã **đã xanh** ở nhánh tích hợp, kể cả CI đỏ sau khi đã đẩy; kiểm toán B7-02 tìm ra lỗ; người dùng báo lỗi lúc chạy; hợp đồng đổi sau khi F-00a/F-00b/F-00c đã hợp nhất.
> **Không dùng khi** cổng đỏ **ngay sau** khi hợp nhất một prompt: người điều phối lùi lần hợp nhất đó bằng `git reset --keep <sha trước>` (bỏ cả merge lẫn các commit sau nó), rồi giao lại chính prompt đó vào worktree cũ, kèm rebase và bảng cổng đỏ (`00-SO-TRA.md` §6.5b, §6.6; phân xử phần 7 Q-4, K7-3). Nhánh tích hợp chỉ đẩy khi verify tích hợp của **cả đợt** đã xanh, nên lúc đó luôn là chưa đẩy.
> Người điều phối điền khối này rồi giao cho **đúng prompt sở hữu** file lỗi, như một task Orca mới trên worktree mới.

## Khuôn spec

```
FIX <mã FIX> cho <mã prompt sở hữu> — <một câu mô tả lỗi>

[1 TRIỆU CHỨNG]      Người dùng hoặc cổng thấy gì. Dán nguyên văn thông báo lỗi, mã thoát, bước cổng
[2 TÁI HIỆN]         Lệnh hoặc chuỗi thao tác tái hiện, trên commit nào
[3 BẰNG CHỨNG]       file:dòng, log có requestId, golden lệch, số đo độ phủ
[4 KHOANH VÙNG]      File được sửa (trong cột "Sở hữu" của prompt gốc) · file CẤM sửa
[5 SỬA NHỎ NHẤT]     Hướng sửa, hoặc "worker tự tìm" kèm giới hạn: không đổi hợp đồng, không đổi schema DB trừ khi ghi rõ
[6 TEST CHẶN TÁI PHÁT] Tên test mới theo CASE.md; phải ĐỎ trên commit hiện tại trước khi sửa
[7 NGHIỆM THU]       just verify (hoặc pnpm verify) đạt; test ở [6] đỏ → xanh; commit "fix(<scope>): …" + trailer "Prompt: <mã prompt>", "Fix: <mã FIX>" (BE-00 §13.2); báo cáo theo REPORT.md
```

## Luật

1. **Đỏ trước, xanh sau.** Báo cáo phải có lệnh đã chạy và mã thoát khi test còn đỏ, rồi mới tới khi đã xanh.
2. **Không sửa test cho khớp lỗi.** Chỉ được sửa test khi [3 BẰNG CHỨNG] chỉ ra chính test sai so với hợp đồng hoặc hiến chương, và báo cáo phải nói rõ.
3. **Không mở rộng phạm vi.** Thấy lỗi khác thì ghi vào "Nợ và việc chưa làm"; không sửa trong FIX này.
4. **Hợp đồng đổi** → FIX cho F-00a/F-00b/F-00c trước. Hợp nhất xong, người điều phối nâng `tools/contract/APPFRONT_SHA` của AppBack (không phải `prompts/APPFRONT_SHA`, Q-8), rồi mới FIX cho prompt BE.
5. **Mã FIX:** `FIX-<số thứ tự 3 chữ số>`, ghi vào `docs/fixes.md` của repo tích hợp (người điều phối giữ).
6. **FIX đổi `packages/domain/spatial/model.py`** chạy `python -m apps.api.spatial_read.cli check-documents` trên seed và dán kết quả, và (khi bảng `versions` của B3-04 đã có) thêm vào test của FIX một lượt giải mọi `versions.snapshot` bằng `codec.document_from_json`; hỏng thì FIX kèm revision chuyển dữ liệu.
7. **FIX nâng `DOCUMENT_SCHEMA_VERSION`** kèm revision chuyển cả `floor_documents` lẫn `versions.snapshot`.
8. **FIX thu hẹp danh mục luật** (B3-05) kèm revision gỡ mã và khoá không còn khỏi `rule_configs.overrides`; thu hẹp khoảng `min`/`max` thì revision kẹp giá trị đã lưu về biên mới.
