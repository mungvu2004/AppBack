# Review merge fix/bench3d-03-rooms-scale → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 59f9c5ef13c7 (PR #30; merge-base e86e0b41c3de, `origin/main` 167ab02a đi trước 6 commit chỉ chạm `.github/`, `tools/ci/`, `deploy/`, `docs/SETUP.md`, `packages/testing/fixtures/ci_split.py` — không trùng tệp nào của nhánh; PR `MERGEABLE`)
- Cổng: phạm vi đầy đủ (CI GitHub Actions run 41479184099) — người dùng quyết định dùng CI thay `run.sh verify` để tiết kiệm thời gian/RAM. Run 41479184099 (workflow CI, head `59f9c5ef13c72597216f3bd105235d60d176ac6f` = đầu nhánh): `changes`, `lint`, `typecheck`, `unit`, `ml`, `integration`, `build`, `contract`, `coverage` đều `success`. Run 41479183988 (CodeQL, cùng SHA): `success`. Run 41483907238 (Commits, cùng SHA): `success`; lần trước 41479184065 `failure` ở `tools.ci.commits` vì tiêu đề PR cũ, đã sửa tiêu đề thành `fix(rooms): loggias, bedroom caps, shafts, scale checks` rồi chạy lại. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` của run 41479184099, `tools.coverage_gate` đạt, bước 5b case_gate đạt): tổng dòng 99,32% · nhánh 97,47% — gói bị chạm: `apps/worker/pipeline_build` 98,10% / 92,69%; `packages/domain` 99,78% / 98,70%; `packages/vision` 99,25% / 96,81%. Tất cả ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch. 3 commit, dòng đầu đúng Conventional Commits, mỗi commit có `Prompt: BENCH3D-03`:
  `0008c008 fix(rooms): infer facade loggias and cap bed/wardrobe bedroom areas`,
  `cbf4a28e fix(rooms): name doorless small rooms shafts and unnamed rooms "other"`,
  `59f9c5ef fix(scale): record per-axis scale spread and door/wall estimate spread`.
- 11 tệp, +376/−60 (mã logic ~200 dòng, phần còn lại là test và `changes/BENCH3D-03.md`) — dưới 400, không cần tách.
- Có `changes/BENCH3D-03.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore` mới, skip/xfail mới, không hạ ngưỡng (`type: ignore[arg-type]` ở `test_rooms.py:327` có sẵn, có mã).

## Soát nội dung

- **Lô gia mặt ngoài** (`rooms.py:830-839`): chỉ áp cho phòng chưa có tên từ chữ/rìa/đồ đạc, 2–15 m², ≥ 3 m biên trong dải 2·`ROOM_SNAP_MM` quanh biên bao lồi, không giường/thiết bị vệ sinh/buồng tắm đứng, và chỉ khi tầng có ≥ 1 nhãn chữ. Thứ tự `rim or fix or facade or box` đúng docstring `build_rooms`. Nguồn tên là `inferred` nên tin cậy thấp hơn nhãn chữ (test khẳng định).
- **Luật đồ đạc** (`rooms.py:609-649`): máy giặt chuyển lên trước luật vệ sinh nhưng điều kiện `(facade ≥ 3 m or không có sanitary)` và `không shower` giữ nguyên hành vi cũ cho WC giữa nhà (test `test_washer_in_bathroom_keeps_bathroom` chuyển sang lưới 3×3 để phòng giữa thật sự không chạm mặt ngoài). Giường giới hạn 6–25 m², tủ áo 8–25 m²; mỗi nhánh mới có test.
- **Tách `_fixtures_in` / `_fixture_labels`**: giữ nguyên logic gom đồ đạc, chỉ để dùng lại `found_in` cho luật lô gia — không trùng lặp.
- **Hộp kỹ thuật** (`rooms.py:574-584`, `840-844`): `STRtree` rỗng khi không có cửa vẫn chạy (test `test_small_room_without_a_door_is_a_shaft`, ca không cửa). Nhãn `double_door` có thật (`packages/ml_contracts/labels.py:16`).
- **`name_rooms`** (`packages/vision/dimensions/rooms.py:222-237`): tên sinh `phòng khác`, `phòng khác 2`…; `_NOT_LABELS` có sẵn `"phong khac"` nên tên sinh không đọc lại thành nhãn (test mới). Đã soát BE và AppFront @ `APPFRONT_SHA` 99e18dbe: không mã nào dựa vào mẫu cũ `phòng <số>`. FE nhận tên tự do (`roomLabelReviewGateway.ts:1144`).
- **"sân phơi"/"giặt phơi" → loggia**: đổi từ điển, test bảng cập nhật; tác giả ghi "chủ dự án chốt".
- **Tỉ lệ** (`build.py:344-371`, `734-741`): `_anisotropy` chỉ ghi `scaleChecks.anisotropic`, không đổi tỉ lệ đã chọn (test so với lượt không có chữ dọc). `_estimate`: `_door_scale` kẹp ≥ 1 nên không có ca 0; lệch ≤ 10 % → trung bình nhân, lệch hơn → ước cửa + `estimateSpread`. Cả ba nhánh có test. `axis_scales` trả `None` khi một trục thiếu mẫu (test).
- **`layer.json`**: `scaleChecks` là khoá gốc tuỳ chọn, `from_json` kiểm hình dạng chặt (khoá lạ, thiếu trường, sai kiểu → `ValueError`, có test). Không lên API, không đổi DB/migration/hợp đồng FE; job `contract` xanh.
- SEC/CON/RES: không đầu vào người dùng mới, không trạng thái dùng chung, không I/O mới.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG | Luật hộp kỹ thuật dựa vào "không hộp cửa nào chạm biên" nhưng không đòi tầng có ít nhất một cửa dò được. Tầng mà YOLO không ra cửa nào (ảnh mờ, âm bản, model lỗi) thì mọi phòng chưa tên < 2,5 m² (WC nhỏ OCR sót chữ, kho) đều thành "hộp kỹ thuật" — đúng loại đoán mù mà luật lô gia đã chặn bằng `labelled_level`. | `apps/worker/pipeline_build/rooms.py:840-844` | Chỉ áp `from_shaft` khi `any(d.label in _DOOR_LABELS for d in detections)`; thêm một test tầng không cửa giữ "phòng khác". Không chặn merge. |
| 2 | P3 | R-07 | `_VERTICAL_TEXT_RATIO = 1.3` chép lại `_VERTICAL_RATIO` của `chains.py` (docstring tự nói "như `_VERTICAL_RATIO`"). Hai nguồn sự thật: chỉnh ngưỡng chữ dọc ở một chỗ thì `_anisotropy` tách trục khác với `chains`. | `apps/worker/pipeline_build/build.py:95`; `packages/vision/dimensions/chains.py:40` | Đổi `chains._VERTICAL_RATIO` thành hằng công khai (vd `VERTICAL_TEXT_RATIO`) và import vào `build.py`. |
| 3 | P3 | MNT | Tên "hộp kỹ thuật" là chuỗi cứng trong `rooms.py`, nằm ngoài từ điển tên; docstring module `packages/vision/dimensions/rooms.py` vẫn khẳng định "Tên chỉ lấy từ `ROOM_USAGE_NAMES`". Câu chữ khớp FE (`verticalCores.ts:92` dùng đúng "hộp kỹ thuật" cho `utility`) nên không sai hành vi, nhưng bất biến ghi trong docstring không còn đúng. | `apps/worker/pipeline_build/rooms.py:840`; `packages/vision/dimensions/rooms.py:3-5` | Đặt hằng `SHAFT_NAME` cạnh `ROOM_USAGE_NAMES` trong `packages/vision/dimensions/rooms.py`, sửa câu docstring cho đúng. |
| 4 | P3 | DB/API | `BuiltLayer.from_json` của bản cũ chỉ nhận khoá gốc trong `_ROOT_KEYS ∪ {"scaleBasis"}`; `layer.json` do worker mới dựng có `scaleChecks` sẽ bị bản cũ từ chối. Dựng (`pipeline_build`) và lưu (`pipeline_persist`) là hai task, nên nếu rollback worker giữa hai bước thì job đang chạy hỏng ở persist. `schemaVersion` không đổi. Cùng tiền lệ `scaleBasis`, rủi ro thấp. | `apps/worker/pipeline_build/build.py:128`, `:179` | Ghi một dòng "rollback: job đang chạy giữa build và persist cần chạy lại" vào `changes/BENCH3D-03.md`; chấp nhận như hiện tại. |
| 5 | P3 | TEST | Số đo bench (18/21 phòng "khác" đổi đúng, 3 sai; trung vị bề dày ≈ 154 mm; ch-01/lowres-ch06 lệch hai phía) chỉ có trong báo cáo/docstring của tác giả, không tái hiện được từ repo hay CI; test chỉ dựng lưới tổng hợp. Ba ca sai đã ghi trong `changes/BENCH3D-03.md`; giới hạn tỉ lệ ch-01/lowres-ch06 chỉ nằm trong docstring. | `changes/BENCH3D-03.md:7`; `apps/worker/pipeline_build/build.py:80-84` | Chấp nhận (luật heuristic, có số đo). Thêm một dòng giới hạn ch-01/lowres-ch06 vào `changes/BENCH3D-03.md` để sổ nợ đầy đủ. |
| 6 | Nit | PERF | `_chain_samples(texts)` nay phân tích chữ ba lần mỗi lượt dựng. Chi phí không đáng kể. | `apps/worker/pipeline_build/build.py:290`, `:351`, `:557` | Không cần đổi. |
| 7 | Nit | MNT | Docstring thuộc tính gắn vào phép gán ngay trước nó: khối giải thích mặt ngoài nằm dưới `_NOT_LOGGIA` (không dưới `_FACADE_MM`), khối hộp kỹ thuật nằm dưới `_DOOR_LABELS` (không dưới `_SHAFT_M2`). | `apps/worker/pipeline_build/rooms.py:111-125` | Khi chạm lại, đặt docstring ngay dưới hằng nó mô tả. |
| 8 | Nit | DOC | Khi hai ước khớp, tỉ lệ là trung bình nhân cửa và tường nhưng `scaleBasis` vẫn ghi `door`. Docstring `_estimate` đã nói rõ. | `apps/worker/pipeline_build/build.py:361-371` | Không cần đổi. |

Không có P0/P1/P2. Nợ tác giả nêu (3 ca bench sai) đã có trong `changes/BENCH3D-03.md`.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,79 / 5

## PHÁN QUYẾT: APPROVE

Thay đổi khoanh gọn trong bước dựng: luật đặt tên phòng mới có điều kiện chặt (diện tích, mặt ngoài, đồ đạc, tầng có nhãn chữ), mỗi nhánh mới có test, hành vi cũ của WC giữa nhà được giữ. Phần tỉ lệ chỉ ghi nghi vấn vào `layer.json` (trừ trung bình nhân khi hai ước khớp, đã có test), không đổi API/DB/hợp đồng FE. CI GitHub Actions trên đúng SHA đầu nhánh xanh toàn bộ, độ phủ gói bị chạm và tổng ≥ 90/90. Không P0/P1/P2; năm P3 và ba Nit có thể làm ở lượt sau (ưu tiên #1: chặn luật hộp kỹ thuật khi tầng không có cửa nào).
