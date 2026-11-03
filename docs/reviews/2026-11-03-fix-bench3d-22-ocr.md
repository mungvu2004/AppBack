# Review merge fix/bench3d-22-ocr → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 7556811e29a9 (PR #49, `MERGEABLE`; merge-base = `origin/main` 3bf5f3ec)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions) — người dùng quyết định dùng CI của PR thay `run.sh verify`. Run 41618920178 (workflow CI, `pull_request`, head `7556811e29a9354b240c457512e14b2198c9d0fe` = đầu nhánh) `success`; run 41622655334 (Commits, cùng head) `success`; `gh pr checks 49`: 24/24 pass (changes, commits, lint, typecheck, unit/integration/ml shards, build, contract, coverage, perf, CodeQL). Reviewer không chạy cổng hay pytest tại chỗ (không cần cho finding nào).
- Độ phủ (job `coverage` của run 41618920178, `tools.coverage_gate` đạt): tổng dòng 99,32% · nhánh 97,55% — gói bị chạm `apps/ml/text` 98,68% / 97,14%. ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước, nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch, HEAD = `origin/fix/bench3d-22-ocr`. `origin/main..HEAD` có 3 commit: `c0a6bd98 fix(ml): OCR đọc lại số ngược 180° và trang chưa ra tỉ lệ chuỗi`, `67d90335 fix(ml): không đọc lại OCR khi chữ ngang và chữ dọc đều ra tỉ lệ`, `7556811e chore(changes): ghi chú BENCH3D-22` — đúng mẫu hook, đều có `Prompt: BENCH3D-22`; job `commits` xanh.
- Diff: `apps/ml/text/reader.py` +24/−1, `apps/ml/text/tasks.py` +86/−4, hai tệp test +136, `changes/BENCH3D-22.md` +5. Logic ~110 dòng (< 400). Có `changes/BENCH3D-22.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pipeline_build`. Không pragma, `noqa` trần, `type: ignore`, skip/xfail, không hạ ngưỡng.

## Soát nội dung

- **T2 — `RapidOcrReader._best`** (`reader.py:346-368`): lượt 0° khớp `0[0-9]{2,}` thì luôn đọc thêm 180°, nhận lượt 180° chỉ khi tin cậy ≥ `TEXT_CONFIDENCE_MIN`, là số nguyên không 0 đầu (`[1-9][0-9]*`) và cùng độ dài; còn lại rơi về luật tin cậy cũ (hoà → 0°). Phát hiện P2 của Codex (`ROOM`/`01` thắng `0009`) đã siết đúng; test phủ `ROOM`, `01`, `0100`, tin cậy 0,3. Chi phí: chỉ thêm một lượt rec cho chữ khớp mẫu.
- **T4 — `read_page`** (`tasks.py:88-117`): lượt thường → `with_spans`; trang cạnh dài < 2000 px chưa ra tỉ lệ chuỗi → OCR lại ảnh ×2 INTER_CUBIC + `_stretch`, hộp chia lại về trang, `span_px` đo trên ảnh gốc, nhận **cả bộ** lượt lại chỉ khi nó ra tỉ lệ chuỗi. `_chain_scale_found` khớp phép nhánh chuỗi của `_resolved_scale` (`pipeline_build/build.py:310-312`) và điều kiện hai trục khớp `axis_scales` của `_anisotropy` (`build.py:385-392`); tỉ lệ chữ dọc 1,3 = `_VERTICAL_TEXT_RATIO`. `span_px == 0` bị bỏ (`not item.span_px`), không chia 0. `_stretch` ảnh nền tối/gần trống (`background − ink < 10`, kể cả âm) giữ nguyên.
- **Hành vi đo được** (`F:/runs/bench-3d/dot4/ocr/BAO-CAO.md`, `KET-QUA-r5.md`): f-19 không tỉ lệ → 12,784 paired (+0,0 %); ch-01 ước cửa +8 % → chain +0,1 % (r5 lên ĐẠT); không ca có đáp án xấu đi; f-23 không bị đọc lại nhờ luật hai trục. Lượt thật r5: 12–20 s/bản.
- SEC/CON/RES: hàm thuần trên ảnh trong bộ nhớ, không đầu vào người dùng mới, không trạng thái dùng chung, không I/O mạng; task vẫn dưới trần mềm 3300 s. DB/API: không migration, `text.json` cùng schema; job `contract` xanh.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | R-07 / MNT | `_chain_scale_found` chép lại `_chain_samples` (lọc `span_px` + `parse_length_mm` + `classify_scale_range`, id `t<i>-chain`) và phép tách trục chữ dọc của `_anisotropy` trong `apps/worker/pipeline_build/build.py:369-392`; vế hai trục viết lại `axis_scales` (`packages/domain/scale/infer.py:160`) bằng `all(...)`. Docstring tự nhận "cùng phép của bước dựng" — hai bản sẽ trôi: đổi luật mẫu ở bước dựng mà quên `tasks.py` thì T4 đọc lại (hay không) theo luật cũ, lặng lẽ, không test nào nối hai bên. | `apps/ml/text/tasks.py:120-137`; `apps/worker/pipeline_build/build.py:369-392` | Đưa `chain_samples(texts)` và `is_vertical(box)` vào `packages/vision/dimensions/chains.py` (cạnh `densest_cluster`, cả hai app đã nhập được), dùng ở `build.py` và `tasks.py`; vế hai trục gọi `axis_scales(densest_cluster(across), densest_cluster(down)) is not None`. Việc chạm `pipeline_build` → giao đúng chủ ở đợt DEBT kế tiếp; ghi vào `changes/BENCH3D-22.md`. |
| 2 | P3 | PERF | T4 đọc lại **mọi** trang < 2000 px không ra chuỗi — 61/80 trang bench (F 21/24, E 12/12) — thêm một lượt OCR CPU trên 4× số điểm ảnh (làn đo trong container tải nặng: ×2,5 trung vị, p90 ×5,4, max 128 s; r5 thật 12–20 s/bản nên hiện chấp nhận được). `_stretch` thêm bản float32 của ảnh phóng (tới ~4000×4000×3 ≈ 190 MB) trong worker ml. | `apps/ml/text/tasks.py:97-111`, `:148` | Bỏ lượt lại khi lượt thường không có chữ nào `parse_length_mm` đọc ra độ dài (ý làn đã nêu, chưa đo); giãn bằng bảng tra 256 mức `cv2.LUT` thay cho phép float32. Ghi giá thời gian vào `changes/BENCH3D-22.md`. |
| 3 | P3 | LOG | `UPSIDE_DOWN_SUSPECT` bắt cả nhãn 3 chữ số có 0 đầu (`001`, `012`: số căn/bản vẽ/trục) ở mọi hướng hộp, không riêng chữ dọc như ca f-19. Nhãn đối xứng 0/1/8 (vd `001`) đọc 180° có thể ra `100` cùng độ dài ≥ 0,5 → thành số 100 mm; nếu chữ có `span_px` nó thành mẫu chuỗi sai. Chưa thấy ca thật (ch-14 `001` lật ra `10D`), xác suất thấp. | `apps/ml/text/reader.py:82`, `:356-367` | Đòi thêm lượt 180° có tin cậy ≥ `UPRIGHT_SURE_CONFIDENCE`, hoặc chỉ nghi ngược khi chuỗi ≥ 4 ký tự; thêm test `001`→`100`. |
| 4 | Nit | MNT | Dòng đầu cả 3 commit tóm tắt tiếng Việt; BE-00 §13.2 (dòng 538) ghi `<tóm tắt tiếng Anh>` (hook không kiểm ngôn ngữ). Commit 7556811e tách `Prompt:` khỏi `Co-Authored-By:` bằng dòng trống. | 3 commit nhánh | Squash merge: đặt tiêu đề squash tiếng Anh, vd `fix(ml): reread upside-down numbers and small pages without chain scale`. |

Không có P0/P1. P2 duy nhất của Codex review (lượt 180° nhận quá rộng) đã sửa, có test.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 3,5 | 0,35 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 3,5 | 0,105 |
Tổng: 4,56 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1, điểm 4,56 ≥ 4,0. T2 sửa đúng gốc (lượt 0° chắc chắn nhưng ra số 0 đầu thì kiểm lượt 180°, nhận có điều kiện chặt), T4 chỉ nhận lượt đọc lại khi nó ra tỉ lệ chuỗi và không giành ca hai trục của bước dựng; có test âm cho mọi nhánh nhận/từ chối. CI GitHub Actions trên đúng SHA đầu nhánh xanh 24/24, `apps/ml/text` 98,68/97,14, tổng 99,32/97,55. Bench: f-19, ch-01 lên, không ca có đáp án xấu đi.

Điều kiện để merge: không có điều kiện chặn. Ghi #1 (gom `chain_samples`/trục chữ dọc vào `packages/vision/dimensions/chains.py`), #2 (giá thời gian đọc lại) vào `changes/BENCH3D-22.md` hoặc đợt DEBT kế tiếp; #3 gom cùng đợt. Squash với tiêu đề tiếng Anh (#4).
