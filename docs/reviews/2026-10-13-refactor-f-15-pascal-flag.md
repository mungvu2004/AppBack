# Review merge refactor/f-15-pascal-flag → main

- Ngày: 2026-10-13 · Reviewer: phiên /merge-review · Commit đầu nhánh: ad177a13ed68 (base `main` @ 94388307)
- Cổng: phạm vi **đầy đủ** (lượt 1, R-33b đk 1; diff chạm `APPFRONT_SHA` và `openapi.json`); `bash tools/verify/run.sh verify` mã thoát **0** (log: `F:/App/AppBack/backend/dieu-phoi/chay/F-15/gate-merge-review-BE.log:678`, bản gốc `.cache/src-out/verify/20261013T111435Z-ad177a13ed68.log` trong worktree `f15-be`). Bước 0–8 và 5b đều `đạt`: pytest 8448 passed; `case_gate: đạt`; `migrate_check: đạt`; bước 7 với AppFront @ `d50bb248`: Smoke, Bản đồ đủ, H1, H1 ngữ cảnh, H3 (10 khoá, 3 vai), H4, H5 đều đạt.
- Độ phủ: tổng dòng 99,47% · nhánh 98,04% — `apps/api/telemetry` 98,92% / 96,05%; `tools` 98,76% / 96,50%; tập file bị chạm 100% / 100%.

## Phạm vi

9 tệp, +24/−28, 3 commit. Cả ba có dòng đầu đúng mẫu và trailer `Prompt: F-15`. Cây làm việc sạch. Có `changes/F-15.md`. Không có pragma, `noqa`, `type: ignore`, skip hay xfail mới, và không hạ ngưỡng.

- `387087cc`: bỏ `scene.pascal-viewer` khỏi `FEATURE_FLAG_KEYS` và `FeatureFlagsOut`; sửa docstring/test 6 → 5 khoá; sửa `env.example:109`. Nằm đúng whitelist của spec-T2.
- `a227bd5a` (`tools/contract/APPFRONT_SHA` → `d50bb248`) và `ad177a13` (`docs/contracts/openapi.json`) chạm file cấm ở §2. **Chấp nhận**: hai tệp thuộc quyền điều phối và do chính điều phối commit (`timeline.md:60`), giống tiền lệ `2026-10-06-fix-fix-378-pascal-flag-compose-round-2.md:31`. Diff `openapi.json` chỉ bỏ thuộc tính `scene.pascal-viewer` và đổi mô tả "6 khoá" → "5 khoá", khớp `schemas.py`.
- Đã tự kiểm FE @ `d50bb248`: `src/lib/telemetry/flags.ts` `FEATURE_FLAG_KEYS` có 5 khoá; `src/api/schemas/featureFlags.ts:30-34` là strict 5 khoá, không còn `scene.pascal-viewer`. Vì vậy response BE mới khớp schema FE, và test gương `==` xanh trong cổng.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | OPS / RES | `d50bb248` chỉ có trên `master` local của AppFront: `git branch -a --contains d50bb248` chỉ ra `master`, còn `origin/master` = `d521b549`. CI checkout `repository: mungvu2004/AppFront`, `ref:` = SHA ghim (`.github/workflows/ci.yml:116-131`, tương tự `:193`, `:214`), và `deploy.yml:51,83` dựng ảnh web từ SHA đó. Đẩy `main` AppBack trước khi đẩy AppFront thì CI hợp đồng, CI build và deploy đều đỏ vì không tìm thấy ref. | `tools/contract/APPFRONT_SHA:1` | **Điều kiện merge:** đẩy AppFront `master` lên `origin` trước (là fast-forward: `origin/master` là tổ tiên của `d50bb248`, đã kiểm `merge-base --is-ancestor`), rồi mới đẩy `main` AppBack. |
| 2 | P2 | API / R-34 | Hiến chương còn ghi `FeatureFlagsSchema` "object strict, **6** khoá", có `scene.pascal-viewer` và nguồn `flags.ts:86-93`. Sau nhánh này, BE và FE đều chỉ còn 5 khoá, nên hiến chương lệch mã. `DEBT.md` không có dòng nào cho lệch này. Lỗi cùng loại với finding #2 của FIX-378. | `docs/charter/HOP-DONG-MOI.md:505-513` | Điều phối xin người dùng duyệt câu chữ (5 khoá, bỏ `scene.pascal-viewer`, sửa lại dòng nguồn `flags.ts` theo `d50bb248`), rồi commit riêng `docs(charter): …` chỉ chạm tệp đó, kèm trailer `Charter-Approved:`. Nếu chưa làm kịp thì mở một dòng `NO-` trong `DEBT.md`. |
| 3 | P3 | OPS | Validator `_known_keys` (`settings.py:28-34`) làm API không khởi động được nếu `FEATURE_FLAGS` còn khoá đã bỏ. Chuỗi F-14 vẫn đặt `FEATURE_FLAGS='{"scene.pascal-viewer": true}'` (`backend/dieu-phoi/chay/F-14/chuoi.sh:8`, ngoài git), và `docs/SETUP.md:223` ghi lại đúng giá trị đó. Chạy chuỗi F-14 với BE này thì API fail-fast ngay lúc nạp cấu hình. Fail-fast là hành vi đúng (K01), nhưng công cụ và tài liệu chưa sửa theo. | `docs/SETUP.md:223` | Đổi sang `'{"scene.instanced-walls": true}'` hoặc bỏ biến, ở cả `chuoi.sh:8` và `SETUP.md:223`. Ghi một dòng DEBT nếu không làm trong đợt gộp. |
| 4 | P3 | MNT / R-02 | `changes/F-15.md:8-11` ghi "KHÔNG sửa `openapi.json`, `APPFRONT_SHA`", "gương sẽ xanh khi điều phối bump SHA" và nhắc commit T4 `8d7ee002`. Nhưng chính nhánh này đã sửa cả hai tệp và ghim `d50bb248`, nên ghi chú thay đổi sai so với nội dung sẽ squash vào `main`. | `changes/F-15.md:8-11` | Viết lại 2 dòng: openapi đã làm mới (`ad177a13`); `APPFRONT_SHA` = `d50bb248` (merge F-15), test gương đạt trong cổng. |
| 5 | P3 | OPS | Chưa có bằng chứng ảnh `web` dựng được ở SHA ghim mới. Ảnh `appback-web:f15` dựng từ `4b3be7db` (nhãn `org.opencontainers.image.revision.appfront`). Từ `4b3be7db` đến `d50bb248` có đổi `package.json`, `pnpm-lock.yaml`, `vite.pascal.config.ts` và `scripts/copy-pascal-assets.mjs`, trong khi `web.Dockerfile:12-16` đòi `pnpm build` và `test -f dist/assets/pascal/pascal-mount.js`. Cổng `run.sh verify` không dựng ảnh web. `vite.pascal.config.ts:73,80` @ `d50bb248` vẫn xuất `public/assets/pascal/pascal-mount.js`, nên rủi ro thấp. | `tools/contract/APPFRONT_SHA:1` | Sau khi đẩy AppFront, xem job `build` của CI trên `main` (hoặc dựng `web` một lần ở `d50bb248`). Ảnh đỏ thì mở FIX ngay. |
| 6 | Nit | TEST | Test khoá lạ chỉ dùng `"khong.ton-tai"`. Không có ca nào khẳng định khoá vừa bỏ (`scene.pascal-viewer`) giờ bị từ chối khi nạp cấu hình, nên không có gì chặn việc vô tình thêm lại. | `apps/api/telemetry/tests/test_flags.py:42-46` | Thêm `'{"scene.pascal-viewer": true}'` vào bộ tham số. Không chặn merge. |

Đã xét, không có finding: SEC (không đụng biên vào), CON (không trạng thái dùng chung), PERF, RES, DB (không migration). Bỏ một trường tuỳ chọn khỏi response là tương thích ngược với FE ghim, vì FE strict 5 khoá và trước đây sẽ từ chối khoá thứ 6.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 3 (#2) | 0,30 |
| TEST | 7% | 5 (chỉ Nit) | 0,35 |
| OBS, OPS | 5% | 3 (#1; #3, #5) | 0,15 |
| MNT | 3% | 4 (#4) | 0,12 |

Tổng: **4,67 / 5**

## PHÁN QUYẾT: APPROVE

Không có P0 hay P1, điểm 4,67 ≥ 4,0. Mã gỡ cờ đúng và tối thiểu, khớp FE @ `d50bb248`. Cổng đầy đủ thoát 0, độ phủ ≥ 90/90 cho mọi gói bị chạm. Duyệt kèm điều kiện sau. Merge (squash) là việc của điều phối.

1. **Bắt buộc, trước khi đẩy `main` AppBack:** đẩy AppFront `master` (`d50bb248`, fast-forward từ `origin/master` `d521b549`) lên GitHub. Không làm thì CI và deploy hỏng (#1).
2. Hiến chương §7.3: commit `docs(charter)` riêng có `Charter-Approved`, hoặc một dòng `NO-` trong `DEBT.md` (#2).
3. Nên làm cùng đợt: sửa `changes/F-15.md` (#4). Sửa `FEATURE_FLAGS` ở `chuoi.sh:8` và `SETUP.md:223`, hoặc ghi dòng DEBT (#3). Theo dõi job `build` web ở CI sau khi đẩy (#5).

Nếu chỉ sửa `changes/F-15.md` (tài liệu) thì không cần chạy lại cổng. Sau merge: commit phán quyết này vào `docs/reviews/`.
