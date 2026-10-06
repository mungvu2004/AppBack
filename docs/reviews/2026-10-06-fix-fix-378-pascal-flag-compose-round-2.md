PHÁN QUYẾT: REJECT (thủ tục, merge-review §2 — hiến chương lẫn trong commit mã, thiếu `Charter-Approved`); mã + cổng: đạt, sẽ APPROVE ngay khi tách hiến chương

# Review merge fix/fix-378-pascal-flag-compose → main — lượt 2

- Ngày: 2026-10-06 · Reviewer: phiên /merge-review (lượt 2) · Commit đầu nhánh: `0e7edc4ef14e` (2 commit trên `main` `a79e7c97b233`: `ee08803`, `0e7edc4`)
- Lưu ở: `docs/reviews/2026-10-06-fix-fix-378-pascal-flag-compose-round-2.md` (điều phối commit)
- Cổng: phạm vi **đầy đủ** (diff vòng sửa chạm `APPFRONT_SHA` → bước 7 hợp đồng FE và Dockerfile, R-33b) — `run.sh verify` tại sha `0e7edc4ef14e95049c8cfb945db40d14942a4ef5` (dòng 1 log, khớp đầu nhánh), **mã thoát 0** (log `F:/App/AppBack/backend/dieu-phoi/chay/F-14/gate-X1.log:672`; bản gốc `.cache/src-out/verify/20261006T131329Z-0e7edc4ef14e.log`). Bảng E.10: bước 0–8 và 5b đều `đạt`; pytest 8411 passed; `case_gate: đạt`; bước 7 H1/H3/H4/H5 đạt với FE @ `8c28ef96` → không có lệch hợp đồng FE mới.
- Độ phủ (log cổng `coverage_gate`): tổng dòng **99,48 %** · nhánh **98,03 %**; `apps/api/telemetry` 98,92 % / 96,05 %; `tools` 98,90 % / 96,46 %; tập file bị chạm 100 % / 100 %.

## Phạm vi diff vòng sửa (`git diff ee08803..0e7edc4`)
8 tệp, +18/−14: `tools/contract/APPFRONT_SHA` 9cf0b0bf → `8c28ef961eee32e55d652f76dc042b323b3e81ce`; `test_flags.py` về `==`; `docs/charter/HOP-DONG-MOI.md` §7.3 thêm khoá thứ 6; `web.Dockerfile` bỏ `pnpm draco`; `dev.yml` `ML_BACKEND`; `test_compose.py`, `test_dockerfiles.py`, `changes/FIX-378.md`. Cây sạch. Dòng đầu cả 2 commit đúng mẫu, trailer `Prompt: FIX-378` có. Không pragma/noqa/skip mới.

## Finding lượt 1 — đã tự kiểm
| # lượt 1 | Trạng thái | Bằng chứng |
|---|---|---|
| 1 P1 `test -f pascal-mount.js` hỏng dựng web ở sha ghim | **Đóng** | `APPFRONT_SHA` = `8c28ef96` (thuộc `origin/e2e/integrate`); tại sha này `package.json:8` `"build": "pnpm pascal && tsc && vite build"`, `vite.pascal.config.ts:65,72` xuất `public/assets/pascal/pascal-mount.js`. |
| 2 P2 hiến chương 5 khoá | **Đóng về nội dung**, nhưng sai thủ tục → finding mới #A | `HOP-DONG-MOI.md` §7.3 6 khoá; khớp FE @ 8c28ef96 `src/api/schemas/featureFlags.ts:34,37` (strict, có `scene.pascal-viewer`); trích `flags.ts:86-93` đúng (86 mở mảng, 92 khoá mới, 93 đóng). |
| 3 P2 test gương nới | **Đóng** | `test_flags.py:29` `assert set(fe_keys) == set(FEATURE_FLAG_KEYS)`; FE @ 8c28ef96 `flags.ts:86-93` 6 khoá; cổng bước 5 xanh. |
| 4 P3 docstring sai | **Đóng** | docstring mới mô tả đúng phép so. |
| 5 Nit `settings.py` ngoài whitelist | Chấp nhận (như lượt 1) | chỉ docstring. |
| 6 Nit `dev.yml` thiếu `ML_BACKEND` | **Đóng — chấp nhận dù ngoài whitelist ban đầu** | `dev.yml:157-158` cùng mẫu `ci.yml`, cùng họ compose B0-08 mà whitelist đã mở (`base.yml`, `ci.yml`, `env.example`); dev không có `env_file` ml.env nên không đè gì; `test_compose.py:481-484` khẳng định cả `dev` và `ci`. |

Thêm: bỏ `pnpm draco` — FE @ 8c28ef96 `scripts/copy-pascal-assets.mjs:50` `import './copy-draco.mjs'` (tác dụng phụ chép bộ giải vào `public/draco/`), `pascal:assets` chạy trong `pnpm build`; `test -f dist/draco/draco_decoder.wasm` vẫn giữ nên nếu sai thì build đỏ rõ ràng. `test_dockerfiles.py` cập nhật đúng.

## Finding mới
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| A | **§2 dừng sớm** | merge-review §2 / BE-00 §2 | Commit `0e7edc4` chạm `docs/charter/HOP-DONG-MOI.md` **cùng** `.py` (`test_flags.py`, `test_compose.py`, `test_dockerfiles.py`) và `tools/contract/APPFRONT_SHA`, **không** có trailer `Charter-Approved:`. Luật: mọi commit chạm `docs/charter/*` chỉ chạm tài liệu và mang `Charter-Approved: <bản duyệt có thật>` — tiền lệ `56cfdd6`, `815e4a0`, `dfba078`. Squash merge sẽ gộp cả vào một commit mã → không thể thoả luật sau khi gộp. Spec-X2 ghi người dùng duyệt **nâng sha + push**, không thấy bản duyệt **câu chữ hiến chương**. | `docs/charter/HOP-DONG-MOI.md:505-513` | (1) Bỏ thay đổi `HOP-DONG-MOI.md` khỏi nhánh (commit `git checkout main -- docs/charter/HOP-DONG-MOI.md` trên nhánh, hoặc rebase). (2) Điều phối xin người dùng duyệt câu chữ (2 dòng: "6 khoá", "`scene.pascal-viewer`", nguồn `flags.ts:86-93`), rồi tự commit `docs(charter): …` chỉ tệp đó, trailer `Charter-Approved: <tệp duyệt>`. Nhánh sau khi bỏ khác cây đã qua cổng **chỉ ở một tệp .md của hiến chương** → không ảnh hưởng mã/test, dùng lại cổng `gate-X1.log`, lượt 3 chỉ soát `git diff 0e7edc4..<mới>` = đúng tệp đó. |
| B | P3 | OPS / R-33 | Chưa có bằng chứng dựng ảnh `web` tại `8c28ef96` với Dockerfile mới (bỏ `pnpm draco`); cổng `run.sh verify` không dựng ảnh web, các `chuoi-*.log` dựng bằng Dockerfile cũ còn `pnpm draco`. Đọc mã cho thấy đúng (xem trên) và lỗi sẽ đỏ to ở CI `job_build`, nên không chặn. | `deploy/docker/web.Dockerfile:12-16` | Trước/sau merge chạy một lần `web-context.sh 8c28ef96 … && docker build -f deploy/docker/web.Dockerfile …` (đường `tools/ci/job.sh:445-447`). |

Về `tools/contract/APPFRONT_SHA` (cũng trong danh sách §2): chấp nhận — tệp thuộc quyền điều phối, chính điều phối ra lệnh nâng với duyệt của người dùng (spec-X2 dòng 1, `timeline.md:83-84`), và commit squash vào `main` do điều phối tạo. Khác với hiến chương, luật không đòi cơ chế trailer riêng cho tệp này.

## Điểm (mã)
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 5 | 0,15 |

Tổng: **4,95 / 5** — về mã đủ điều kiện APPROVE.

## PHÁN QUYẾT: REJECT (thủ tục)
Mọi finding mã của lượt 1 đã đóng, cổng đầy đủ tại đúng `0e7edc4` thoát 0 với độ phủ ≥ 90/90 ở mọi gói chạm và bước 7 hợp đồng FE @ `8c28ef96` xanh. Phán quyết REJECT chỉ vì điều kiện dừng sớm §2 của merge-review: sửa `docs/charter/*` trong commit có mã mà không có `Charter-Approved`. Để được APPROVE: bỏ `HOP-DONG-MOI.md` khỏi nhánh; điều phối lấy duyệt câu chữ của người dùng và commit hiến chương riêng (chỉ tài liệu, có trailer); lượt 3 chỉ cần xác nhận diff so với `0e7edc4` đúng là việc bỏ tệp đó, dùng lại cổng này. (Lệch khỏi prompt: spec-RB2 chỉ cho APPROVE|REQUEST CHANGES; luật §2 của skill bắt buộc REJECT — làm theo luật.)
