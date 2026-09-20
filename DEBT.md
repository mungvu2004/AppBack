# DEBT — Sổ nợ kỹ thuật

> **Mọi nợ phát sinh trong một phiên phải có một dòng ở đây trước khi phiên kết thúc** (`RULE-CODE.md` R-34).
> Nợ = việc biết là còn thiếu/còn sai mà lần này không làm: lỗi của module khác, test chập chờn,
> giới hạn đã chấp nhận, tối ưu hoãn lại, `ponytail:`/`TODO` trong mã.
>
> **Ô `✔` là nguồn sự thật:**
>
> | Ô | Nghĩa | Bắt buộc kèm |
> |---|---|---|
> | `⬜` | mở, chưa ai làm | — |
> | `🔧` | đang sửa | ai/phiên nào đang giữ |
> | `✅` | **đã giải quyết** | ngày đóng + commit sửa (mã `FIX-<nnn>`, hoặc `sha 7` nếu đóng ở commit sau) |
> | `➖` | chấp nhận, không sửa | lý do đứng được + đường nâng cấp nếu đổi ý |
> | `❌` | bỏ, không còn đúng | lý do |
>
> Luật: Id `NO-<nnn>` tăng dần, **không dùng lại**. Sửa xong là **tích ngay trong chính commit sửa**
> (ghi mã `FIX-<nnn>`; sha điền sau nếu cần) — đừng để phiên sau phải đoán. Mức theo `RULE.md` §1. **Không bao giờ xoá dòng**:
> sổ này là lịch sử, không phải hàng đợi. Nợ `P0`/`P1` còn `⬜`/`🔧` thì chặn merge (R-38).

| ✔ | Id | Mở | Đóng | Nợ | Nguyên nhân gốc | Chủ | Mức | Ghi chú đóng |
|---|---|---|---|---|---|---|---|---|
| ✅ | NO-001 | 2026-09-20 | 2026-09-20 | `bash tools/verify/run.sh lock` hỏng `FileExistsError: /src-out/lock`; phải lock bằng cách mount `/src-out` thủ công | `run.sh` bind-mount host **đúng vào** `/src-out/<việc>`; `rmtree` xoá được nội dung nhưng không gỡ được chính mount point (EBUSY, `ignore_errors` nuốt), nên `mkdir` không `exist_ok` ném `FileExistsError`. Ba việc `lock`, `openapi`, `merge-heads` cùng đi qua `_clean_dir` | B0-01 (`tools/verify/*`) | P2 | **FIX-001** — `_clean_dir` `mkdir(..., exist_ok=True)` (`tools/verify/steps.py:243`), test chặn tái phát `test_lock_thư_mục_ra_là_mount_point_không_gỡ_được` (đỏ trước, xanh sau). `run.sh lock` thoát 0, `uv.lock` không đổi |
| ✅ | NO-002 | 2026-09-20 | 2026-09-20 | `test_migrate_check.py::test_downgrade_leaving_table_fails` và vài test DB khác hỏng ~1/7 lượt `coverage run -m pytest` | **Không phải rò trạng thái test.** Đường `verify-container → host.docker.internal:<cổng testcontainer>` thỉnh thoảng kẹt ~68 s rồi tự thông (đo: `socket.create_connection` 67,9 s rồi THÀNH CÔNG, Postgres rảnh 6/100 kết nối); asyncpg bỏ cuộc ở **trần 60 s mặc định của thư viện** — không file nào đặt trần tường minh (vi phạm R-24) — nên cổng kết tội nhầm bước migration bằng `TimeoutError()` trần | B0-03 (`packages/db/**`) | P1 | **FIX-002** — trần bắt tay tường minh: `db_connect_timeout_s=10` cho đường phục vụ request, `GATE_CONNECT_TIMEOUT_S=180` cho đường cổng (`engine.py`, `migrate_check.py`, `migrations/env.py`, `fixtures/db.py`). Chứng minh: 10/10 lượt test đó xanh, cả file xanh, `run.sh verify` thoát 0. Giới hạn: kẹt > 180 s vẫn đỏ → xem NO-007 |
| ➖ | NO-003 | 2026-09-20 | 2026-09-20 | `LocalDiskStorage`: object và `<key>.meta.json` là hai lần `os.replace`, giữa hai lần đó `stat` có thể trả `sha256` của bản trước | Khuôn lưu trữ tách metadata ra file riêng; không có API đổi tên hai file nguyên tử | B0-04 | P3 | Chấp nhận: chỉ là kho máy dev; staging/production dùng S3 nơi `put_object` gắn metadata trong cùng lượt ghi. Giới hạn đã ghi trong docstring `packages/storage/local.py`. Đổi ý thì phải nhúng metadata vào chính object (đổi khuôn lưu trữ) |
| ➖ | NO-004 | 2026-09-20 | 2026-09-20 | `S3Storage.list_prefix` gọi `stat` cho **từng** object (N+1) | `ListObjectsV2` của AWS không trả `x-amz-meta-*`, mà `ObjectInfo` hứa có `sha256`/`kind` | B0-04 | P2 | Chấp nhận: chỉ lịch dọn rác nền gọi. Nâng cấp khi thành điểm nóng: `list_prefix` trả `key` + `last_modified`, bỏ `stat` (~3 dòng, `packages/storage/s3.py:186`) |
| ➖ | NO-005 | 2026-09-20 | 2026-09-20 | `S3Storage._put_cors` dùng API riêng `Minio._execute` | `minio` 7.2.20 chưa phơi `set_bucket_cors` | B0-04 | Nit | Chấp nhận: gỡ khi nâng `minio` lên bản có API CORS công khai (`packages/storage/s3.py:227`) |
| ⬜ | NO-006 | 2026-09-20 | | Chưa có nơi khai `STORAGE_*`, `S3_*` cho dev/staging/production | Dự án cố ý không dùng `.env` (`env_file=None`, BE-00 §5); compose của app là việc của B0-08, `deploy/` mới chỉ có `verify.yml` | B0-08 (`deploy/**`) | P2 | mở — B0-04 chỉ khai biến trong `packages/storage/settings.py`, không tự tạo file dưới `deploy/` (K27) |
| ⬜ | NO-007 | 2026-09-20 | | Chặng `host.docker.internal` giữa container verify và testcontainers thỉnh thoảng kẹt ~68 s, làm cổng đỏ giả | Docker Desktop chuyển tiếp cổng qua host; FIX-002 chỉ nâng sức chịu lên 180 s chứ không bỏ được chặng này | B0-01 (`deploy/compose/verify.yml`, `tools/verify/*`) | P2 | mở — chữa dứt điểm: cho container verify và testcontainers dùng chung một docker network, hoặc khai Postgres thành service của `verify.yml` |
| ⬜ | NO-008 | 2026-09-20 | | `_clean_dir` vẫn `rmtree(..., ignore_errors=True)`: lỗi xoá **file** bên trong thư mục ra bị nuốt im lặng | Có từ trước FIX-001; `merge-heads` chép `*.py` nên có thể chép nhầm file cũ còn sót | B0-01 (`tools/verify/*`) | Nit | mở — duyệt và xoá từng mục con, để lỗi nổi lên |
