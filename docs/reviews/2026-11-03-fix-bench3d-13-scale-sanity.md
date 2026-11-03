# Review merge fix/bench3d-13-scale-sanity → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: ed4788a337d7 (PR #41; merge-base = `origin/main` 297f2067ea93, PR `MERGEABLE`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions run 41589635822) — quy ước hiện hành dùng CI thay `run.sh verify` tại chỗ. Run 41589635822 (workflow CI, head `ed4788a337d702671355c826e81ff07c6500d7b5` = đầu nhánh): `changes`, `lint`, `typecheck`, `unit` (2 shard), `ml` (3 shard), `integration` (5 shard), `build`, `perf`, `contract`, `coverage` đều `success`. Run 41589635763 (CodeQL, cùng SHA): `success`. Run 41589635739 (Commits, cùng SHA): `success`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` của run 41589635822: `coverage_gate: đạt`, `case_gate: đạt`): tổng dòng 99,32% · nhánh 97,52% — gói bị chạm: `apps/worker/pipeline_build` 98,37% / 93,73%. Tất cả ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch (`.bench3d/` nằm trong `.git/info/exclude`). 3 commit, dòng đầu đúng Conventional Commits, mỗi commit có `Prompt: BENCH3D-13`:
  `e655025d fix(pipeline-build): sanity-check scale on skew, raster PDF, strays`,
  `e8b47c72 fix(pipeline-build): guard skew mean and near-shell stray drop` (sửa phát hiện Codex 2 và 5),
  `ed4788a3 fix(pipeline-build): judge same-plan skew by the main wall frame`.
- 8 tệp, +236/−35 (mã logic ~150 dòng) — dưới 400, không cần tách.
- Có `changes/BENCH3D-13.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore`, skip/xfail mới, không hạ ngưỡng.
- `apps/worker/pipeline_build/tasks.py` nằm ngoài danh sách tệp của làn L2 trong `BRIEF-dot3.md` (brief ghi `preprocess.py`), nhưng cùng thư mục sở hữu `apps/worker/pipeline_build/`, không làn nào khác chạm tệp này và `changes/BENCH3D-13.md` có ghi — không vi phạm R-27.

## Soát nội dung

- **Ảnh giãn không đều** (`build.py:373-411`, `:796-799`): `_anisotropy` giữ ngưỡng 3 % cũ, thêm điều kiện mọi hộp chữ của hai cụm trục nằm trong khung tường chính (`_plan_frame`: `wall_clusters` + `grow_region` trên mm, đúng cách `_drop_far_clusters` dựng vùng) nới 25 % cạnh dài. Chỉ khi `basis == "chain"` và cùng khung thì tỉ lệ mới đổi thành √(x·y); không tường → `None` → giữ cụm đông nhất. Kịch bản P1 của Codex (mặt bằng 1:100 + chi tiết 1:50 ngoài khung) có test tham số `shell`/`no-walls` khẳng định giữ 10 mm/px. √(x·y) của hai giá trị trong dải 1-200 mm/px vẫn trong dải; không về 0 sau quantize.
- **Ghi chú `TL 1:N` trên PDF ảnh** (`build.py:344-358`): PDF vector giữ nguyên hành vi; PDF ảnh chỉ nhận ghi chú khi lệch ước cửa ≤ 10 %. Ba nhánh (khớp, lệch, không cửa) có test. `_door_scale` chỉ gọi khi có tường, đúng tiền điều kiện của nó.
- **`_vector_page`** (`tasks.py:127-135`): `stat` khoá `preprocess/vectors.json` của chính lượt; `_put_vectors` (`pipeline_orchestrate/preprocess.py:298-320`) chỉ ghi khoá này khi `pixel_vectors` khác `None` (không phải PDF quét/ảnh). Không `px_per_paper_mm` thì khỏi `stat`. Test dùng `LocalDiskStorage` thật cho cả ba trạng thái. Lỗi kho lan lên như các lần đọc khác của task.
- **Mẩu lạc** (`geometry.py:325-389`): cụm < min(600 mm, 3 % tổng) lòi khỏi hộp cụm dài nhất quá bề dày lớn nhất → bỏ; trong dải 1 m chỉ bỏ khi mọi tường nằm trên đường gióng của tường cụm chính. Cụm chính không bao giờ tự bị bỏ (hộp của nó nằm trong hộp nới). Kịch bản P2 của Codex (má tường song song vỏ cách 500 mm) giữ lại, có test `balcony-pier-500mm`. Đếm vào `isolatedBlock` như cũ.
- SEC/CON/RES: không đầu vào người dùng mới, không trạng thái dùng chung; một `stat` thêm mỗi lượt dựng PDF. Không đổi API/DB/hợp đồng FE; `scaleChecks` giữ khoá cũ; job `contract` xanh.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG | Khung "cùng mặt bằng" là heuristic có trần: (a) chi tiết khác tỉ lệ đặt trong 25 % cạnh dài của khung, hoặc có tường cách mặt bằng ≤ `FAR_CLUSTER_GAP_MM` (1,5 m theo tỉ lệ chuỗi) nên `grow_region` nuốt vào khung, vẫn bị coi là "giãn trục" → lấy √(x·y), lệch tới ~−29 % như kịch bản Codex 2; (b) cụm chữ của một trục có thể chỉ 3 mẫu. Hành vi cũ ở ca này chỉ ghi nghi vấn. | `apps/worker/pipeline_build/build.py:97`, `:399-411`, `:796-799` | Ghi giới hạn (a) vào `changes/BENCH3D-13.md`; lượt sau cân nhắc đòi thêm chứng cứ độc lập (vd. tỉ lệ x/y của hộp bao tường so với chuỗi tổng, hoặc mỗi trục ≥ 4 mẫu) trước khi đổi tỉ lệ. Không chặn merge. |
| 2 | P3 | LOG | Luật PDF ảnh không phân biệt PDF quét (khổ trang = khổ giấy thật, ghi chú `TL 1:N` thường đúng) với PDF xuất từ ảnh (khổ tuỳ ý, two-page-ch04). Với PDF quét không đọc được chuỗi, ghi chú đúng mà ước cửa lệch > 10 % (ước cửa lệch trung vị 8-10 %, ca lẻ tới 15 %) sẽ bị bỏ và rơi về ước cửa/tường kém hơn. Bench hiện không có ca quét nào phải dùng ghi chú (ch-03-scan đi đường chuỗi) nên chưa đo được. | `apps/worker/pipeline_build/build.py:126`, `:344-358`; `apps/worker/pipeline_build/tasks.py:127-135` | Ghi giới hạn vào `changes/BENCH3D-13.md`; thêm một ca bench PDF quét không chuỗi có ghi chú TL trước khi siết thêm. |
| 3 | P3 | LOG | `_on_extension` so với đường thẳng vô hạn của **mọi** tường cụm chính (cả vách trong). Má/vách ngăn lô gia ngắn (< 600 mm) bị khe tách khỏi vỏ (khe > ½ tổng dày + `WALL_JOIN_MM`, dễ gặp khi mặt nạ ML đứt) mà thẳng hàng với một vách trong và cách hộp chính ≤ 1 m vẫn bị bỏ như nét gióng. | `apps/worker/pipeline_build/geometry.py:338-349`, `:382-385` | Giới hạn thẳng hàng với tường có đầu mút gần mẩu (vd. khoảng cách từ mẩu tới đoạn tường ≤ `_STRAY_SHELL_BAND_MM`), hoặc ghi giới hạn vào `changes/BENCH3D-13.md`. |
| 4 | P3 | DOC | Docstring cũ/sai sau thay đổi: (a) `axis_scales` vẫn ghi "người gọi so hai trục để ghi lại, không đổi tỉ lệ đã chọn" trong khi `build_layer` nay đổi tỉ lệ; (b) `_door_scale` ghi "chỉ gọi ở nhánh ước lượng" nhưng `_trusted_note` cũng gọi; (c) `_vector_page` nói "Lượt dùng lại trang (i) không ghi `vectors.json` nên bị coi như PDF ảnh" — đường (i) có `px_per_paper_mm=None` (`preprocess.py:332-339`) nên hàm trả `True` ngay, câu này không xảy ra. | `packages/domain/scale/infer.py:161-165`; `apps/worker/pipeline_build/build.py:435-438`; `apps/worker/pipeline_build/tasks.py:128-132` | Sửa ba câu docstring cho đúng (mục (a) nằm ở `packages/domain`, ngoài tệp của làn: giao lượt sau hoặc người điều phối). |
| 5 | P3 | TEST | Số đo thật (ch-13 30,381 → 28,513 mm/px; "mọi ca chuỗi khác không đổi"; "bench r3 không tường nào trong khung căn đáp án bị bỏ") chỉ có trong commit message/docstring, không tái hiện được từ repo hay CI; test dựng dữ liệu tổng hợp. | commit `ed4788a3`; `apps/worker/pipeline_build/geometry.py:325-331` | Chấp nhận (luật heuristic, có số đo bench r4b trong `F:/runs/bench-3d/KET-QUA-r4.md`). |
| 6 | Nit | PERF | `_plan_frame` (STRtree + BFS trên mọi tường) chạy mỗi lượt dựng kể cả khi không có chữ chuỗi hay `basis != "chain"`, lúc kết quả không dùng; `_door_scale` có thể tính hai lần (`_trusted_note` rồi nhánh ước lượng). Chi phí nhỏ so với bước dựng. | `apps/worker/pipeline_build/build.py:796`, `:354`, `:806` | Khi chạm lại: chỉ dựng khung khi `anisotropic` khác rỗng và `basis == "chain"`. |
| 7 | Nit | MNT | Docstring `_STRAY_CLUSTER_SHARE` mô tả cả `_STRAY_CLUSTER_MM` (docstring thuộc tính gắn vào phép gán ngay trước nó), giống Nit 7 của phán quyết BENCH3D-03. | `apps/worker/pipeline_build/geometry.py:325-331` | Khi chạm lại, đặt docstring dưới hằng đầu hoặc tách hai docstring. |

Không có P0/P1/P2. Hai phát hiện Codex thuộc làn này (2 — P1, 5 — P2) đã sửa đúng gốc và có test hồi quy. Giới hạn còn lại (finding 1-3) chưa có dòng trong `changes/BENCH3D-13.md`.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,71 / 5

## PHÁN QUYẾT: APPROVE

Ba sửa tỉ lệ khoanh gọn trong bước dựng, mỗi nhánh mới có test, hai phát hiện Codex (tờ có chi tiết khác tỉ lệ; trụ/má tường sát căn) đã sửa tận gốc với test hồi quy đúng kịch bản. PDF vector và ảnh thường giữ hành vi cũ; không đổi API/DB/hợp đồng FE. CI GitHub Actions trên đúng SHA đầu nhánh xanh toàn bộ, độ phủ gói bị chạm và tổng ≥ 90/90. Không P0/P1/P2; năm P3 và hai Nit làm ở lượt sau — ưu tiên ghi giới hạn của finding 1-3 vào `changes/BENCH3D-13.md` và sửa ba docstring cũ (finding 4).
