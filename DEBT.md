# DEBT — Sổ nợ kỹ thuật

> **Mọi nợ phát sinh trong một phiên phải có một dòng ở đây trước khi phiên kết thúc** (`RULE-CODE.md` R-34).
> Nợ = việc biết là còn thiếu/còn sai mà lần này không làm: lỗi của module khác, test chập chờn,
> giới hạn đã chấp nhận, tối ưu hoãn lại, `ponytail:`/`TODO` trong mã.
>
> - Id: `NO-<nnn>` tăng dần, không dùng lại.
> - Mức: theo `RULE.md` §1 (`P0 P1 P2 P3 Nit`).
> - Trạng thái: `mở` · `đang sửa (<phiên/agent>)` · `đã sửa (<sha 7>)` · `chấp nhận (<lý do>)` · `bỏ (<lý do>)`.
> - Đã sửa hay chấp nhận thì **giữ nguyên dòng**, chỉ đổi trạng thái — sổ này là lịch sử, không phải hàng đợi.

| Id | Ngày | Nợ | Nguyên nhân gốc | Chủ | Mức | Trạng thái |
|---|---|---|---|---|---|---|
| NO-001 | 2026-09-20 | `bash tools/verify/run.sh lock` hỏng `FileExistsError: /src-out/lock`; phải lock bằng cách mount `/src-out` thủ công | `run.sh` mount host **đúng vào** `/src-out/lock`, `steps.py::_clean_dir` `rmtree` không xoá được mount point rồi `mkdir` → trùng. `openapi`, `merge-heads` cùng khuôn | B0-01 (`tools/verify/*`) | P2 | đang sửa (sub-agent, phiên B0-04) |
| NO-002 | 2026-09-20 | `packages/db/tests/test_migrate_check.py::test_downgrade_leaving_table_fails` hỏng 1/3 lượt verify (`['seed ci hai lần'] != ['chỉ còn alembic_version']`) | chưa xác định — nghi thứ tự bước hoặc rò trạng thái giữa test | B0-03 (`packages/db/**`) | P1 (cổng không tin được) | đang sửa (sub-agent, phiên B0-04) |
| NO-003 | 2026-09-20 | `LocalDiskStorage`: object và `<key>.meta.json` là hai lần `os.replace`, giữa hai lần đó `stat` có thể trả `sha256` của bản trước | Khuôn lưu trữ tách metadata ra file riêng; không có API đổi tên hai file nguyên tử | B0-04 | P3 | chấp nhận (chỉ là kho máy dev; staging/production dùng S3 nơi `put_object` gắn metadata trong cùng lượt ghi — đã ghi trong docstring `packages/storage/local.py`) |
| NO-004 | 2026-09-20 | `S3Storage.list_prefix` gọi `stat` cho **từng** object (N+1) | `ListObjectsV2` của AWS không trả `x-amz-meta-*`, mà `ObjectInfo` hứa có `sha256`/`kind` | B0-04 | P2 | chấp nhận (chỉ lịch dọn rác nền gọi; nếu thành điểm nóng thì đổi `list_prefix` trả `key` + `last_modified`, ~3 dòng) |
| NO-005 | 2026-09-20 | `S3Storage._put_cors` dùng API riêng `Minio._execute` | `minio` 7.2.20 chưa phơi `set_bucket_cors` | B0-04 | Nit | chấp nhận (gỡ khi nâng `minio` lên bản có API CORS công khai) |
