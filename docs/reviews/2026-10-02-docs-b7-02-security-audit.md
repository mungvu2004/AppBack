# Review merge docs/b7-02-security-audit → main

- Ngày: 2026-10-02 · Reviewer: phiên /merge-review (độc lập, lượt 1) · Commit đầu nhánh: `3e431edada86`
- Phạm vi diff (`git diff main...HEAD`): `changes/B7-02.md`, `docs/security/{README,asvs-checklist,threat-model}.md`, `docs/security/fixes/SEC-{020,040,041,042,043,060,061,062}.md` — 12 tệp, +841, không tệp nào ngoài phạm vi (`grep -v` thoát 1). Cây sạch; 16 commit không merge đều `docs(security): …` + trailer `Prompt: B7-02`; không `pragma`/`type: ignore`/`skip`/`xfail` mới.
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1, lượt 1) — không chạy lại theo lệnh điều phối, đọc log:
  - cổng 1, sha soát `2a63cfc5420f` (`P/gate.sha`): `P/gate-1.log` — 8 bước + 0 + 5b `đạt`, `7868 passed` (dòng 383), `mã thoát: 0` (dòng 523–524).
  - cổng 2, sha nhánh `3e431edada86` (`M/gate.sha`): `M/gate-2.log` — **chưa chạy — hạ tầng** (Docker Desktop sập vì RAM). `gate-2.log`: bước 0–4 `đạt`, bước 5 `đạt` (`7868 passed` dòng 390, `coverage_gate: đạt` :397, tổng 99,45 % / 97,89 % :395), 5b `case_gate: đạt` (:486); bước 6 `migrate_check` → `unexpected EOF`, `mã thoát (run.sh): 125` → bước 6–8 `chưa chạy`. `gate-2c.log`: pytest tới 99 % rồi `unexpected EOF`, `mã thoát (run.sh): 125`. `gate-2b.log` (chỉ bước 6–8): 6 `đạt`, 7 `hỏng` với `H1 0 mẫu response`/`H5 0 khung SSE` — hệ quả của việc chạy bước 7 không có bước 5 (mẫu golden do test C01 ghi), không phải bằng chứng về mã; 8 `chưa chạy`. Nhánh chỉ đổi tài liệu, cây mã = `096e870` = cây của cổng 1 → bằng chứng "test đạt" của kiểm toán dựa cổng 1; cổng 3 phải xanh trước merge
- Độ phủ (cổng 1): tổng dòng 99,45 % · nhánh 97,89 %; tập file bị chạm 100/100 (nhánh chỉ đổi tài liệu).

## Tự kiểm (không tin báo cáo)

- **Test dẫn (K25):** 131 nodeid trích từ checklist đối chiếu `P/collect.txt` (7868 dòng): 125 khớp nguyên văn; 6 lệch chỉ do regex (thoát `\u…`/khoảng trắng) và đều có trong `collect.txt`; `test_safe_extract_rejects_unsafe_names` là test tham số (6 biến thể). 15 ký hiệu rút gọn `…::` (S09, telemetry Origin, pinned, workflows, refresh chain, C26_expired, `[worker]`…) đều có 1 dòng.
- **Fixture V2/V3/V4:** `test_login.py:159` `auth_client`; `test_refresh.py:423-433` dựng `create_app(get_core_settings(), …)` thật; `probe_client` = `build_probe_app` "verifier thật (không tiêm)" (`packages/testing/fixtures/auth.py:120-137`); trúng `api_client` trong bốn tệp auth/access chỉ là `make_api_client` (bọc app thật), không `api_app`/`grant_stub`/`fake_principal`/`dependency_overrides`. A-19, A-21, A-23 tự loại test `api_client` và dựa thăm dò `A/probe-1.log` — đúng [6].2.
- **`file:dòng`:** 27 trích dẫn `git show 2a63cfc5420f:<file> | sed -n` đều khớp (artifacts.py:73-76, step_done.py:138-141, gpu.py:140-149, training_runner/tasks.py:73-75, ml_eval/tasks.py:133-140, passwords.py:40-44/120-130, auth/settings.py:21,33-36, origin.py:44-62, ba router admin_ml :27/:30/:31, routing.py:136-148, storage/local.py:196-210, core/settings.py:14-19/56-67, env.example:8, logging.py:43-47, backup.sh:82-88, error_413/503_body.conf, notify.yml:8-25, port.py:154-157, middleware.py:46-52, streams/settings.py:34-35, archive.py:115-120).
- **`SEC-*`:** 8 khối đủ 7 mục, dòng đầu đúng mẫu; chủ tự kiểm bằng `git log --diff-filter=A` + trailer: training_runner (B6-03b), backup/notify (B0-10 `7f36f79`), core settings/logging (B0-02 `14ceca2`), `.gitleaks.toml` (B0-09 `55f75bc`), nginx snippets (B0-08), training_segformer (B6-04a) — khớp. Hai chiều SEC ↔ `lỗ`: 8 ↔ 8. Tự tái hiện 5 khối bằng grep trên `2a63cfc5420f`: SEC-062 (`HF_HUB_OFFLINE` chỉ ở `BE-00.md:407`), SEC-040 (`umask|chmod|UMask` ở `deploy/backup` thoát 1), SEC-061 (`environment` ở `notify.yml` thoát 1), SEC-041 (không chặn `change-me` trong `packages/core/settings.py`), SEC-020 (`Popen` không `env=`); SEC-060 đọc hai snippet: chỉ `X-Request-Id`/`Retry-After`.
- **[8]:** gitleaks cả lịch sử (C/L-01, thoát 1, 11 phát hiện → SEC-043); quét route (D/L-01, 86 op, 12 công khai); grep đủ 18 mẫu (B/L-01…19, thêm `subprocess`); thăm dò A/B/C/D có lệnh + mã thoát 0. Không bí mật thật trong tài liệu (grep `eyJ…|AKIA|BEGIN|ghp_|Bearer <chuỗi>` 0 trúng; mật khẩu thăm dò là giả).
- **case_gate:** 9 thao tác thiếu C16 trong bảng (`floors_delete_floor`, …, `versions_restore_version`) đều miễn hợp lệ bằng `waive = { C16 = … }` trong `cases.toml` (CASE §2.3 chỉ cho miễn C16) — D-28 đúng.
- **Mô hình đe doạ:** 17 ranh giới, mỗi ranh giới đủ S T R I D E; mọi `#` dẫn tới tồn tại trong checklist; ba lỗ có chủ ý của v1 ở "Rủi ro tồn dư" kèm chủ.
- **Bỏ sót (tự dò 3 chỗ):** `streams_open_progress` (public, kiểm thành viên **và** `UploadRow.project_id == project_id` trong `drawings/stream_providers.py:37-63`); `drawings_upload_chunk` (`load_upload` lọc `project_id`, `uploads.py:127-146,291`); `measurements_delete_record` (lọc `MeasurementRow.project_id`, `service.py:141-155`). Không thấy lỗ mới chưa có `SEC-*`.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P1 | LOG-06 ([11].2) | Bảng `chưa kiểm` theo nhóm gộp hai nhóm của khối [6] — "Giao tiếp, cấu hình (V9, V14)" và "Giấy phép (V14)" — thành một dòng 7/14 = 50 % (không > 50 %). Tách đúng: **Giấy phép = D-24, D-25 → 2/2 = 100 % `chưa kiểm`** > 50 %, nên dòng đầu README phải là `kiểm toán chưa đủ`; hiện là `# Kiểm toán bảo mật B7-02`. Bảng chỉ có 9 dòng cho 10 nhóm. Tiêu chí nghiệm thu [11].2 không đạt và tài liệu báo mức hoàn tất cao hơn thật | `docs/security/README.md:1`, `:40` | Tách bảng đúng mười nhóm của [6] (Giấy phép 2/2 100 %; Giao tiếp 12 mục, 5 `chưa kiểm` — hay 11/4 nếu D-13 về nhóm chuỗi cung ứng, xem #4); đổi dòng đầu README thành `kiểm toán chưa đủ` (ví dụ `# Kiểm toán bảo mật B7-02 — kiểm toán chưa đủ`) và ghi nhóm vượt ngưỡng vào báo cáo cho người điều phối |
| 2 | P2 | R-27 ([6].4) | `SEC-061` giao B0-10 nhưng [6] đặt test chặn tái phát vào `tools/ci/tests/test_workflows.py` — tệp của **B0-09** (`55f75bc`, trailer `Prompt: B0-09`); [4] không liệt kê tệp test. Worker FIX của B0-10 phải sửa tệp của chủ khác (K27) hoặc không có chỗ đặt test | `docs/security/fixes/SEC-061.md:15-22` | Dùng tệp test của chính B0-10: `deploy/scripts/tests/test_workflow_notify.py` (`7f36f79`, `Prompt: B0-10`) → `…::test_notify_workflow__secret_only_from_environment`, và thêm tệp đó vào [4] |
| 3 | P2 | LOG-06 ([2] "không bịa mã") | `mã ASVS` sai nghĩa với câu kiểm: B-28 "con `ml_eval` chạy trọng số không tin trong hộp hạn chế" ghi `12.1.1` (V12.1.1 = không nhận tệp lớn làm đầy kho/DoS); B-27 "định dạng, băm, không nạp ở API" ghi `12.1.1` trong khi ý chính là loại theo nội dung (V12.2.1) | `docs/security/asvs-checklist.md:110`, `:111` | B-28 → `—` (luật [2]: không chắc → `—`); B-27 → `12.2.1` hoặc `—` |
| 4 | P3 | LOG-06 | Xếp nhóm lệch khối [6], làm sai số `chưa kiểm` theo nhóm: C-22 (`compare_digest`, K16) ghi chương V11 nên đếm vào "Giới hạn, API" trong khi [6] đặt ở "Dữ liệu, bí mật (V6, V8)"; D-13 (`/metrics`) đếm vào "Giao tiếp" trong khi [6] đặt ở "Chuỗi cung ứng, triển khai" | `docs/security/asvs-checklist.md:81`, `:130`; `docs/security/README.md:33-43` | Khi tách bảng ở #1, đếm theo nhóm của [6] chứ không theo chương (C-22 → Dữ liệu, D-13 → Chuỗi cung ứng); có thể đổi chương C-22 thành V6 |
| 5 | P3 | R-27 | `SEC-043` [5] đưa phương án "chủ các test thêm `# gitleaks:allow`" — sửa tệp test của nhiều prompt khác, trái chính [4] của khối ("CẤM sửa: file test của các prompt khác") | `docs/security/fixes/SEC-043.md:20-24` | Bỏ phương án đó khỏi [5] (đã có ở "Nợ hiến chương" C.7) |
| 6 | Nit | — | (a) `SEC-041` mức `trung bình` không ghi lý do vì sao không `nghiêm trọng` (khoá mẫu cho phép ký access token không cần đăng nhập, điều kiện: vận hành giữ nguyên `env.example`); (b) `SEC-060` [4] không liệt kê `deploy/tests/test_nginx.py` dù [6] đặt test ở đó (cùng chủ B0-08); (c) B-22 `7.1.1` (thông tin xác thực trong log) chỉ phủ một phần câu kiểm "đường dẫn, biến môi trường"; (d) B-08 dẫn test tham số không kèm id | `fixes/SEC-041.md:2`, `fixes/SEC-060.md:16-17`, `asvs-checklist.md:50`, `:104` | Thêm một câu lý do mức; liệt kê tệp test vào [4]; cân nhắc `—` cho B-22 |

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 1 | 0,15 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 3 | 0,21 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |

Tổng: **4,23 / 5**

## Nợ nên ghi (`DEBT.md`, người điều phối — nhánh không được sửa)

- Tám `SEC-*` theo chủ: B6-03b (020), B0-10 (040, 061), B0-02 (041, 042), B0-09 (043), B0-08 (060), B6-04a (062) — mỗi khối một dòng `NO-*` cho tới khi cấp `FIX-*`.
- Nợ hiến chương A1 (MFA admin), B (env con huấn luyện, công bằng hàng ML, Redis ACL), C1–C8, D (header lỗi nginx, chỗ đặt `HF_HUB_OFFLINE`, ngưỡng trivy/secret Environment, giấy phép tới phiên bản kích hoạt).
- 18 mục `chưa kiểm — thiếu ảnh` (phương án (a)): lượt kiểm bù qua nginx/`prod.yml` khi có ảnh `appback-*`.

## PHÁN QUYẾT: REQUEST CHANGES

Một P1 chưa waiver: bảng `chưa kiểm` theo nhóm gộp hai nhóm của khối [6] nên che mất nhóm "Giấy phép" 100 % `chưa kiểm`; theo [11].2 dòng đầu README phải là `kiểm toán chưa đủ`. Nội dung kiểm toán còn lại vững: test dẫn đều có trong `collect.txt`, fixture V2–V4 đúng luật, `file:dòng` lấy mẫu khớp, 6/8 `SEC-*` tự tái hiện (5 bằng grep, SEC-060 bằng đọc snippet), cả 8 giao đúng chủ (trừ test của SEC-061), STRIDE đủ. Để được duyệt: (1) sửa #1 — tách bảng đúng mười nhóm, dòng đầu `kiểm toán chưa đủ`; (2) sửa #2 — test của SEC-061 vào tệp của B0-10 và liệt kê ở [4]; (3) sửa #3 — mã ASVS của B-27/B-28. #4, #5, Nit nên sửa cùng lượt. Cổng trên sha nhánh chưa hoàn tất (cổng 2 `chưa chạy — hạ tầng`), nên trước merge cần một cổng đầy đủ xanh trên sha của vòng sửa (cổng 3); lượt 2 soát diff vòng sửa + `gate-3.log`.
