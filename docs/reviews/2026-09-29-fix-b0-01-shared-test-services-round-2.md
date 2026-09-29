# Review merge fix/b0-01-shared-test-services → main (lượt 2)

- Ngày: 2026-09-29 · Reviewer: phiên /merge-review (FIX-114, độc lập) · Commit đầu nhánh: `84b424b0…`
- Phạm vi: **chỉ vòng sửa** `git diff 3a98cb2..84b424b` (8 file, +119/−27) — đáp lại F-1…F-6 của
  phán quyết lượt 1 (`docs/reviews/2026-09-29-fix-b0-01-shared-test-services.md`).
- Cổng: phạm vi **đích — lượt 2** (R-33b: diff chỉ chạm mã test/fixture test + `.importlinter`,
  không chạm migration, hợp đồng FE hay biên bảo mật). Không chạy lại; đọc log đầy đủ của tác giả:
  `C:/Users/mxuan/orca/workspaces/AppBack/fix-114/.cache/src-out/verify/20260929T074433Z-3a98cb2e7f12.log`
  → `mã thoát: 0`, bảng 8/8 bước `đạt` (0,1,2,3,4,5,5b,6,7,8), `6382 passed … 624.91s` (log:259).
  Tên log mang sha cha `3a98cb2` vì chạy trước lúc commit, nhưng **nội dung khớp cây `84b424b`**:
  log:180 nạp plugin `packages.testing.fixtures.worker_id` — file **chỉ có** ở lượt 2; số test
  6382 > 6380 của lượt 1, đúng bằng 2 test mới của vòng sửa; `Contracts: 10 kept, 0 broken` (log:41)
  ứng với `.importlinter` đã thêm `tools`.
- Độ phủ (log:262-266): tổng dòng 99,56 % · nhánh 98,43 %; `packages/testing` 99,56/98,35;
  `tools` 98,90/96,42; **tập file bị chạm 100,00 % dòng · 96,43 % nhánh** — mọi số ≥ 90/90.
- Cây sạch, 1 commit thêm. Dòng đầu `fix(verify): drop the shared service state with its last user`
  (61 ký tự) đúng mẫu, thân có `Prompt: B0-01` + `Fix: FIX-114`. Không chạm file cấm, không
  `pragma: no cover`, không `skip`/`xfail`, không hạ ngưỡng (K24).

## Kiểm từng finding lượt 1

**F-1 (P2, CON-03) — đã sửa đúng gốc.** `packages/testing/fixtures/services.py:149-158`: trong nhánh
`users == 0`, `state.unlink(missing_ok=True)` chạy **trước** `_remove_container`, cả hai nằm trong cùng
một lượt `with lock`, và `write_text` dời hẳn xuống nhánh `else` — không còn đường nào để lại file
`users: 0` trỏ vào container đã xoá. Không có cửa sổ tranh chấp: tiến trình tới sau chỉ vào được sau khi
khoá nhả, lúc đó file đã biến mất nên nó đi nhánh `start()`. Test người vào sau có thật và đúng ý:
`test_người_vào_sau_khi_đếm_về_0_dựng_container_mới` (`tools/tests/test_shared_services.py:122-140`)
khẳng định `endpoint-cid-1` (container **mới**) chứ không phải endpoint cũ, và `starter.calls ==
["cid-0", "cid-1"]`. Test cũ `test_container_bị_xoá_dù_thân_test_ném_lỗi` đổi khẳng định từ
`_state(tmp_path)["users"] == 0` sang "không còn file" — đúng, không phải nới lỏng.

**F-2 (P3, RES-02) — đã sửa, đúng một loại.** `services.py:93-101`: `with suppress(NotFound)` bọc đúng
`get(...).remove(force=True)`, chỉ `docker.errors.NotFound`; mọi lỗi Docker khác (`APIError`,
`DockerException`) vẫn nổi lên — không nuốt ngoại lệ rộng (LOG, R-16). Docstring nói rõ vì sao `NotFound`
là đích đã đạt. Test `test_container_đã_biến_mất_không_làm_hỏng_lượt_dọn` (:142-150) bơm `side_effect =
NotFound` và khẳng định teardown kết thúc sạch + file trạng thái vẫn bị xoá.

**F-3 (P3, MNT-02) — đã sửa đúng hướng phụ thuộc.** `packages/testing/fixtures/worker_id.py` mới:
chỉ `import os`, một hằng `XDIST_WORKER_ENV`, một hàm `xdist_worker_id()` — **không** tác dụng phụ lúc
nhập, docstring module + docstring hàm đầy đủ (R-01). `db.py:39-42` và `services.py:42` cùng nhập từ đó;
`services.py` bỏ hẳn `_worker_id()` và `import os` (không còn bản trùng, R-07), `db.py` không còn kéo theo
`testcontainers` lẫn `ryuk_disabled`. Chỗ đặt file (`fixtures/`) đúng quy ước CLAUDE.md — `conftest.py`
gốc nạp nó như plugin; module không khai fixture nên vô hại, và cảnh báo `PytestAssertRewriteWarning`
kèm theo là cùng loại đã có sẵn cho `clock`/`services`/`storage` (log:150-180), không phải hồi quy.
Hai chỗ nhập trong test (`test_parallel_fixtures.py`, `test_reset_guard.py`) cập nhật theo.

**F-4 / F-5 (P3, TEST-07) — đã sửa, lưới phủ đúng.** `.importlinter`: `tools` vào `root_packages` (:9)
và `source_modules` (:193); `ignore_imports` đổi `packages.*.tests.**` → `packages.**.tests.**` và thêm
`tools.tests.**` + `tools.**.tests.**` (hai dòng vì `**` không khớp khúc rỗng — `tools/tests` là một cấp,
`tools/ci/tests` và `tools/contract/tests` là hai cấp; đã đối chiếu `find -type d -name tests`, khớp đủ).
`_top_level_modules()` (`test_reset_guard.py:89-101`) khởi tạo `{"tools"}` nên hợp đồng thiếu `tools` sẽ
đỏ ngay, và `test_hợp_đồng_vẫn_cho_test_nhập_packages_testing` neo đúng bốn dòng mới. Bằng chứng cổng:
`lint-imports` vẫn **10 kept, 0 broken** sau khi `tools` vào `source_modules` — mở rộng phạm vi không
kéo theo vi phạm tồn đọng.

**F-6 (Nit, MNT-01) — đã sửa.** `changes/FIX-114.md:11` ghi đúng `tools/tests/test_shared_services.py`;
mục về `services.py` và dòng mới về `worker_id.py` cũng đã tả đúng cơ chế hiện tại.

**Không sinh lỗi mới về hành vi.** Nhánh ngoài xdist (`-p no:xdist`) giữ nguyên `start()/stop()`;
bộ đếm, `FileLock` và phạm vi cô lập (database mỗi tiến trình, bucket mỗi test, Redis/Mailpit **không**
chia chung) không đổi. Toàn bộ diff là mã test/fixture test + cấu hình lint — không chạm mã sản phẩm,
không chạm migration, không chạm hợp đồng FE.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| G-1 | P3 | MNT-06 | `from docker.errors import NotFound` là lần **đầu tiên** repo nhập trực tiếp gói `docker`, nhưng `docker` không khai ở `[dependency-groups] dev` của `pyproject.toml` — nó chỉ có trong `uv.lock` như phụ thuộc gián tiếp của `testcontainers`. Hôm nay chạy được; ngày `testcontainers` đổi client (hay khai lại phụ thuộc) thì bước 3/5 vỡ với `ModuleNotFoundError` xa nguồn gốc | `packages/testing/fixtures/services.py:27`, `tools/tests/test_shared_services.py:18` | thêm `"docker"` vào nhóm `dev` rồi `bash tools/verify/run.sh lock` (nhập trực tiếp thì khai trực tiếp) |

Không có P0, không có P1, không có P2.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 (F-1 đóng, có test) | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 (F-2 đóng, `suppress` đúng một loại) | 0,50 |
| DB, API – Migration & contract | 10% | 5 (không chạm) | 0,50 |
| TEST – Kiểm thử | 7% | 5 (F-4, F-5 đóng; 2 test mới đúng ý) | 0,35 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 (G-1) | 0,12 |

Tổng: **4,97 / 5**

## PHÁN QUYẾT: APPROVE

Cả sáu finding của lượt 1 đều được sửa ở đúng gốc chứ không vá triệu chứng: F-1 xoá file trạng thái cùng
container trong cùng lượt giữ khoá và có test dựng đúng kịch bản "người vào sau" mà finding mô tả; F-2
chỉ nuốt `NotFound` chứ không nuốt cả họ lỗi Docker; F-3 dời hằng xuống một module trung tính thật sự
(chỉ `os`, không tác dụng phụ) nên hướng phụ thuộc DB → container đã cắt; F-4/F-5 mở lưới hợp đồng sang
`tools` và sang thư mục test hai cấp mà vẫn **10 kept, 0 broken**. Cổng là mã thoát thật 0, 8/8 bước,
6 382 test, phủ tập file bị chạm 100,00 %/96,43 %, và log tự chứng minh nó chạy trên cây lượt 2
(plugin `worker_id`). Không P0/P1/P2, điểm ≥ 4,0.

Trước khi gộp: F-1…F-6 đã đóng bằng mã, **không cần** dòng `DEBT.md` nào cho chúng nữa (hướng dẫn "ghi
F-1 thành NO-<nnn>" của lượt 1 hết hiệu lực). G-1 gộp vào một dòng nợ P3 của chủ B0-01, không chặn gộp.
`NO-281` (Ryuk tắt) giữ nguyên `mở`, vẫn chấp nhận được như lượt 1.
