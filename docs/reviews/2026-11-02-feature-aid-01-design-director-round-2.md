# Review merge feature/aid-01-design-director → main (lượt 2)

- Ngày: 2026-11-02 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh được soát: efd5e44ca358 (phán quyết lượt 1: `03526a9d`; soát `git diff 03526a9d..efd5e44c`, 3 commit `c11de6b7`, `27dd0906`, `efd5e44c`)
- Cổng: phạm vi **đầy đủ**. Vòng sửa chạm `docs/contracts/openapi.json`, `tools/contract/APPFRONT_SHA` và thêm tệp test/thư mục `.py` dưới `tools/`, đều thuộc sàn "đầy đủ" của R-33b. Lượt 1 cũng đã đòi một lượt đầy đủ thoát 0.
  - **Lượt 7** @ `dd449861` (= `efd5e44c` + bản nháp phán quyết này, chỉ thêm `.md`), `VERIFY_SHARED_STACK=off`. Log: `F:/worktrees/AppBack/_logs/aid-01-verify.log`, log cổng `.cache/src-out/verify/20261102T115207Z-dd44986186ec.log`. Kết quả: **mã thoát 1**.
    - Đạt: bước 0, 1, 2, **3 (mypy)**, 4, **5** (pytest 9724 passed, 0 failed; `coverage_gate: đạt`).
    - Hỏng: **5b**, 1 failed `apps/worker/pipeline_build/tests/test_perf.py::test_build_layer__perf_under_30_seconds` ("build_layer mất 32.19s, trần 30s").
    - Bước 6, 7, 8 **chưa chạy**, vì cổng dừng ở 5b.
  - Lượt 6 @ 27dd0906 (`_logs/aid-01-verify-6.log`): mã thoát 1. Pytest 9721 passed, nhưng `coverage_gate` hỏng (độ phủ nhánh tập file bị chạm 89,76 %) vì `build_materials.py` chưa có test. `efd5e44c` đã sửa, lượt 7 xác nhận.
  - Reviewer tự chạy lại test perf lẻ (`run.sh shell`, `pytest -m perf … -k perf_under_30`, 3 lần):
    - nhánh @ dd449861: **hỏng 3/3**, 33,51 / 32,70 / 32,36 s;
    - **`main` @ 4e1cd3b2** (`F:/App/AppBack`, cây sạch): **hỏng 3/3**, 62,02 / 59,19 / 57,90 s. Lúc đó máy còn chạy song song `appback-verify-sec-deps-…` của phiên khác và `f14-ml-1`.
    - → Test này đỏ cả trên `main` trong môi trường hiện tại. Nhánh không làm nó chậm thêm: diff không chạm `apps/worker/pipeline_build`, `packages/domain/spatial` hay `packages/vision`; chỉ thêm một tiền tố trong `packages/core/ids.py`.
  - Reviewer đối chiếu openapi (`run.sh shell` @ 27dd0906): `python -m apps.api.core.openapi --out /tmp/o.json --compare docs/contracts/openapi.json` → **thoát 0**. Vòng `efd5e44c` không đổi API.
  - Bước 6 (migrate_check) chỉ có bằng chứng @ `03526a9d` (`_logs/aid-01-steps3678.log`, đạt). Sau đó migration không đổi. Bước 7 chưa từng chạy với junit thật của bước 5 trên nhánh này.
- Độ phủ (lượt 7): tổng dòng 99,35 % · nhánh 97,50 % | `tools` 98,77/96,49 · tập file bị chạm 99,21/98,03 · `packages/genai` 100/100 · `apps/api/design_director` 97,98/96,67 · `apps/worker/design_director` 97,44/97,78.

## Kiểm từng yêu cầu của lượt 1

| Yêu cầu lượt 1 | Kết quả | Bằng chứng |
|---|---|---|
| (1) P1 `openapi.json` thiếu N47/N48 | **Đã sửa** | `c11de6b7`: +260/−0, chỉ thêm `/api/projects/{project_id}/design-concept` (`get`, `post`) cùng 4 schema `DesignConcept*`/`DesignStyleId`; `--compare` thoát 0 |
| (2) P1 `APPFRONT_SHA` không có trên `master` của FE | **Đã sửa** | `27dd0906`: `99e18dbe`. Trong `F:/App/AppFront`: `git fetch origin` rồi `merge-base --is-ancestor 99e18dbe origin/master` → 0; `origin/master` = `99e18dbe`; có `src/api/schemas/designConcept.ts`. FE `pnpm verify` trên worktree @ `99e18dbe` (cây sạch): đạt cả 7 bước, `exit 0` (`F:/worktrees/AppFront/_logs/aid-01-verify.log`) |
| (3) Một lượt cổng đầy đủ thoát 0 trên HEAD | **Chưa đạt** | Lượt 7 thoát 1 ở bước 5b, do test perf ngoài diff (xem R2-2) |
| (4) P2 RES: lượt xấu nhất dài hơn trần quét 15 phút | **Đã sửa** | `packages/genai/vertex.py:35-37`: `TIMEOUT_S` 60, `MAX_ATTEMPTS` 3. Xấu nhất 3 × 60 + 2 + 4 = 186 s một lời gọi, bốn lời gọi ≈ 12,4 phút < 15 phút. Test lùi `[2.0, 4.0]` và `test_retry_exhaustion_unavailable` dùng chính hằng |
| P3 #4–#11 phải có dòng nợ | **Đã ghi / đã sửa** | NO-AID-1..5, 7 có trong `changes/AID-01.md`. NO-AID-6 (#10) đã sửa ở `efd5e44c` và gỡ khỏi sổ |

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| R2-1 | — | TEST-05 (đã đóng trong lượt) | Lượt 6 đỏ vì `build_materials.py` bị đo mà chưa có test. Commit `efd5e44c` thêm 3 test: thư viện Pascal giả trong `tmp_path`, không ghi `data/` thật; `main(argv, out=OUT)` nhận thư mục ghi. Lượt 7: `coverage_gate: đạt`, tập file bị chạm 99,21/98,03. Đã soát diff: mọi hàm test có docstring, có `tests/__init__.py`, không phụ thuộc mạng hay thời gian thật. `monkeypatch` `ImageFont.truetype` và `MAX_JPG` nằm đúng tầng | `tools/design_director/tests/test_build_materials.py`; `tools/design_director/build_materials.py:142-153` | Không cần làm gì |
| R2-2 | P1 (ngoài diff, có sẵn trên `main`) | BE-00 §12 bước 5b / TEST-02 | Cổng đầy đủ đỏ ở 5b vì `test_build_layer__perf_under_30_seconds`, trần đồng hồ tường 30 s. Test đỏ 3/3 khi chạy lẻ trên nhánh (32–34 s) và **3/3 trên `main` 4e1cd3b2** (58–62 s, máy đang chịu tải). Đây không phải lỗi của AID-01 và nhánh không sửa được trong phạm vi của mình. Nhưng theo ma trận, cổng thoát ≠ 0 thì không duyệt được, và vì nó mà bước 6, 7, 8 chưa chạy trên HEAD | `apps/worker/pipeline_build/tests/test_perf.py:91-124` | Người điều phối đưa lên người dùng, chọn một: (a) chạy lại cổng đầy đủ lúc máy rảnh (không cổng nào khác chạy song song, `docker stop f14-ml-1`), nếu 5b xanh thì đủ; (b) mở FIX/nợ cho chủ `pipeline_build` (trần 30 s đỏ trên `main` ở máy này), rồi người dùng waiver riêng bước 5b cho lượt merge này. Cả hai cách vẫn cần bằng chứng bước 6, 7, 8 trên HEAD (`--steps 5,6,7,8`, bước 7 cần junit của bước 5) |
| R2-3 | Nit | RES | Mức 12,4 phút chỉ tính thời gian chờ Vertex. Tải ảnh, vẽ bảng và ghi kho cộng thêm vào cùng trần 15 phút, nên lề còn khoảng 2,5 phút. Trần tổng theo hạn chót (đề xuất lượt 1) vẫn chắc hơn | `packages/genai/vertex.py:37` | Không chặn |

Các lỗi chập chờn khác ngoài diff ở lượt 3–5 (không lặp lại ở lượt 6–7): `apps/api/admin_ml_datasets/tests/test_contract.py::test_ml_create_dataset__C07`, `apps/ml/walls/tests/test_tasks.py::test_segment_walls__J01` (cả hai do Redis f14 dùng chung), `apps/worker/pipeline_steps/tests/test_sweep_rules.py::test_sweep_resends_remaining_families_when_walls_used` (lượt 5, `VERIFY_SHARED_STACK=off`).

Điều kiện dừng sớm của vòng sửa: cây sạch. Ba commit đúng mẫu (`fix(design-director)`, `chore(contract)`, `test(tools)`) và có `Prompt: AID-01`. `openapi.json` sinh bằng `run.sh openapi`, `APPFRONT_SHA` do người điều phối ghim, cả hai đúng yêu cầu lượt 1. Không có `pragma`/`noqa` trần/`skip` mới, không hạ ngưỡng.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4 | 0,60 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 4 | 0,40 |
| RES | 10% | 4,5 | 0,45 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 3,5 | 0,175 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,44 / 5

## PHÁN QUYẾT: REQUEST CHANGES

Mọi yêu cầu về mã và hợp đồng của lượt 1 đã xong: P1 #1, P1 #2, P2 RES, NO-AID-6. Lượt 7 cho 9724 test đạt, `coverage_gate` đạt, mypy đạt. **Chỗ chặn duy nhất còn lại là lỗi có sẵn ngoài diff:** `apps/worker/pipeline_build/tests/test_perf.py::test_build_layer__perf_under_30_seconds` (bước 5b) đỏ cả trên `main` 4e1cd3b2 trong môi trường hiện tại. Ma trận không cho APPROVE khi cổng thoát ≠ 0 và chưa có waiver. Để được duyệt cần một trong hai:
1. Một lượt `bash tools/verify/run.sh verify` đầy đủ **thoát 0** trên HEAD, chạy lúc máy rảnh; hoặc
2. Người dùng waiver bước 5b cho test perf trên (kèm dòng nợ/FIX cho chủ `pipeline_build`), cộng bằng chứng `--steps 5,6,7,8` thoát 0 trên HEAD.

Lượt 3 chỉ cần soát log cổng đó (và waiver, nếu đi cách 2). Không cần soát lại mã.
