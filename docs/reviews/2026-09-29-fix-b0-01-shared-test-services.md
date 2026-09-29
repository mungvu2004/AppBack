# Review merge fix/b0-01-shared-test-services → main

- Ngày: 2026-09-29 · Reviewer: phiên /merge-review (FIX-114, độc lập) · Commit đầu nhánh: `3a98cb2e7f12`
- Cổng: phạm vi **đầy đủ** — không chạy lại, đọc log cổng của tác giả (nhiệm vụ review cấm chạy lại).
  Log: `C:/Users/mxuan/orca/workspaces/AppBack/fix-114/.cache/src-out/verify/20260929T065533Z-6cca3fdfaf9b.log`,
  `bash tools/verify/run.sh verify` → **mã thoát: 0**, 8/8 bước `đạt` (0,1,2,3,4,5,5b,6,7,8).
  Tên log mang sha nền `6cca3fd` (lượt chạy trước khi commit), nhưng **nội dung khớp đúng cây của nhánh**:
  `Contracts: 10 kept, 0 broken` gồm dòng `mã sản phẩm không nhập packages.testing (FIX-114…)` (log:39,41),
  `6380 passed … 684.90s` (log:249), venv `venv-fix-114`. Số của §4 báo cáo tác giả đối chiếu khớp từng dòng.
- Độ phủ (log:254-257): tổng **dòng 99,57 % · nhánh 98,45 %**; `packages/testing` 99,56/98,35;
  `tools` 98,90/96,42; tập file bị chạm 100,00/96,43 — mọi số ≥ 90/90.
- Cây làm việc sạch; 1 commit; dòng đầu `perf(verify): share test services across xdist workers` (57 ký tự)
  đúng mẫu, có trailer `Prompt: B0-01` + `Fix: FIX-114`. `changes/FIX-114.md` có mặt.
  Không chạm file cấm (`docs/charter/*`, `openapi.json`, `APPFRONT_SHA`); `uv.lock` chỉ thêm 2 dòng khai
  `filelock` — hệ quả của `pyproject.toml` cùng nhánh, không sửa tay. Không `pragma: no cover`,
  không `skip`/`xfail` mới, không hạ ngưỡng (K24). Diff 421 dòng thêm, trong đó 241 dòng là test mới —
  phần logic sản phẩm dưới ngưỡng tách nhánh.

## Soát trọng tâm

**1. Chặn cứng lượt dọn `DELETE` — đạt.** `assert_reset_target` (`packages/testing/fixtures/db.py:105-121`)
chạy ở dòng đầu `_on_reset_connection` (`db.py:137`), **trước** `create_async_engine`, nên không câu SQL nào
chạy khi từ chối. Đã kiểm lại bằng `grep`: `_on_reset_connection` là đường **duy nhất** thi hành khối
`DELETE FROM public.%I` (`db.py:170`), và chỉ có một chỗ gọi nó (`db.py:291`) — không còn đường vòng nào
(R-19 đúng). Hai điều kiện AND, fail-closed thật: tên database phải bằng đúng `shared_db_name()` của tiến
trình (có hậu tố `gw<n>` dưới xdist) và phải thấy dấu vết phiên pytest. `tools/tests/test_reset_guard.py:38-73`
chứng minh cả hai chiều từ chối, gồm 6 URL lạc (`postgres`, `appback`, DB mẫu, DB của tiến trình xdist khác,
tên ngoài-xdist khi đang ở `gw3`, URL trống) và nhánh "không phải pytest". `_drop_database`/`_admin` không
nằm trong phạm vi chặn, nhưng tên của chúng luôn sinh từ `template_db_name()`/`shared_db_name()` — chấp nhận được.

**2. Hợp đồng `testing-only-from-tests` — đạt.** `.importlinter:166-188`: `forbidden`,
`forbidden_modules = packages.testing`, `source_modules` liệt kê đúng 9 gói `packages/*` (trừ
`packages.testing`) + `apps.api`/`apps.worker`/`apps.ml` — đối chiếu thủ công với `ls -d packages/*/ apps/*/`
khớp đủ, không bỏ lọt `apps.*`. `test_hợp_đồng_phủ_mọi_gói_sản_phẩm` neo đúng tập này nên gói mới quên khai
sẽ đỏ ngay. Test vẫn nhập được (`ignore_imports`), không chặn nhầm — `lint-imports` **10 kept, 0 broken** (log:41).

**3. Dùng chung Postgres/MinIO giữa tiến trình xdist — đúng, một khe hở P2.**
Cô lập giữ nguyên và có thật: Postgres một database mỗi tiến trình (`_per_worker`, `db.py:69-73`),
MinIO một bucket ngẫu nhiên mỗi test (`packages/testing/fixtures/storage.py:57-58`), Redis và Mailpit
**không** chia chung — quyết định đúng, vì vai Redis chốt cứng ở số hiệu DB (`packages/messaging/redis.py`)
và `mailpit_inbox` dọn cả hộp thư. Bộ đếm người dùng đúng ý: người dựng không xoá sớm, chỉ người rời cuối
cùng xoá (`services.py:145-150`), có test `test_chỉ_người_rời_cuối_cùng_xoá_container`. Nhánh ngoài xdist
(`-p no:xdist`) giữ nguyên hành vi cũ, có test. Không rò sang lượt chạy khác: không nơi nào đặt `--basetemp`
cố định (`tools/verify/steps.py:170`, `pyproject.toml:101`), nên gốc basetemp mới mỗi lượt. Khe hở: xem F-1.

**4. NO-281 (Ryuk tắt) — chấp nhận được, không chặn gộp.** Ryuk buộc vòng đời container vào **một** tiến
trình, nên để bật là nó giật container dùng chung khỏi tiến trình còn sống; tắt là điều kiện của chính thiết
kế này, không phải đi tắt. Ngưỡng chỉ hiện khi phiên bị **giết cứng** (Ctrl-C, Docker Desktop tắt) — lượt
chạy bình thường và cả lượt hỏng giữa chừng đều trả container (test `test_container_bị_xoá_dù_thân_test_ném_lỗi`).
Đã có script dọn của người điều phối và dòng `NO-281` (P3, mở) trong `DEBT.md:302`. Không cần sửa trước gộp.

**5. Dependency mới — đạt.** `filelock` khai ở `pyproject.toml:40` nhóm `dev`, không ghim phiên bản — đúng
thói quen của mọi dòng quanh nó, `uv.lock` mới là chỗ ghim. `uv.lock` chỉ thêm đúng 2 dòng khai vào nhóm
`dev`, không đổi bản nào khác → đúng là hệ quả của `run.sh lock`, không sửa tay.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| F-1 | P2 | CON-03 | File trạng thái **không bị xoá** khi bộ đếm về 0: sau khi người cuối xoá container, `shared-service-<key>.json` vẫn nằm đó với `users: 0`. Tiến trình xdist nhận fixture **lần đầu** muộn hơn (xdist tắt worker đã hết việc trước khi cả phiên xong, `--dist loadfile`) sẽ đi nhánh `state.exists()`, tăng đếm lên 1 và dùng **endpoint của container đã bị xoá** → bước 5 hỏng chập chờn, lỗi hiện ra là "connection refused" chứ không nói vì sao | `packages/testing/fixtures/services.py:149-150` | trong nhánh `users == 0`: `state.unlink(missing_ok=True)` thay cho `write_text` ngay trước đó, để tiến trình tới sau dựng container mới; thêm test "người mới vào sau khi đếm về 0 dựng lại container" |
| F-2 | P3 | RES-02 | `_remove_container` xoá cứng không phòng thủ: container đã biến mất (Docker restart, dọn tay) → `NotFound` ném ra giữa teardown fixture phiên, khi đang giữ `FileLock`, làm cả lượt chạy báo lỗi teardown thay vì kết thúc sạch | `packages/testing/fixtures/services.py:93-95` | bọc `try/except docker.errors.NotFound: pass` — mục tiêu đã đạt khi container không còn |
| F-3 | P3 | MNT-02 | `db.py` nhập `XDIST_WORKER_ENV` từ `services.py` chỉ để lấy **một chuỗi hằng**, kéo theo `filelock`, `testcontainers` và **tác dụng phụ lúc nhập** `testcontainers_config.ryuk_disabled = True` (`services.py:57`). Ý định R-07 (một hằng một chủ) đúng, nhưng hướng phụ thuộc ngược: module DB giờ phụ thuộc module container | `packages/testing/fixtures/db.py:40` | đưa hằng xuống một module trung tính (`packages/testing/fixtures/xdist.py`), hai bên cùng nhập |
| F-4 | P3 | TEST-07 | Hợp đồng chỉ phủ `packages/` và `apps/`; `tools/` cũng là gói Python (`tools/__init__.py`) có mã không phải test (`coverage_gate.py`, `case_gate.py`, `pinned_images.py`) nhưng nằm ngoài `source_modules`, và `_top_level_modules()` cố tình chỉ quét hai thư mục kia nên sẽ không bao giờ phát hiện. Hôm nay chưa có vi phạm (đã grep kiểm), nhưng lưới chưa phủ hết ý "mã sản phẩm không nhập `packages.testing`" | `.importlinter:177-186`, `tools/tests/test_reset_guard.py:86-94` | thêm `tools` vào `source_modules` kèm `ignore_imports = tools.tests.** -> packages.testing.**`, hoặc ghi rõ trong docstring vì sao `tools` đứng ngoài |
| F-5 | P3 | TEST-07 | `ignore_imports` dùng `packages.*.tests.**` (đúng một cấp) trong khi test thật có ở **hai** cấp (`packages/domain/library/tests`, `packages/vision/quality/tests`…); vế `apps` lại dùng `apps.**.tests.**` đúng. Hôm nay chưa vỡ vì các thư mục đó chưa nhập `packages.testing`, nhưng lần nhập đầu tiên sẽ làm bước 4 đỏ oan; `test_hợp_đồng_vẫn_cho_test_nhập_packages_testing` đang neo cứng mẫu thiếu đó | `.importlinter:170-171`, `tools/tests/test_reset_guard.py:108-113` | đổi thành `packages.**.tests.**` (mẫu cũ là quy ước có sẵn của 9 hợp đồng kia — sửa cả loạt hay chỉ hợp đồng mới đều được) |
| F-6 | Nit | MNT-01 | `changes/FIX-114.md` liệt kê `tools/tests/test_services.py` trong khi file mới thật là `tools/tests/test_shared_services.py` | `changes/FIX-114.md:9` | sửa tên file |

Không có P0, không có P1.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 3 (F-1) | 0,45 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 4 (F-2) | 0,40 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 (F-4, F-5) | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 (F-3, F-6) | 0,12 |

Tổng: **4,50 / 5**

## PHÁN QUYẾT: APPROVE

Không P0/P1 và điểm ≥ 4,0. Phần nguy hiểm nhất của nhánh — lượt dọn `DELETE` toàn bảng — giờ fail-closed
thật ở đúng chỗ duy nhất thi hành nó, và test dựng đúng những URL lạc mà một lỗi thật sẽ tạo ra; hợp đồng
import-linter mới khoá `packages.testing` lại ở đúng phạm vi mà không chặn nhầm test; cơ chế dùng chung
Postgres/MinIO giữ nguyên cô lập sẵn có (database mỗi tiến trình, bucket mỗi test) và cố ý **không** chia
chung Redis/Mailpit — đúng chỗ mà chia chung sẽ hỏng thật. Cổng là mã thoát thật 0, 8/8, 6 380 test, phủ
99,57/98,45. Báo cáo tác giả trung thực: các mục "lệch khỏi prompt" (§3) đều có lý do đứng được, và §4.2
tự nói rằng lợi ích đo được là RAM/container chứ không phải đồng hồ — không thổi phồng.

Trước khi gộp, người điều phối ghi **F-1** thành một dòng `NO-<nnn>` (P2, chủ B0-01) trong `DEBT.md` và giao
FIX sửa sớm: nó là nguồn chập chờn của chính cổng, một dòng `state.unlink()` là đủ. F-2…F-6 gom thành một
dòng nợ P3 chung. NO-281 (Ryuk tắt) giữ nguyên `mở`, chấp nhận được, không chặn gộp.
