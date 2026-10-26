# Review merge fix/apt-scale-chains → main

- Ngày: 2026-10-26 · Reviewer: phiên /merge-review · Commit đầu nhánh: d132bd45f59c (base `main` 95d3c78a)
- Nguồn luật: `RULE.md`, `RULE-CODE.md`, `DEBT.md` **không có** trong repo. Dùng `docs/charter/*` (BE-00, BE-KFM, FIX); mã `R-xx`/`LOG-xx`… giữ như các phán quyết trước.
- Cổng: phạm vi **đầy đủ** (lượt review đầu, R-33b (1)). `bash tools/verify/run.sh verify` mã thoát **1** (log `F:/worktrees/AppBack/apt-scale-verify.log`): bước 0, 1, 2, 4 đạt; bước 5 **hỏng**, 3 failed / 8841 passed:
  - `tools/contract/tests/test_check.py::test_real_repo_check_runs_through` ("Thao tác đã mount" hỏng);
  - `apps/api/versions/tests/test_routes_read.py::test_versions_read_snapshot__C01` (snapshot thiếu khoá `edited` của tường);
  - `apps/api/health/tests/test_health.py::test_health_ready_recomputes_after_cache_expires` (503 thay vì 200).
  Hai test đầu **hỏng ổn định trên `main` 95d3c78a** (chạy riêng trên checkout `main` bằng `run.sh shell`, 2/2 lượt hỏng), không do nhánh: nhánh không chạm `apps/api`, `tools/contract`, route hay model không gian. Test health qua 2/2 trên `main` khi chạy riêng: chập chờn do tải.
  Bước 3, 5b, 6, 7, 8 bị ghi "chưa chạy", reviewer chạy bù: `--steps 3,5b,6,7,8` → mypy --strict **đạt**; 5b perf 6 test đạt nhưng `case_gate` hỏng vì lượt từng phần không có junit bước 5 (đồ tạo tác của `--steps`). `--steps 6,7,8` → 6 **đạt**; 7 hỏng: "Thao tác đã mount" 94 route / 86 dòng BE-BIND (`projects_cancel_create_project`, `share_links_create/export/list/revoke` thiếu dòng BE-BIND, cùng gốc với test hỏng thứ nhất, có sẵn trên `main`), H1/H5 0 mẫu vì lượt từng phần không có mẫu bước 5. `--steps 8` → openapi **đạt**.
- Độ phủ: tổng của lượt đầy đủ **không in** (bước 5 hỏng trước `coverage_gate`). Đo riêng bằng `pytest --cov --cov-branch` trên 4 gói bị chạm (1012 passed): `packages/vision/dimensions/chains.py` 99% (134 dòng, 1 trượt; 36 nhánh, 1 trượt), `apps/ml/text/tasks.py` 100%, `apps/worker/pipeline_build/build.py` 96%, `packages/ml_contracts/artifacts.py` 100%; tổng 4 gói 99%.

## Phạm vi và điều kiện dừng sớm

- Cây sạch. 3 commit, đều `Prompt: SB-APT-SCALE`, `Fix: FIX-2449`: 9bd0fabf `fix(scale): infer scale from dimension chains measured on the page`, b96f8cfa `fix(scale): pick the dimension line nearest the text, round grey`, d132bd45 `docs(changes): correct FIX-2449 baseline to 1/14 measured on f14`. Có `changes/FIX-2449.md`.
- 9 file, +462/−6, mã logic ~250 dòng, dưới ngưỡng MNT-05. Không `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới, không hạ ngưỡng. Không chạm `docs/charter/*`, `uv.lock`, `pyproject.toml`, `openapi.json`, `APPFRONT_SHA`.

## Reviewer tự kiểm

1. **Đỏ trước, xanh sau (FIX luật 1).** Trong `run.sh shell` của nhánh: thay `build.py` bằng bản `main` → `test_build_layer__scale_from_dimension_chains` **đỏ** (17 khác xanh). Thay `chains.py` bằng bản 9bd0fabf → `test_dimension_spans__nearest_line_beats_darker_wall_edge` **đỏ**, đúng lỗi ch-06 mà b96f8cfa sửa.
2. **`test_perf.py` không chập chờn do nhánh.** Chạy riêng 3 lần mỗi bản: nhánh 11,4 / 11,1 / 11,8 s; nhánh với `build.py` của `main` 12,2 / 11,1 / 10,9 s; checkout `main` 10,9 / 10,8 / 11,0 s (trần 30 s). Phần nhánh thêm vào `build_layer` là `_chain_samples` (O(số chữ), chữ không có `span_px` thì không parse) và `densest_cluster` trên tập rỗng: không đáng kể. Lần hỏng dưới `-n 4` mà tác giả gặp là do tải máy; lượt đầy đủ này 5b không chạy tới, lượt bù thì 6 test perf đạt.
3. **Mẫu ghép tường lạc khi chuỗi quyết.** Khi chuỗi thắng, `rejected_ids` là id chuỗi nên mẫu ghép-tường lạc không bị loại ở `_grouped_samples`. Nhưng `_best_sample` chỉ nhận mẫu lệch ≤ 2 % so với `s` cuối, nên mẫu lạc thành `dimensionUnpaired`, không dựng `Dimension` sai. Không phải finding.
4. **Hợp đồng FE.** `TextPx` không lộ qua `apps/api` (grep), bước 8 openapi đạt. `text.json` cũ (không có `span_px`) vẫn đọc được, có test.
5. **Thời gian bước đọc chữ.** Đo `dimension_spans` trong `f14-ml-1` trên trang 3000×4000 px, 100 chữ (64 trên chuỗi): 1,37 s (13,7 ms/chữ), ảnh xám 0,36 s, RSS đỉnh 448 MB. Xem finding 1, 2.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | PERF-01 | `_ticks` gọi `np.pad(ink, 1)` và dựng `near` cho **cả trang** ở mỗi chữ, nên chi phí là O(số chữ × số điểm ảnh). Đo được 13,7 ms/chữ ở 12 Mpx. Ở trần hợp đồng (40 Mpx, `MAX_TEXTS` 5000) ước ~45 ms/chữ, ~4 phút, còn dưới soft limit 3300 s nhưng tốn vô ích. | `packages/vision/dimensions/chains.py:332-333` | Dựng `near` một lần trong `dimension_spans` (một bản cho `bare`, một cho `bare.T`) rồi truyền vào `_span`/`_ticks`. |
| 2 | P3 | PERF-04 | `image[..., :3] @ np.array([...])` ép ảnh RGB sang float64 trước khi nhân: bản tạm H×W×3×8 byte, ~960 MB ở trần 40 Mpx, cộng ảnh kết quả 320 MB, trong container ml. | `apps/ml/text/tasks.py:29` | Số nguyên: `((image[..., :3].astype(np.uint32) * (299, 587, 114)).sum(-1) + 500) // 1000` rồi `astype(np.uint8)` (~4 byte/kênh, vẫn làm tròn như cv2), hay `cv2.cvtColor` nếu opencv headless đã có trong ảnh ml (`apps/ml/text/reader.py` đã `import cv2`). |
| 3 | P3 | LOG-01 / K19 | `densest_cluster` khi hai cụm đông nhất bằng nhau thì chọn cụm có tâm nhỏ hơn. Trang có hai nhóm kích thước khác tỉ lệ (mặt bằng 1:100 và chi tiết 1:50) với số mẫu bằng nhau sẽ ra một tỉ lệ theo quy tắc chọn, tức là đoán. K19 đòi không đoán. Bench 14 bản chưa gặp ca này. | `packages/vision/dimensions/chains.py:418-429`; test `test_densest_cluster__empty_and_tie` khẳng định hành vi hiện tại | Hoà giữa hai cụm không chồng nhau → trả `()`, để rơi về ghép tường hay `project_default`. Sửa test hoà tương ứng. |
| 4 | P3 | OPS-02 | `TextPx` là `extra=forbid`. Ảnh ml mới ghi `span_px`, worker cũ đọc `text.json` sẽ ném, bước dựng hỏng. Ghi chú triển khai "ml và worker phải ra cùng SHA" chỉ có trong mô tả phiên, không có trong `changes/FIX-2449.md`. | `packages/ml_contracts/artifacts.py:183`; `changes/FIX-2449.md` | Thêm vào `changes/FIX-2449.md`: "Triển khai: ảnh `ml` và `worker` cùng SHA (khoá mới `span_px`, `extra=forbid`); worker trước, ml sau nếu buộc phải lệch." |
| 5 | Nit | MNT | `changes/FIX-2449.md` còn số của commit đầu ("6/6 bản vẽ ảnh thẳng"), chưa có số đo trên stack ở b96f8cfa (8/14 có tỉ lệ, 6 lệch ≤ 0,2 %, 2 ảnh giãn ~4 %). | `changes/FIX-2449.md:9` | Cập nhật dòng "Sau sửa" theo số đo trên f14. |
| 6 | Nit | LOG | Chữ ngang một ký tự ("5") có hộp cao > 1,3 lần rộng nên bị coi là chữ dọc, đo trên ảnh chuyển vị, ra `None`. Chỉ mất mẫu, không sai tỉ lệ. | `packages/vision/dimensions/chains.py:400` | Chấp nhận, hoặc coi là dọc chỉ khi chuỗi có ≥ 2 ký tự. |
| 7 | Nit | MNT | `_chain_samples` kiểm `text.span_px` hai lần (cho mypy thu hẹp kiểu). | `apps/worker/pipeline_build/build.py:236-237` | `if text.span_px is None: continue` ở đầu vòng. |

Không phải finding của nhánh nhưng **chặn cổng**: hai test hỏng ổn định trên `main` 95d3c78a (`test_real_repo_check_runs_through` do 5 route đã mount thiếu dòng BE-BIND; `test_versions_read_snapshot__C01` do snapshot C01 chưa có khoá `edited` mà `56c98abe` thêm vào `Wall`). Mọi nhánh rẽ từ `main` hiện tại đều không qua được bước 5 và 7.

Đã soát, không có finding: SEC (không có biên vào mới; `span_px` qua `Field(gt=0, allow_inf_nan=False)`, có test âm), CON (hàm thuần, không trạng thái chung), RES (không I/O mới), DB/API (không migration, không đổi OpenAPI, `TextPx` không lên dây FE), TEST (đỏ-trước đã kiểm; có ca rỗng, nền xám, vạch xiên, chữ dọc, vạch giả, chữ lệch tâm, đoạn hẹp, khối dày phía kia, mép tường đậm; không phụ thuộc thời gian thật), edge case toạ độ hộp vượt ảnh (lát numpy tự kẹp, `_line_extent` không chạy vòng khi `cx` ngoài ảnh).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 4 | 0,40 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |

Tổng: **4,65 / 5** · P0: 0 · P1: 0 · P2: 0 · P3: 4 · Nit: 3

## PHÁN QUYẾT: REQUEST CHANGES

Mã của nhánh đạt mức APPROVE (không P0/P1/P2, điểm 4,65, đỏ-trước đã kiểm, độ phủ file đổi 96–100 %, `test_perf` không chậm hơn `main`). Nhưng cổng đầy đủ thoát 1, và skill đòi "thoát khác 0 → REQUEST CHANGES". Gốc của mã thoát nằm ở `main`, không ở nhánh. Để được duyệt:
1. Sửa `main` (việc riêng, không thuộc nhánh này): thêm dòng BE-BIND (hay miễn K06) cho `projects_cancel_create_project`, `share_links_create`, `share_links_export`, `share_links_list`, `share_links_revoke`; cập nhật snapshot C01 của `test_routes_read.py` cho khoá `edited`.
2. Đưa nhánh lên `main` đã sửa, chạy lại `bash tools/verify/run.sh verify` đầy đủ, thoát 0 (test health chập chờn thì chạy lại, ghi như các review trước).
3. Lượt review 2 chỉ cần soát diff vòng sửa (phạm vi đích) nếu nhánh không đổi mã. Finding 1–4 là P3, sửa luôn trong vòng này thì tốt (mỗi cái vài dòng), không bắt buộc.
