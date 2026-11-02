# Review merge feature/aid-01-design-director → main (lượt 2)

- Ngày: 2026-11-02 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh: 27dd09060671 (phán quyết lượt 1: `03526a9d`; soát `git diff 03526a9d..HEAD`, 2 commit `c11de6b7`, `27dd0906`)
- Cổng: phạm vi **đầy đủ**. Vòng sửa chạm `docs/contracts/openapi.json` và `tools/contract/APPFRONT_SHA`, cả hai nằm trong sàn "đầy đủ" của R-33b (`tools/**`, `docs/contracts*`). Lượt 1 cũng đã đòi một lượt đầy đủ thoát 0 (điều kiện 3).
  - Lượt 6 @ 27dd0906, `VERIFY_SHARED_STACK=off` (`F:/worktrees/AppBack/_logs/aid-01-verify.log`, log cổng `.cache/src-out/verify/20261102T113802Z-27dd09060671.log`): **mã thoát 1**. Bước 0, 1, 2, 4 đạt. Bước 5: pytest **9721 passed, 0 failed**, nhưng `coverage_gate` hỏng `[độ phủ nhánh tập file bị chạm < 90%] 89.76%`. Bước 3, 5b, 6, 7, 8 **chưa chạy**.
  - Lượt 1–5: đều thoát 1 (xem phán quyết lượt 1 và `aid-01-verify-5.log`: 1 failed `apps/worker/pipeline_steps/tests/test_sweep_rules.py::test_sweep_resends_remaining_families_when_walls_used`). Lượt 6 không lặp lại các lỗi của 3–5, nên các lỗi đó là lỗi chập chờn ngoài diff. Chúng **không** phải chỗ chặn của lượt này.
  - `aid-01-steps3678.log` chạy @ **03526a9d**, chưa phải HEAD: bước 3 (mypy) và 6 (migrate_check) đạt; bước 7 hỏng vì thiếu junit của bước 5 (luật đã biết: `--steps 7` cần bước 5 cùng lượt). Vòng sửa chỉ đổi hai hằng số trong `vertex.py`, nên mypy/migration gần như chắc không đổi, nhưng chưa có bằng chứng trên HEAD.
  - Reviewer tự đối chiếu (`run.sh shell` @ 27dd0906): `python -m apps.api.core.openapi --out /tmp/o.json --compare docs/contracts/openapi.json` → **thoát 0**.
- Độ phủ (lượt 6): tổng dòng 99,04 % · nhánh 97,20 % | `tools` 94,77/93,86 · **tập file bị chạm 92,14/89,76 (hỏng)** · các đơn vị khác giữ như lượt 1 (`packages/genai` 100/100, `apps/api/design_director` 97,98/96,67, `apps/worker/design_director` 97,44/97,78).

## Kiểm từng yêu cầu của lượt 1

| Yêu cầu lượt 1 | Kết quả | Bằng chứng |
|---|---|---|
| (1) P1 `openapi.json` thiếu N47/N48 | **Đã sửa** | `c11de6b7`: +260/−0, chỉ thêm `/api/projects/{project_id}/design-concept` (`get`, `post`) cùng 4 schema `DesignConcept*`/`DesignStyleId`; `--compare` thoát 0 |
| (2) P1 `APPFRONT_SHA` không có trên `master` của FE | **Đã sửa** | `27dd0906`: `99e18dbe`. Trong `F:/App/AppFront`: `git fetch origin` rồi `merge-base --is-ancestor 99e18dbe origin/master` → 0; `origin/master` = `99e18dbe`; có `src/api/schemas/designConcept.ts`. FE `pnpm verify` trên worktree @ `99e18dbe` (cây sạch, log 18:23, sau commit 18:08): đạt cả 7 bước, `exit 0` (`F:/worktrees/AppFront/_logs/aid-01-verify.log`) |
| (3) Một lượt cổng đầy đủ thoát 0 trên HEAD | **Chưa đạt** | Lượt 6 thoát 1 ở bước 5 (`coverage_gate`), xem finding R2-1 |
| (4) P2 RES: lượt xấu nhất dài hơn trần quét 15 phút | **Đã sửa** | `packages/genai/vertex.py:35-37`: `TIMEOUT_S` 60, `MAX_ATTEMPTS` 3. Xấu nhất một lời gọi 3 × 60 + 2 + 4 = 186 s, bốn lời gọi ≈ 12,4 phút < 15 phút. Test `test_retry_then_success_with_backoff` sửa theo (3 lần gọi, lùi `[2.0, 4.0]`). `test_retry_exhaustion_unavailable` dùng chính hằng `MAX_ATTEMPTS` |
| P3 #4–#11 phải có dòng nợ | **Đã ghi** | `changes/AID-01.md`: NO-AID-1..7 phủ finding 4, 5, 6, 8, 9, 10, 7 + 11 |

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| R2-1 | P1 | TEST-05 / BE-00 §12 bước 5 | Cổng đầy đủ đỏ vì chính mã của nhánh: `coverage_gate` báo độ phủ nhánh của tập file bị chạm là 89,76 % (< 90 %). Nguyên nhân: `03f9349c` thêm `tools/design_director/__init__.py`, nên `build_materials.py` (160 dòng, 22 nhánh `if/for`) giờ bị đo, mà không test nào nhập nó (`grep build_materials` chỉ thấy một docstring ở `packages/domain/design_director/materials.py:1`). So sánh: lượt 2 @ 037b7823 (chưa có `__init__.py`) cho tập file bị chạm 98,74/98,28, `tools` 98,76/96,52. Lượt 6 cho 92,14/89,76 và 94,77/93,86, trong khi vòng sửa không thêm `.py` nào khác ngoài hai hằng số của `vertex.py` (100/100). Lượt 1 ghi việc này là P3 #10 / NO-AID-6, nhưng nó làm cổng đỏ nên phải nâng lên. Lượt 3–5 dừng ở pytest trước khi tới `coverage_gate`, vì thế chưa ai thấy | `tools/design_director/build_materials.py:26-160`; `tools/design_director/__init__.py`; `changes/AID-01.md` (NO-AID-6) | Chọn một: (a) thêm `tools/design_director/tests/__init__.py` + `test_build_materials.py`, test `srgb_to_lab` (trắng/đen ra L 100/0), `describe` trên mảng nhỏ, `split_sets` theo `DRY_CATEGORIES`/`WET_CATEGORIES`/`DRY_PATTERN_MAX`, `save_jpg` giữ dưới `MAX_JPG`, `main` với thư mục FE giả trong `tmp_path`, sao cho tập file bị chạm ≥ 90/90; hoặc (b) chuyển công cụ chạy tay này ra khỏi repo (vd. `F:/runs/...`), xoá `tools/design_director/` và sửa docstring `materials.py:1`. Sau đó gỡ NO-AID-6 nếu chọn (a) |
| R2-2 | P2 | R-33b / bằng chứng cổng | Bước 3, 5b, 6, 7, 8 chưa chạy trên HEAD trong cùng một lượt. Bằng chứng mypy/migrate là của `03526a9d`; bước 7 chưa từng chạy được với junit thật của bước 5 trên nhánh này | `_logs/aid-01-steps3678.log` | Sửa xong R2-1 thì chạy lại một lượt `bash tools/verify/run.sh verify` đầy đủ (`VERIFY_SHARED_STACK=off`, sau `docker stop f14-ml-1`). Lượt đó phải thoát 0 và có đủ bước 3, 5b, 6, 7, 8 |
| R2-3 | Nit | RES | Mức 12,4 phút chỉ tính thời gian chờ Vertex. Tải ảnh, vẽ bảng và ghi kho cộng thêm vào cùng trần 15 phút, nên lề còn khoảng 2,5 phút. Trần tổng theo hạn chót (đề xuất lượt 1) vẫn chắc hơn | `packages/genai/vertex.py:37` | Không chặn. Có thể gom vào NO-AID khi làm hạn chót tổng của lượt |

Ghi chú về lỗi chập chờn ngoài diff (không chặn lượt này, để người điều phối biết): `apps/api/admin_ml_datasets/tests/test_contract.py::test_ml_create_dataset__C07` (lượt 3, Redis f14), `apps/ml/walls/tests/test_tasks.py::test_segment_walls__J01` (lượt 4, Redis f14), `apps/worker/pipeline_steps/tests/test_sweep_rules.py::test_sweep_resends_remaining_families_when_walls_used` (lượt 5, `VERIFY_SHARED_STACK=off`; ở lượt 6 cùng cấu hình thì đạt).

Điều kiện dừng sớm của vòng sửa: cây sạch. Hai commit đúng mẫu (`fix(design-director)`, `chore(contract)`) và có `Prompt: AID-01`. `openapi.json` sinh bằng `run.sh openapi` (`--compare` thoát 0), `APPFRONT_SHA` do người điều phối ghim, cả hai đúng yêu cầu lượt 1. Không có `pragma`/`noqa` trần/`skip` mới, không hạ ngưỡng.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4 | 0,60 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 4 | 0,40 |
| RES | 10% | 4,5 | 0,45 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 3 | 0,21 |
| OBS/OPS | 5% | 3,5 | 0,175 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,33 / 5

## PHÁN QUYẾT: REQUEST CHANGES

Vòng sửa đúng và đủ cho P1 #1, P1 #2 và P2 RES; các P3 đã có dòng nợ. Chỗ chặn duy nhất còn lại **không** phải lỗi chập chờn: lượt 6 đã cho toàn bộ 9721 test đạt, nhưng cổng đỏ thật ở `coverage_gate` vì tệp của chính nhánh (`tools/design_director/build_materials.py`, chưa có test, bị đo từ khi thêm `__init__.py`). Để được duyệt:
1. **R2-1:** thêm test cho `build_materials.py` để tập file bị chạm ≥ 90 % dòng và nhánh, hoặc đưa công cụ ra khỏi repo.
2. **R2-2:** một lượt `bash tools/verify/run.sh verify` đầy đủ **thoát 0** trên HEAD mới, có đủ bước 3, 5b, 6, 7, 8.

Lượt 3 chỉ cần soát diff sửa R2-1 cùng log của lượt cổng ở mục 2.
