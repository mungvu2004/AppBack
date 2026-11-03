# Review merge fix/bench3d-21-scale → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 2e29d3af8579 (PR #48, `MERGEABLE`, headRefOid = đầu nhánh)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions) — quy ước hiện hành (PROMPT-dot3) dùng CI của PR thay `run.sh verify` tại chỗ. Run 41618908179 (workflow CI, event `pull_request`, headSha `2e29d3af857969641cd442af0f0bb7db3d2e4357`): `changes`, `lint`, `typecheck`, `unit` (2 shard), `ml` (3 shard), `integration` (5 shard), `build`, `perf`, `contract`, `coverage` đều `pass`; run 41618907845 (CodeQL) `pass`; run 41618908037 (Commits) `pass`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` run 41618908179: `coverage_gate: đạt`, `case_gate: đạt`): tổng dòng 99,32% · nhánh 97,56% — gói bị chạm `apps/worker/pipeline_build` 98,56% / 94,56%. Tất cả ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch. 1 commit `2e29d3af fix(pipeline_build): tỉ lệ chuỗi từ hai trục khi cụm chung hoà (T3)`, có `Prompt: BENCH3D-21`; job `commits` xanh.
- 3 tệp, +80/−11 (mã logic ~35 dòng) — dưới 400.
- Có `changes/BENCH3D-21.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore`, skip/xfail mới, không hạ ngưỡng. Mọi tệp trong `apps/worker/pipeline_build/` (thư mục của làn).

## Soát nội dung

- **T3** (`build.py:318-325`): chỉ chạy khi cả cụm chuỗi chung (`chained` rỗng — hoà) lẫn mẫu ghép tường không ra tỉ lệ; thứ tự ưu tiên chuỗi → ghép tường giữ nguyên. Hai trục lệch ≤ 15 % → √(x·y), `paired=False` → gốc `chain`; lệch hơn → rơi về `default` như cũ (test `axes-50pct`). √ của hai giá trị dương hữu hạn vẫn qua `classify_scale_range` + quantize như nhánh cũ; ngoài dải → `scaleOutOfRange`, `axes=None`.
- **Không thành "đã giải" im lặng** (`build.py:833-834`): T3 cứu → luôn ghi `scaleChecks.anisotropic` kể cả khi `_anisotropy` trả rỗng (lệch ≤ 3 %). Đã kiểm đường đọc: `pipeline_quality/service.py:163` ghi khoá `scaleChecks` vào tóm tắt, `spatial_read/readiness.py:114` coi lượt có `scaleChecks` là chưa đo → `scaleUnresolved`. P1 Codex (phản ví dụ 20/20,4 hoà cụm 50) có test hồi quy đúng kịch bản (`test_build_scale.py:447`).
- **Mẫu thêm vào `samples`**: id `t…-chain`, bước 7 chỉ dựng `Dimension` từ id `t…-w…` (docstring `_resolved_scale`), nên không sinh kích thước giả.
- `_axis_clusters` tách nguyên văn từ `_anisotropy`, hai nơi gọi cùng `texts` → cùng kết quả; khi `_anisotropy` cũng báo lệch và `same_plan`, phép √ lặp lại cho cùng số.
- Hành vi thật: lượt chạy f14 `tap-f/runs/f3/f-23/layer.json` cho `scaleMillimetresPerPixel 26.168351`, `scaleBasis chain`, `scaleStatus unresolved` — khớp báo cáo làn (~26,2, vẫn `scaleUnresolved`). Replay (`dot4/scale/cmp.txt` theo `BAO-CAO.md`): bench 0 tốt/0 xấu, F chỉ f-23 đổi; reviewer không chạy lại replay.
- SEC/CON/RES/DB-API: không đầu vào mới từ người dùng, không trạng thái dùng chung, không đổi API/DB/hợp đồng FE (`scaleChecks` giữ khoá `x`,`y` cũ; job `contract` xanh).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG | T3 lấy √(x·y) **không** đòi hai cụm trục nằm sát khung tường chính, khác luật `_ANISOTROPY_LIMIT` của BENCH3D-13 (chỉ đổi tỉ lệ khi `same_plan`). Tờ có mặt bằng + hình khác tỉ lệ gần nhau (1:100 cạnh 1:110 hay 1:90, lệch ≤ 15 %) mà chuỗi hoà → ra tỉ lệ pha trộn sai tới ~7 %. Tác động có trần: luôn ghi `anisotropic` nên readiness báo `scaleUnresolved`, không phải lỗi im lặng. | `apps/worker/pipeline_build/build.py:110-113`, `:322-325` | Ghi giới hạn vào `changes/BENCH3D-21.md`; lượt sau cân nhắc chỉ cứu khi `same_plan` (khung dựng từ tỉ lệ ứng viên) hoặc đòi mỗi trục ≥ 4 mẫu. Không chặn merge. |
| 2 | P3 | DOC | Docstring cũ sau thay đổi: (a) `ScaleChecks` vẫn nói `anisotropic` đổi tỉ lệ chuỗi "khi hai cụm trục cùng sát khung tường chính (`_anisotropy`)" — nay T3 đổi tỉ lệ không cần khung; (b) `_resolved_scale` vẫn ghi "K19: không bao giờ đoán một tỉ lệ khác" trong khi T3 là một ước (có cờ). | `apps/worker/pipeline_build/build.py:146-149`, `:311-312` | Sửa hai câu: nêu đường T3 và việc tỉ lệ cứu luôn mang cờ nghi vấn. |
| 3 | Nit | TEST | Thiếu test biên ngưỡng `_AXIS_AGREEMENT` (đúng 15 % → cứu, 15,1 % → không) và test thứ tự ưu tiên ghép tường trước T3 khi chuỗi hoà. Độ phủ nhánh vẫn đạt nhờ hai ca 7 %/50 %. | `apps/worker/pipeline_build/tests/test_build_scale.py:423-445` | Thêm hai `pytest.param` khi chạm lại. |
| 4 | Nit | MNT | Dòng đầu commit tóm tắt bằng tiếng Việt; `AppBack/CLAUDE.md` (Git) ghi `<tóm tắt tiếng Anh>`, các commit làn trước (BENCH3D-13) viết tiếng Anh. Hook/CI `commits` không bắt. | commit `2e29d3af` | Lần sau viết tóm tắt tiếng Anh; người gộp squash có thể đặt lại tiêu đề. |
| 5 | Nit | PERF | Trên đường T3, `_axis_clusters` (cả `_chain_samples` + hai `densest_cluster`) chạy hai lần (`_resolved_scale` rồi `_anisotropy`). Chỉ ở ca chuỗi hoà, chi phí nhỏ; đường `chain` thường không thêm phép tính (job `perf` xanh). | `apps/worker/pipeline_build/build.py:322`, `:412` | Khi chạm lại có thể truyền cụm đã tính sang `_anisotropy`. |

Không có P0/P1/P2. P1 của Codex thuộc làn này đã sửa tận gốc với test hồi quy; ba P2 Codex thuộc T1, không nằm trong nhánh (T1 tách ở `fix/bench3d-21-scale-t1`, không gộp — đã ghi ở `changes/BENCH3D-21.md`).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,76 / 5

## PHÁN QUYẾT: APPROVE

Sửa nhỏ, khoanh trong bước dựng tỉ lệ, chỉ chạy ở ca chuỗi hoà mà ghép tường cũng không ra; tỉ lệ cứu luôn mang `scaleChecks.anisotropic` nên readiness vẫn báo `scaleUnresolved` (đã đối chiếu `readiness.py:114` và lượt f14 f-23). CI GitHub Actions trên đúng SHA đầu nhánh xanh toàn bộ, độ phủ gói bị chạm và tổng ≥ 90/90. Không P0/P1/P2; hai P3 (ghi giới hạn khung của T3, sửa hai docstring) và ba Nit làm ở lượt sau.
