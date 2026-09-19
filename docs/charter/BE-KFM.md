# BE-KFM — Lỗi agent hay mắc

> **Bản 5 · 2026-09-17.** K13 theo tranh luận lô 4c: kiểm `w × h` tường minh, không gán biến toàn cục của Pillow.
>
> **Bản 4 · 2026-09-17.** Thêm K35–K37 theo tranh luận lô 4a phần 4 chặng 3.
>
> **Bản 3 · 2026-09-17.** K24 mở rộng theo tranh luận phần 3 chặng 3 (chú thích né cổng, file cấu hình riêng, test bị bỏ qua).
>
> **Bản 2 · 2026-09-17.** Đọc cùng `BE-00.md`. Thay đổi so với bản 1: sửa K02, K04, K06, K10, K11, K17, K24, K28 theo tranh luận phần 1 chặng 3; thêm K30–K34.
> Mỗi mục gồm: **Sai** (việc agent hay làm) · **Đúng** (cách làm) · **Bắt bởi** (cổng hoặc case sẽ đánh hỏng).
> Khối [9] của mỗi prompt trích lại những mục liên quan tới module đó, cộng lệnh cấm riêng của module.

## Hợp đồng với FE

**K01 — Thừa trường trong response.**
- Sai: trả thêm `ownerId`, `deletedAt`, `_links`… "cho đủ".
- Đúng: response kế thừa `WireModel` (BE-00 §3.1) và có **đúng** các trường của schema FE.
- Bắt bởi: H1 (zod `.strict()`), C01.

**K02 — Trả `null` thay vì vắng trường.**
- Sai: `{"areaM2": null}`.
- Đúng: `WireModel` bỏ trường `None`, trừ trường khai `KeepNull` (chỉ `AdminUser.lastActiveAt`, bắt buộc có khoá). **Cấm** `exclude_unset`: nó làm rơi cả trường bắt buộc.
- Bắt bởi: H1, C17.

**K03 — SSE có dòng `event:`.**
- Sai: `event: notification\ndata: …`.
- Đúng: chỉ `id:` + `data:`; heartbeat là `: ping` (W15).
- Bắt bởi: H5, S03.

**K04 — Vai thứ tư hoặc vai viết hoa trong payload refresh.**
- Sai: `roles: ["owner"]`, `"Admin"`.
- Đúng: đúng một trong `admin|engineer|viewer` (W16).
- Bắt bởi: H1 bằng schema refresh strict riêng trong `tools/contract` (schema FE là `.passthrough()` và lùi `roles` về `[]`, nên không bắt được thiếu `roles`), C01 của refresh.

**K05 — Tin người thực hiện trong thân.**
- Sai: lưu `actorId`, `creatorId` từ request.
- Đúng: lấy từ token (W18); trường đó trong thân bị bỏ qua (nếu FE gửi) hoặc 422 (nếu hợp đồng mới).
- Bắt bởi: C18.

**K06 — Đổi tên hay đường endpoint FE đang gọi cho "đẹp hơn".**
- Sai: `/api/floors` → `/api/levels`.
- Đúng: giữ đường trong `BE-BIND.md`; muốn đổi thì prompt phải ghi rõ và có F-xx đi kèm.
- Bắt bởi: H1 kiểm "mọi thao tác BE-BIND có trong OpenAPI", `kiem_bo_prompt.py`.

**K07 — Ghi có version mà không kiểm `baseVersion` trong cùng giao dịch.**
- Sai: đọc revision, so sánh trong Python, rồi mới `UPDATE`.
- Đúng: `UPDATE … WHERE revision = :base RETURNING …`; 0 dòng → 409 (W20).
- Bắt bởi: C09, C14.

## Quyền và bảo mật

**K08 — 403 cho người ngoài dự án.**
- Sai: kiểm vai trước, kiểm thành viên sau.
- Đúng: không phải thành viên → 404 `NOT_FOUND`; là thành viên nhưng thiếu quyền → 403.
- Bắt bởi: C06, C07.

**K09 — Kiểm quyền theo id trên đường nhưng làm theo id trong thân.**
- Sai: `require_project(path.p)` rồi `repo.get(body.projectId)`.
- Đúng: so id đường ↔ thân → 422 `PATH_BODY_MISMATCH`, rồi chỉ dùng id trên đường (W21).
- Bắt bởi: C21.

**K10 — Refresh xoay vòng không có ân hạn.**
- Sai: token cũ dùng lại là thu hồi ngay.
- Đúng: token kế tiếp tính tất định bằng HMAC; mọi lượt dùng lại trong 30 s đều nhận **cùng** cookie kế tiếp (lượt đầu có thể mất phản hồi); ngoài 30 s mới thu hồi họ phiên (BE-00 §5).
- Bắt bởi: C19, C20.

**K11 — Log bí mật.**
- Sai: log cả thân request đăng nhập, log header `Authorization`.
- Đúng: dùng bộ che log của `packages/core/logging.py` (B0-02, BE-00 §11).
- Bắt bởi: test che khoá của B0-02, soát B7-02.

**K12 — Nạp trọng số không an toàn.**
- Sai: `torch.load(file_người_dùng)`, nhận `.pt` người dùng tải lên, nạp trọng số gốc không kiểm SHA-256.
- Đúng: hai mức tin cậy (BE-00 §9).
- Bắt bởi: M02, M03.

**K13 — Giải nén hay đọc ảnh không giới hạn.**
- Sai: `zipfile.extractall()`; `Image.open()` không trần điểm ảnh.
- Đúng: chặn `..`, đường tuyệt đối, symlink; trần dung lượng và số file; đọc `w × h` từ đầu tệp so với trần tường minh trước `load()`, bắt `DecompressionBombError`; không gán `Image.MAX_IMAGE_PIXELS`.
- Bắt bởi: U03, B6-02b.

**K14 — Tin đuôi file và `Content-Type` client khai.**
- Sai: `if name.endswith(".png")`.
- Đúng: kiểm magic bytes khi nhận.
- Bắt bởi: U08.

**K15 — Phục vụ tệp người dùng như nội dung chạy được.**
- Sai: nginx mở thẳng thư mục upload; object không có `nosniff`.
- Đúng: BE-00 §8.
- Bắt bởi: soát B7-02, test của B0-04.

**K16 — URL ký sẵn sống ngắn hơn cache FE.**
- Sai: TTL 5 phút.
- Đúng: ≥ 60 phút (W23).
- Bắt bởi: test của B0-04.

## Dữ liệu và job

**K17 — Xếp hàng job trước khi commit.**
- Sai: `task.delay(id)` trong giao dịch; worker đọc không thấy bản ghi.
- Đúng: `on_after_commit(session, fn)` của `packages/db/hooks.py` (BE-00 §7).
- Bắt bởi: J09.

**K18 — Task không idempotent.**
- Sai: giao lặp là tạo phiên bản thứ hai, gửi thông báo thứ hai.
- Đúng: khoá nghiệp vụ duy nhất + kiểm "đã làm chưa" trong cùng giao dịch.
- Bắt bởi: J06, J10.

**K19 — Ghi mm giả.**
- Sai: không suy được tỉ lệ thì mặc định 1 mm/px và im lặng.
- Đúng: dùng tỉ lệ tạm **kèm** `SCALE_UNRESOLVED`; hình học px giữ làm artifact để tính lại.
- Bắt bởi: test B3-01, B5-05.

**K20 — Sai kiểu dữ liệu.**
- Sai: datetime không múi giờ; mm kiểu `float`; so email phân biệt hoa thường; lưu chuỗi chưa NFC.
- Đúng: BE-00 §6.
- Bắt bởi: W3, C16.

**K21 — Pipeline đè mục người đã duyệt.**
- Sai: ghi đè cả lớp bằng kết quả AI.
- Đúng: chỉ qua hàm trộn của B3-06.
- Bắt bởi: test B3-06, J06 của B5-06b.

## Quy trình và cổng

**K22 — "Lưu giả".**
- Sai: trả 200 mà không ghi bền vững; giữ dữ liệu trong biến module.
- Đúng: mọi ghi đi vào Postgres hoặc object storage trong request đó.
- Bắt bởi: test tích hợp đọc lại qua một session mới.

**K23 — Mock chính dịch vụ đang kiểm.**
- Sai: `AsyncMock` cho session DB trong test repository; `fakeredis` cho test rate limit.
- Đúng: Testcontainers thật; mock chỉ dùng cho phụ thuộc **ngoài** module đang kiểm.
- Bắt bởi: soát báo cáo của người điều phối.

**K24 — Qua cổng bằng cách né cổng.**
- Sai: `# pragma: no cover` hay `pragma: no branch`, `# type: ignore` không mã lỗi, hạ ngưỡng, `--no-verify`, xoá test đỏ, bỏ qua test (có lý do hay không), thêm `.coveragerc`/`pytest.ini`/`ruff.toml`/`conftest.py` lồng để đổi luật, gắn `gpu` cho test khó.
- Đúng: viết test; `# type: ignore[mã]` chỉ khi thư viện ngoài thiếu stub, kèm chú thích lý do; `# noqa: <MÃ>` kèm lý do khi prompt bắt dùng đúng API mà luật cờ (vd `S311` cho dữ liệu tất định, `S314` sau khi đã chặn DTD bằng byte). `# noqa` trần bị cấm.
- Bắt bởi: ruff `PGH003`; `coverage_gate.py` hỏng khi gặp chú thích né cổng, file cấu hình riêng, hay junit có test bị bỏ qua (BE-00 §12); người điều phối chạy lại verify.

**K25 — Báo "đạt" cho bước chưa chạy.**
- Sai: bảng cổng ghi "đạt" cho migration khi Docker không lên.
- Đúng: E.10, ghi "chưa chạy" kèm lý do.
- Bắt bởi: người điều phối chạy lại `just verify` khi hợp nhất.

**K26 — Không commit, hoặc commit file chung.**
- Sai: báo xong khi còn thay đổi chưa commit; commit `openapi.json`, `uv.lock` sửa tay, sửa `docs/charter/*`.
- Đúng: BE-00 §13.
- Bắt bởi: người điều phối từ chối hợp nhất.

**K27 — Sửa file của prompt khác.**
- Sai: "tiện tay" sửa router, model hay migration của module khác.
- Đúng: ghi vào "Nợ và việc chưa làm"; người điều phối giao FIX cho đúng chủ.
- Bắt bởi: diff ngoài cột "Sở hữu" khi hợp nhất.

**K28 — Việc nặng đồng bộ trong request.**
- Sai: chạy nắn ảnh 20 s trong handler.
- Đúng: > 15 s → job + 202 (W11).
- Bắt bởi: test đo thời gian của prompt.

**K29 — Kéo `opencv-python` bản GUI vào ảnh.**
- Sai: `uv add rapidocr-onnxruntime` để nó tự kéo phụ thuộc.
- Đúng: cài `--no-deps` và khai phụ thuộc thật; chỉ `opencv-python-headless` (ENV §3).
- Bắt bởi: bước import của job `ml`.

## Bổ sung sau tranh luận phần 1 chặng 3

**K30 — Trả 401 cho lỗi nghiệp vụ.**
- Sai: sai mật khẩu hiện tại → 401.
- Đúng: 401 chỉ dành cho token/phiên (W10); lỗi nghiệp vụ dùng 422. Mọi 401 còn lại sau refresh làm FE đăng xuất **mọi thẻ** (`src/lib/http/client.ts:436-461`).
- Bắt bởi: C25, test của N13.

**K31 — Kiểm `Origin` ở GET luồng.**
- Sai: `/api/streams/*` đòi header `Origin`.
- Đúng: trình duyệt không gửi `Origin` cho GET cùng origin; chỉ kiểm cho phương thức ghi dùng cookie (BE-00 §5).
- Bắt bởi: S09 ("GET không có `Origin` vẫn mở được").

**K32 — Phát lại hoặc gửi trùng thông báo.**
- Sai: nối lại luồng thông báo thì phát lại N thông báo chưa đọc; XADD lại khi task được giao lặp.
- Đúng: FE không khử trùng (`src/screens/system/NotificationCenter/useNotificationCenter.ts:491-494`); mỗi thông báo XADD đúng một lần, luồng thông báo không có ảnh chụp.
- Bắt bởi: J10, S02.

**K33 — Đặt `endedAt` cho lượt pipeline hỏng.**
- Sai: `status:"failed"` kèm `endedAt`.
- Đúng: `endedAt` chỉ khi `completed`; FE coi có `endedAt` là xong mọi bước (BE-BIND §4).
- Bắt bởi: golden H1 nhánh `failed`.

**K34 — Tin vai trong JWT, hoặc dùng chord.**
- Sai: đọc vai từ claim; `chord(group(...), build.s())` để điều phối pipeline.
- Đúng: vai lấy từ DB/cache mỗi request (C25); pipeline điều phối bằng trạng thái trong DB, `task_ignore_result=True` (BE-00 §7).
- Bắt bởi: C25; test điều phối của B5-06a, B5-06c.

## Bổ sung sau tranh luận lô 4a (phần 4 chặng 3)

**K35 — Refresh xoay lần hai trong ân hạn, hoặc thu hồi phiên vì token lạ.**
- Sai: mỗi lượt refresh đều xoay; token không khớp hash nào là thu hồi cả phiên.
- Đúng: thuật toán BE-00 §5 — trong 30 s sau lần xoay không xoay nữa; kiểm thu hồi/hết hạn trước; token lạ chỉ thu hồi khi chuỗi HMAC ≤ 32 bước chạm `current`, còn lại 401 không ghi DB.
- Bắt bởi: C19 (chuỗi xoay), C20, test "token rác không thu hồi phiên".

**K36 — Giữ kết nối DB trong lúc chờ việc chậm.**
- Sai: `SELECT` người dùng rồi `await` băm argon2, chờ semaphore, hay xử lý ảnh khi session của request còn giữ kết nối; generator SSE dùng session của request.
- Đúng: chưa ghi gì thì `await db.rollback()` trước khi chờ; việc CPU chạy trên executor riêng có trần; luồng dài dùng session ngắn riêng (BE-00 §5, §7).
- Bắt bởi: test "N lượt đăng nhập song song với `DB_POOL_SIZE` nhỏ", test `pool.checkedout() == 0` khi nhiều luồng SSE mở. Test pool nhỏ luôn đặt `DB_POOL_SIZE=1`, `DB_MAX_OVERFLOW=0`, `DB_POOL_TIMEOUT_S=1` và khẳng định `engine.pool.checkedout() == 0` trong lúc việc chậm đang chặn.

**K37 — Email ngoài mẫu FE.**
- Sai: `EmailStr`, hoặc chép regex zod mà quên `re.ASCII` (Python với `re.I` nhận `ſ`, `K`), rồi lưu email Unicode.
- Đúng: `validate_wire_email` của B1-01 (BE-00 §5); một email hỏng làm màn quản trị người dùng hỏng giải mã cả danh sách.
- Bắt bởi: test tham số hoá `ſ`, `K`, `İ`, `ı`, `admin@localhost` → 422; H1.
