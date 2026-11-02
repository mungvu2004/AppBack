# Review merge fix/bench3d-02-walls-openings → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: f68e61f2b701 (PR #31; `origin/main` 167ab02a6be8, merge-base e86e0b41c3de — `main` đi thêm chỉ đổi CI, không chạm tệp của nhánh)
- Cổng: phạm vi đầy đủ (CI GitHub Actions run 41480385506) — người dùng quyết định dùng CI thay `run.sh verify` tại chỗ (máy bận chạy chụp 3D). Run 41480385506 (CI, head `f68e61f2`, `success`): lint, typecheck, unit, integration, ml, contract, build, changes, coverage đều `pass`. Run 41480385501 (CodeQL, `success`). Commits: run 41480385484 `failure` (bước `tools.ci.commits` hỏng với tiêu đề PR cũ "fix(walls): tee thickness, hairline junk, wide doors, envelope gaps (BENCH3D-02)"), run 41483913607 `success` với tiêu đề PR hiện tại — cùng head SHA. SHA đầu nhánh = SHA CI = `f68e61f2b7019ef7670ea60afe9b18ddd1ab21d8`.
- Độ phủ: tổng dòng 99,33% · nhánh 97,48% (job coverage, `coverage_gate: đạt`) — gói bị chạm: `apps/worker/pipeline_build` dòng 98,17% / nhánh 93,04%; `packages/vision` dòng 99,25% / nhánh 96,81%.

## Phạm vi

- Cây sạch. Ba commit, dòng đầu đúng mẫu, cả ba có `Prompt: BENCH3D-02`: `df12ae72 fix(walls)` (C1 + C2), `7d38983d fix(openings)` (C3 + C4), `f68e61f2 fix(walls)` (C5). Có `changes/BENCH3D-02.md`.
- 8 tệp, +550/−14; mã logic ~280 dòng (`geometry.py` +260, `vectorize.py` +10, `build.py` +12), dưới ngưỡng 400 của MNT-05.
- Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `type: ignore`, `noqa`, skip/xfail mới.
- Không đổi API, DB, hợp đồng FE–BE. Tường khe mới dùng `kind="partition"` như tường dựng sẵn (`geometry.py:1112`); trần 2400 mm của khe do `_near_ends` (`OPENING_GAP_MAX_MM`) đảm bảo.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG / R-19 | `_bridge_hosts` lấy **mọi** tường có đầu mút trùng một đầu đoạn nối, không kiểm thẳng hàng. Ở chữ T/L ngay mép khe (vách `P` vuông góc gặp tường ngoài `A` đúng tại đầu khe — cửa sát vách ngăn), `P` cũng là "tường chủ". Nhánh khe < 600 mm, `_extend_host` chọn tường đầu tiên có **cuối** ở khe (hoặc `hosts[0]`): nếu đó là `P` (tuỳ thứ tự tường/hướng vẽ của bộ vector hoá) thì đầu `P` bị dời sang đầu kia khe → `P` thành tường xiên, vỏ không khép đúng. Lỗi im lặng (không có kiểm toàn vẹn critical nào bắt). Nhánh ≥ 600 mm chỉ bị ảnh hưởng nhẹ (`max` bề dày, `min` tin cậy gồm cả `P`). Không test nào dựng khe sát chữ T. | `apps/worker/pipeline_build/geometry.py:1163-1165`, `:1200-1201`, `:1241` | Lọc tường chủ thẳng hàng với đoạn nối, ví dụ trong `_bridge_hosts`: giữ `wall` khi `abs(cos(wall, bridge)) >= _HUG_COS_MIN`. Thêm một test: `_box_with_top_gap(2000, 2500)` + vách `wall_px(2000, 4000, 2000, 0)` đứng trước trong danh sách, khẳng định vách giữ nguyên hai đầu. |
| 2 | P3 | MNT / R-01 | Khối hằng số mới chèn giữa `_MIN_DOUBLE_DOOR_MM` và docstring của nó: docstring của `_SPLIT_GAP_MM` ("Hai ô mở cùng loại…") nằm sau `_INFERRED_DOOR_CONFIDENCE`, docstring của `_MIN_DOUBLE_DOOR_MM` ("Cửa đôi hẹp hơn 600 mm…") nằm sau đó — hai chuỗi trôi, `_SPLIT_GAP_MM` và `_MIN_DOUBLE_DOOR_MM` không còn tài liệu đi kèm. | `apps/worker/pipeline_build/geometry.py:59-71` | Đưa mỗi docstring về ngay dưới hằng số của nó. |
| 3 | P3 | R-07 | `_gap_door` chép lại luật chiều mở C3 của `_read_swing` (cánh → `left/right`, > 1200 → `double`, không cánh ≥ 1500 → `sliding`); docstring tự ghi "cùng luật C3". Đổi ngưỡng một nơi sẽ lệch nơi kia. | `apps/worker/pipeline_build/geometry.py:1168-1185` và `:975-979` | Tách một hàm `_swing_for(width_mm, leaf) -> SwingDirection` dùng chung cho cả hai. |
| 4 | P3 | LOG | C4 lệch C3: `_merge_split` biến cửa bản lề gộp > 1200 mm thành `double` kể cả khi mảnh dẫn không đọc được cánh (`lead.leaf is None`) và tổng rộng ≥ 1500 mm — theo C3 trường hợp này phải là `sliding`. | `apps/worker/pipeline_build/geometry.py:1072-1073` | `swing = "sliding" if lead.leaf is None and width >= _SLIDING_MIN_MM else ("double" if hinged and width > _MAX_SINGLE_LEAF_MM else lead.swing)` (hoặc dùng chung hàm ở finding 3). |
| 5 | Nit | LOG | `_drop_hairlines` dùng ngưỡng tuyệt đối 40 mm; chốt an toàn chỉ là "cả bản đều mảnh". Tỉ lệ sai cỡ ×2,5 trở lên mà còn một khối ≥ 40 mm thì toàn bộ tường thật bị bỏ. | `apps/worker/pipeline_build/geometry.py:287-296` | Khi chạm lại, so với trung vị bề dày đo (vd bỏ khi `< min(40, 0,4·trung vị)`). |
| 6 | Nit | MNT | `door.height_mm or 2200` / `door.sill_mm or 0`: nhãn `door` luôn có 2200/0 (`labels.py:71`), fallback là số ma thuật chết; `_candidate` xử lý `None` bằng cách bỏ ô mở (`:937`). | `apps/worker/pipeline_build/geometry.py:1274-1275` | Bỏ fallback, dùng thẳng giá trị nhãn (hoặc một hằng có tên). |
| 7 | Nit | PERF | `close_envelope_gaps` quét tuyến tính mọi tường (`_bridge_hosts`, `inner.intersects`) và mọi phòng (`wall_side`) cho mỗi đoạn nối — O(nối × tường); phần còn lại của tệp dùng `STRtree`. Không đáng kể ở cỡ bản vẽ hiện tại. | `apps/worker/pipeline_build/geometry.py:1239-1250` | Để nguyên; dùng `STRtree` nếu bản vẽ lớn làm chậm bước dựng. |

Không có nợ tác giả nêu trong `changes/BENCH3D-02.md`; finding 1 nếu không sửa trước khi merge thì ghi một dòng nợ ở lô DEBT kế tiếp (R-34).

## Soát theo miền

- **LOG**: C1 `_same_thickness` đúng chiều (lớn ≤ 1,25·nhỏ); C2 `_inside` yêu cầu song song, mỏng hơn, hai đầu trong thân ± ½ dày — vách nối tiếp quá đầu tường được giữ (có test); `_drop_dangling_nibs` tha mẩu chạm hộp ô mở (nới một bề dày). C3 đổi hành vi khi không có trang (cửa ≥ 1,5 m → `sliding`), đã ghi trong `changes`. C4 gộp sau khi đã giải chồng, nên không sinh chồng mới cùng loại. C5: khe trong nhà giữ hở; đoạn nối cắt tim tường khác bị bỏ qua, nên cặp A–C vắt qua B không sinh tường chồng.
- **SEC/CON/RES/DB-API**: không chạm.
- **PERF**: xem Nit 7; `_drop_dangling_nibs` ngắt sớm theo độ dài trước khi truy vấn cây.
- **TEST**: có test cho từng nhánh C1–C5 (bề dày qua chữ T, nét mảnh, trong thân, mẩu lơ lửng, cửa lùa/hai cánh/không trang, gộp cửa sổ, khe ngoài 900/1600, khe hẹp kéo cuối/kéo đầu + dời offset, khe trong nhà, đọc cánh từ trang), và test e2e 10 hạt giống bỏ hộp cửa đi vẫn ra đúng một cửa đoán, giữ số phòng, không lỗi toàn vẹn critical. Thiếu case chữ T sát khe (finding 1).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,70 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1, điểm 4,70 ≥ 4,0. CI đầy đủ xanh trên đúng head `f68e61f2` (run 41480385506, độ phủ tổng 99,33/97,48, gói bị chạm ≥ 93% nhánh). Đề nghị sửa finding 1 trước khi merge (lọc tường chủ thẳng hàng + một test, vài dòng); nếu merge ngay thì ghi finding 1 thành dòng nợ ở lô DEBT kế tiếp. Finding 2–4 và các Nit sửa khi chạm lại tệp.
