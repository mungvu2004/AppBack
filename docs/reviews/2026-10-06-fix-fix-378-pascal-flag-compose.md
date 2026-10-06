PHÁN QUYẾT: REQUEST CHANGES (tạm — chờ log cổng `gate-X1.log`; nếu `APPFRONT_SHA` được nâng ≥ efbda6bd cùng đợt gộp thì xem §Hai trường hợp)

# Review merge fix/fix-378-pascal-flag-compose → main

- Ngày: 2026-10-06 · Reviewer: phiên /merge-review (lượt 1, soát mã) · Commit đầu nhánh: `ee08803abae2` · so với `main` `a79e7c97b233`
- Lưu ở: `docs/reviews/2026-10-06-fix-fix-378-pascal-flag-compose.md` (điều phối commit)
- Cổng: phạm vi **đầy đủ** (lượt 1, R-33b đk 1; diff chạm compose/Dockerfile/nginx/openapi) — **chưa chạy**, điều phối chạy một lần, log `F:/App/AppBack/backend/dieu-phoi/chay/F-14/gate-X1.log` (chưa tồn tại lúc review). Bằng chứng phụ của worker (chưa phải cổng): `X-kiem.log` — `verify --steps 1,2,3,4` `VERIFY exit 0` (4 bước đạt); pytest `apps/api/telemetry` + `deploy/tests` 264 passed `pytest exit 0`.
- Độ phủ: **không đo** (chờ cổng). Số worker (`X-kiem.log`, chỉ `apps/api/telemetry/*`): dòng 275/278 = 98,9 % · nhánh 73/76 = 96,1 % — chưa tự kiểm, không dùng làm bằng chứng cổng.

## Phạm vi diff
14 tệp, +71/−14, 1 commit. Dòng đầu đúng mẫu (`fix(telemetry): …`, 70 ký tự), trailer `Prompt: FIX-378` có. Cây sạch. `changes/FIX-378.md` có. Không chạm `docs/charter/*`, `tools/contract/APPFRONT_SHA`, `uv.lock`; `docs/contracts/openapi.json` đổi đúng theo spec (chỉ `FeatureFlagsOut`: mô tả "6 khoá" + thuộc tính `scene.pascal-viewer` `bool|null`). Không pragma/noqa/type: ignore/skip mới.

## Đã tự kiểm (không tin báo cáo)
- **`${FEATURE_FLAGS:-{}}`**: `docker compose config` thật — không đặt biến → `'{}'`; `FEATURE_FLAGS='{"scene.pascal-viewer": true}'` → nguyên JSON, không dính `}` thừa. Đúng.
- **`ML_BACKEND` chỉ ở `ci.yml`** — lập luận worker ĐÚNG: `prod.yml:7-19` ghi rõ `environment:` (kế thừa base) ĐÈ `env_file:`; `ml.env.example:15` giữ `ML_BACKEND=onnx` làm khoá của `/etc/appback/ml.env`. Đặt ở `base.yml` (kể cả `${ML_BACKEND}` không mặc định) sẽ đè `ml.env` bằng giá trị của `appback.env`/rỗng → prod lặng lẽ bỏ cấu hình ml.env. `ci.yml` merge map `environment` qua `extends` — test `test_compose_ml_backend_and_feature_flags_wired` khẳng định trên dịch vụ đã giải `extends`; `chuoi-2.log:122-123` quan sát `fake` trong `ml`.
- **`FEATURE_FLAGS` ở `base.yml` cho `api`**: đúng sơ đồ prod (`--env-file appback.env` dùng chung cho nội suy) — giá trị đặt trong `appback.env` tới container. Hợp đồng B0-08 §2 (`base.yml:1-4`) chỉ cấm ports/depends_on/profiles/image/build/container_name — `environment` được phép.
- **nginx**: `location = /assets/pascal/pascal-mount.js` khớp chính xác ưu tiên hơn prefix `/assets/`, có `include security_headers.conf` (CSP/HSTS… không mất vì `add_header` cấp con), `try_files $uri =404`, `Cache-Control "no-cache" always`; test nginx khẳng định cả ba. `chuoi-2.log:129-131` quan sát `Cache-Control: no-cache`.
- **`APPFRONT_SHA` = `9cf0b0bf`** (F-00c) trên `main`; FE @ 9cf0b0bf: `package.json` `"build": "tsc && vite build"`, không có `vite.pascal.config.ts`, không có `vendor/`, `flags.ts` 5 khoá. FE @ `efbda6bd` (ảnh dùng cho chuỗi F-14): `"build": "pnpm pascal && tsc && vite build"`, `flags.ts` **6 khoá có `scene.pascal-viewer`**.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | OPS / R-19 | `test -f dist/assets/pascal/pascal-mount.js` làm **hỏng dựng ảnh `web` ở CI và deploy** khi `APPFRONT_SHA` còn `9cf0b0bf`: `tools/ci/job.sh:445-447` (`job_build`) và `.github/workflows/deploy.yml:83-89` xuất AppFront đúng sha ghim; tại 9cf0b0bf `pnpm build` không chạy bước pascal (không `vite.pascal.config.ts`) nên tệp không tồn tại → `RUN` thoát 1. Chuỗi F-14 xanh chỉ vì `build-images.sh`/`chuoi.sh` dựng từ `efbda6bd`, không phải sha ghim. Cổng `run.sh verify` không dựng ảnh web nên **cổng xanh vẫn không bắt được lỗi này**. | `deploy/docker/web.Dockerfile:17` | (a) nâng `tools/contract/APPFRONT_SHA` ≥ `efbda6bd` trước/cùng đợt gộp (việc của điều phối), **hoặc** (b) bỏ dòng `test -f …pascal-mount.js` khỏi nhánh này, mở dòng DEBT "thêm lại khi nâng APPFRONT_SHA". Khối nginx giữ được (vô hại, `=404` khi thiếu tệp). |
| 2 | P2 | API / R-34 | Hiến chương `HOP-DONG-MOI.md:505-512` vẫn ghi `FeatureFlagsSchema` "object **strict**, **5** khoá" — **không** khai `scene.pascal-viewer` (spec-X §1 nói "`HOP-DONG-MOI.md:511` đã khai khoá" là sai). BE nay 6 khoá; FE @ sha ghim là `.strict()` 5 khoá (`src/api/schemas/featureFlags.ts:29-36` @ 9cf0b0bf) → khi `FEATURE_FLAGS` bật khoá này, schema FE ghim từ chối response. Lệch hiến chương không có dòng DEBT. | `apps/api/telemetry/flags.py:24`, `schemas.py:21` | Điều phối: cập nhật `HOP-DONG-MOI.md` §7.3 (6 khoá) theo luật sửa hiến chương (người dùng duyệt câu chữ, trailer `Charter-Approved`) **hoặc** mở dòng `NO-` ghi lệch; không cần sửa mã nhánh. |
| 3 | P2 | TEST / R-34 | Test gương bị nới vĩnh viễn: `fe ⊆ be` và `be − fe ⊆ {scene.pascal-viewer}` — không còn bắt FE thêm/bỏ khoá theo chiều BE thừa; không có dòng DEBT ghi "trả lại `==` khi nâng sha". | `apps/api/telemetry/tests/test_flags.py:26-31` | Nếu nâng sha ≥ efbda6bd: trả lại `assert set(fe_keys) == set(FEATURE_FLAG_KEYS)` **trong cùng đợt** (FE @ efbda6bd đã 6 khoá, so `==` xanh). Nếu chưa nâng: giữ bản nới + dòng `NO-` có điều kiện đóng. |
| 4 | P3 | MNT / R-02 | Docstring test khẳng định "FE chưa thêm khoá vào `flags.ts`, chỉ có ở `schemas/featureFlags.ts`" — sai với FE hiện tại (`efbda6bd:src/lib/telemetry/flags.ts:92` có khoá); chỉ đúng ở sha ghim. | `apps/api/telemetry/tests/test_flags.py:27-28` | Ghi đúng nguyên nhân: "FE @ `APPFRONT_SHA` 9cf0b0bf chưa có khoá" — hoặc biến mất cùng #3. |
| 5 | Nit | R-27 | `apps/api/telemetry/settings.py` ngoài whitelist spec-X §4 — chỉ đổi docstring "5→6 khoá", cùng module telemetry, spec §2.1 yêu cầu "mọi chỗ đếm khoá". Chấp nhận. | `apps/api/telemetry/settings.py:31` | Không cần sửa. |
| 6 | Nit | OPS | `dev.yml` `ml` không nhận `ML_BACKEND` → dev compose không chọn được `fake`. Ngoài phạm vi spec (F-14 dùng ci). | `deploy/compose/dev.yml:146` | Thêm khi dev cần. |

## Hai trường hợp `APPFRONT_SHA` (điều phối đang hỏi người dùng)
- **Giữ `9cf0b0bf`** → **REQUEST CHANGES**: #1 là P1 thật (CI `job_build` + deploy hỏng). Để duyệt: bỏ dòng `test -f …pascal-mount.js` ở `web.Dockerfile:17` (hoặc nâng sha), mở dòng DEBT cho #2, #3 (+ dòng "thêm lại `test -f` khi nâng sha"); sửa docstring #4. Lượt 2 phạm vi đích (Dockerfile + test_flags), trừ khi chạm điều kiện đầy đủ.
- **Nâng ≥ `efbda6bd`** (commit nâng sha vào `main` trước hoặc cùng đợt với nhánh này) → #1 hết. Còn phải: trả lại `==` cho test gương (#3, #4 tự hết), xử lý #2 (sửa hiến chương hoặc dòng DEBT). Khi đó, nếu cổng đầy đủ (gồm bước 8 hợp đồng chạy với sha mới) thoát 0 → **APPROVE WITH COMMENTS** (P2 #2 có dòng DEBT) hoặc **APPROVE** (hiến chương đã sửa). Lưu ý: nâng sha có thể kéo theo lệch hợp đồng khác ở bước 8 — ngoài phạm vi FIX-378, phải đọc từ log cổng.

## Điểm (trạng thái hiện tại, sha giữ nguyên)
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 3 | 0,30 |
| TEST | 7% | 3 | 0,21 |
| OBS, OPS | 5% | 1 | 0,05 |
| MNT | 3% | 4 | 0,12 |

Tổng: **4,43 / 5** — nhưng có P1 chưa waiver → ma trận ra REQUEST CHANGES.

## PHÁN QUYẾT: REQUEST CHANGES (tạm)
Mã telemetry, compose, nginx đúng và lập luận `ML_BACKEND` chỉ ở `ci.yml` đứng vững (đã tự kiểm nội suy compose và thứ tự đè env_file). Chặn duy nhất là #1: dòng `test -f dist/assets/pascal/pascal-mount.js` biến bản dựng ảnh `web` theo `APPFRONT_SHA` ghim (CI `job_build`, `deploy.yml`) thành đỏ — cổng `run.sh verify` không dựng ảnh web nên sẽ không thấy. Điều kiện duyệt: hoặc nâng `APPFRONT_SHA` ≥ efbda6bd (kèm trả `==` cho test gương), hoặc bỏ dòng `test -f` đó; cộng dòng DEBT/sửa hiến chương cho #2 (và #3 nếu giữ sha); và log cổng đầy đủ `gate-X1.log` thoát 0 với độ phủ ≥ 90/90 cho gói chạm. Phán quyết chốt sau khi đọc log cổng.
