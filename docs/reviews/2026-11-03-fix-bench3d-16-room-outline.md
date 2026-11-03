# Review merge fix/bench3d-16-room-outline → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: ebd222746890 (PR #44; merge-base 297f2067ea93 = `origin/main` hiện tại; PR `MERGEABLE`/`CLEAN`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions run 41598179675) — người dùng quyết định dùng CI thay `run.sh verify`. Run 41598179675 (workflow CI, `pull_request`, head `ebd222746890facf355bb9329c5ff3659ff45d80` = đầu nhánh) `success`; `gh pr checks 44`: 24/24 pass (changes, commits, lint, typecheck, unit/integration/ml shards, build, contract, coverage, perf, CodeQL). Hai lượt trước đỏ ở `perf`: 41589654836 (a0a44c72) và 41595739226 (af27da66). Reviewer không chạy cổng tại chỗ; ba probe hình học chạy qua `bash tools/verify/run.sh shell` (script ở scratchpad, không ghi vào repo), mã thoát 0.
- Độ phủ (job `coverage` của run 41598179675, `tools.coverage_gate` đạt): tổng dòng 99,32% · nhánh 97,52% — gói bị chạm `apps/worker/pipeline_build` 98,44% / 94,03%. ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước, nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch, HEAD = `origin/fix/bench3d-16-room-outline`. `origin/main..HEAD` có 7 commit; nhánh **đã gộp** `fix/bench3d-15-envelope-closers` (PR #43) tại 5642823f (merge 1619bd6b). Review này chỉ chấm phần riêng của L5:
  `git diff origin/fix/bench3d-15-envelope-closers...HEAD` = `rooms.py` +266/−24, `test_rooms.py` +174/−16, `changes/BENCH3D-16.md` +10. Phần BENCH3D-15 (`geometry.py`, `build.py`, `test_envelope_closers.py`…) thuộc phán quyết riêng của #43.
- Commit L5: `47e7f31e fix(pipeline-build): keep rooms open to the facade via flat envelope`, `a0a44c72 fix(pipeline-build): split holed envelope faces, hand open edges to L4`, `af27da66 perf(pipeline-build): skip covered envelope blocks before noding`, `ebd22274 perf(pipeline-build): buffer envelope per cluster, gate exposed lengths` — dòng đầu đúng mẫu, đều có dòng `Prompt: BENCH3D-16`; merge 1619bd6b là thông điệp git tự sinh (hook và `tools.ci.commits` bỏ qua). Job `commits` xanh.
- **#43 đi trước #44 hai commit** chưa có trong nhánh này: `0397ed30` (khớp trùng vỏ theo loại/hướng) và `dfbd9586` (tường vai cạnh khe bắc cầu), cùng chạm `geometry.close_envelope_gaps` — chính hàm nhận `closers_out` không nhãn mới của L5. `git merge-tree HEAD origin/fix/bench3d-15-envelope-closers` không xung đột, nhưng tổ hợp chưa được CI chạy.
- Logic L5 ~200 dòng (phần còn lại docstring/test) — dưới 400. Có `changes/BENCH3D-16.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore` mới, skip/xfail, không hạ ngưỡng.

## Soát nội dung

- **Đường bao căn** (`rooms.py:560-646`): đóng hình thái tim tường + đoạn khép (nới 2 m đầu vuông/góc vát, lấp lỗ, co 2 m), nút với `lines`, `polygonize` lại. Ô thành phòng khi trừ phòng có sẵn còn > 50 %, ≥ 2 cạnh hộp bao sát đường khép, có nhãn hay ≥ 4 m², bao lồi không ôm phòng có sẵn quá 0,5 diện tích ô. Thứ tự trong `build_rooms` đúng docstring; chữ ký `build_rooms` không đổi (BRIEF-dot3).
- **Codex review phát hiện 1 (P1, phòng mới phủ phòng kín)**: đã sửa — `_simple_parts` (`:687-702`) cắt ô có lỗ qua tâm lỗ thành mảnh không lỗ, outline làm tròn chồng phòng có sẵn quá dải dung sai thì bỏ (`:635-637`). Cắt luôn đi qua phần trong của lỗ (tâm khối của lỗ liên thông nằm trong khoảng chiếu mở của nó), mỗi lượt bớt ≥ 1 lỗ nên đệ quy dừng. Test `test_envelope__closed_room_inside_the_open_space_is_not_covered`.
- **Codex review phát hiện 3 (P2, biên hở không giao cho L4)**: đã sửa — biên hở trên đường bao (trừ lô gia) thành `RoomCloser` không nhãn, đầu chuỗi bắt vào đầu tường (`_open_edge_closers`, `:736-756`), xuất qua `closers_out` sau `_door_closers`/`_gap_closers`. Test tích hợp `test_envelope__open_edges_go_to_close_envelope_gaps` chạy `build_rooms → close_envelope_gaps` và kiểm vỏ khép kín (56 m²).
- **`_grown`** (`:649-675`): gom cụm bằng lan nhãn min + nhảy con trỏ trên cặp `intersects` (đối xứng) — điểm dừng đúng là nhãn nhỏ nhất của thành phần liên thông, đơn điệu giảm nên dừng. Xem finding #3 về cụm chạm nhau tại một điểm.
- **`_exposed_lengths(outlines, wanted)`**: chỉ đo cho phòng cỡ lô gia, nông, không đồ "không lô gia", còn thiếu mặt ngoài. Điều kiện `from_facade` tương đương bản cũ (khi `facade_mm ≥ _FACADE_MM` thì `max(facade, 0)` vẫn đạt), `_depth_mm` vẫn chỉ tính khi cần (đánh giá ngắn mạch).
- **`bare = [*centrelines, *lines[len(walls):]]`**: đúng vì `_room_lines` trả đúng một đường mỗi tường rồi mới tới cầu/đoạn khép.
- **Bao/khe**: test âm có đủ — sân chữ U rộng hơn 4 m ở ngoài, vành giữa căn và khung ảnh không thành phòng, hành lang dài hở một đầu không thành lô gia; đồ đạc thắng cờ lô gia nông.
- **Probe tại chỗ (run.sh shell, HEAD ebd22274)**: (a) cụm tường chạm cụm khác đúng một điểm → mất phòng (af27da66 vẫn ra 56,0 m²); (b) lượt fuzz + e2e thật (222 test) chạm nhánh `except GEOSException` 1 lần với **mọi** phòng có sẵn đều hợp lệ (`is_valid`) — lỗi là độ bền GEOS, không phải "phòng tự cắt" như chú thích; phòng nơ (bowtie) đưa thẳng vào `_envelope_outlines` vẫn ném `TopologyException` ở đoạn xét từng ô; (c) khách hở góc 10 × 6 m có cột 0,4 × 0,4 m khép kín ở giữa → hai phòng 31,42 + 25,92 m² (không cột: một phòng 57,5 m²).
- **PERF** (`test_build_layer__perf_under_30_seconds`, thời gian testcase trong `junit-perf.xml` của CI, gồm lượt khởi động): `main` 297f2067 15,5 s → #43 dfbd9586 23,3 s → #44 a0a44c72 38,8 s → af27da66 31,3 s → ebd22274 **27,6 s**. Thông điệp ebd22274 ghi "local 21.5 s vs origin/main 20.5 s" — trên CI chênh với `main` là +12 s, không phải +1 s.
- SEC/CON/RES: hàm thuần, không đầu vào người dùng mới, không trạng thái dùng chung, không I/O. DB/API: không migration, không đổi `layer.json`/hợp đồng; job `contract` xanh. Tường vỏ mới dựng từ closer không nhãn đi qua đường có sẵn của #43.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG | Ô đường bao có lỗ bị cắt thẳng qua **mọi** phòng có sẵn nằm giữa ô, kể cả phòng rác nhỏ sẽ bị bỏ ở `roomTooSmall`. Probe: khách hở góc 57,5 m² có cột 0,4 × 0,4 m (4 tường khép kín) ở giữa thành hai phòng 31,42 + 25,92 m² ngăn bởi vết cắt không có tường; nhãn chữ chỉ rơi vào một mảnh, mảnh kia thành "phòng khác". Đường khép kín (`_room_outlines`) xử lý cùng ca bằng vòng ngoài nên ra một phòng — hai đường cho kết quả khác nhau. Cột/hộp kỹ thuật giữa phòng khách hở là ca thường gặp ở căn hộ VN. | `apps/worker/pipeline_build/rooms.py:624-631`, `:687-702` | Trước `_simple_parts`, lấp các lỗ có diện tích < `MIN_ROOM_AREA_M2` (hoặc chỉ đưa vào `held`/`room_tree` phòng có sẵn ≥ `MIN_ROOM_AREA_M2`), vì các phòng đó đằng nào cũng bị bỏ. Thêm test khách hở góc có cột giữa → một phòng. |
| 2 | P2 | PERF | Trần K18 (20 000 tường) còn ~2,4 s (testcase 27,6 / 30 s, CI): L4+L5 cộng +12 s so với `main` (15,5 s), riêng L5 ≈ +4 s trên #43. Nhánh chưa có hai commit cuối của #43 nên con số sau khi gộp chưa đo. Chạm trần trên `main` làm đỏ `perf` của mọi PR sau. Đoạn nặng còn lại: `unary_union` + `polygonize` lại **toàn bộ** `lines` khi còn ≥ 1 khối hở (`:615-616`, lặp việc của `_room_outlines`), và `union_all` toàn bộ `bare` trong `_grown` (`:655`). | `apps/worker/pipeline_build/rooms.py:615-616`, `:655` | Điều kiện merge: sau khi #43 vào `main`, cập nhật nhánh từ `main`, CI `perf` phải xanh. Ghi nợ: chỉ nút/polygonize `lines` trong tầm các khối còn hở (`STRtree` theo `rings`), mục tiêu đưa testcase về ≤ 25 s. |
| 3 | P3 | LOG | `_grown` trả `GeometryCollection` các hình nới theo cụm; cụm có hai hình nới chạm nhau đúng một điểm (đầu tường lệch đúng 4 000 mm cả hai trục) cho `MultiPolygon`, `get_parts` chỉ bóc một tầng nên `get_exterior_ring` → `None` → `POLYGON EMPTY`, cả cụm bị bỏ khỏi đường bao **lặng lẽ**. Probe: khách hở góc + một tường lẻ chạm góc → 0 phòng (af27da66, nới cả khung: 56,0 m²). Hồi quy do ebd22274; docstring `_grown` khẳng định "kết quả như nới cả khung một lần" — sai ở ca này. Xác suất thấp (cần trùng toạ độ chính xác). | `apps/worker/pipeline_build/rooms.py:595`, `:668-675` | `return shapely.GeometryCollection(list(shapely.get_parts(grown)))` (bóc `MultiPolygon` của từng cụm); thêm test hai cụm chạm góc. |
| 4 | P3 | LOG | Chỉ một phép overlay được bọc `except GEOSException`; các phép cùng loại trên cùng dữ liệu theo từng ô (`union_all(near)`, `shell.difference(held)`, `hull.intersection`, `outline.intersection(held)`, `_band`) không bọc. Probe: nhánh `except` bị chạm trong fuzz dù mọi phòng có sẵn hợp lệ, tức GEOS ném với đầu vào hợp lệ; phòng nơ làm `_envelope_outlines` ném `TopologyException` ra ngoài → cả lượt dựng hỏng. Chú thích "phòng tự cắt (fuzz)" không khớp nguyên nhân đo được. Chưa có đầu vào thật tái hiện. | `apps/worker/pipeline_build/rooms.py:605-608`, `:621-646`, `:719` | Đưa phòng có sẵn lên lưới 1 mm (`shapely.set_precision(taken, 1.0)`, cùng lưới `merged`) trước mọi overlay, hoặc bọc thân vòng lặp từng ô để bỏ ô lỗi thay vì hỏng cả tầng; sửa chú thích cho đúng. |
| 5 | P3 | LOG | Góc mặt ngoài hở hai đầu (vách kính góc) được khép thành **khấc** 2 × 2 m vào trong phòng (đóng hình thái đầu vuông/góc vát không kéo dài hai tường gặp nhau): test xác nhận vỏ 56 m² thay vì 60 m², và L4 dựng hai tường đặc theo khấc (`(8000,6000)→(8000,4000)→(10000,4000)` trong probe) — tường nằm trong không gian khách thật. Đúng như docstring nói "góc khuyết chữ L … vẫn ở ngoài bao", nên là giới hạn đã biết, nhưng `changes/BENCH3D-16.md` không ghi. | `apps/worker/pipeline_build/rooms.py:592-600`; `apps/worker/pipeline_build/tests/test_rooms.py:1051-1052` | Ghi giới hạn vào `changes/BENCH3D-16.md`. Lượt sau: khi hai đầu tường tự do vuông góc và giao điểm phần kéo dài nằm trong tầm `_ENVELOPE_CLOSE_MM`, khép bằng hai đoạn kéo dài tới giao điểm thay cho khấc. |
| 6 | P3 | TEST | Tên test `test_build_rooms__corner_gap_over_limit_gives_no_room` nay khẳng định `len(rooms) == 1` — tên nói ngược hành vi. | `apps/worker/pipeline_build/tests/test_rooms.py:110-117` | Đổi tên, vd `…corner_gap_over_limit_has_no_closer_but_envelope_keeps_room`. |
| 7 | Nit | OBS | Thông điệp ebd22274 ghi số đo perf máy cục bộ (21,5 s vs `main` 20,5 s) lệch hẳn CI (27,6 s vs 15,5 s); `changes/BENCH3D-16.md` không ghi số. | commit ebd22274; `changes/BENCH3D-16.md:8-9` | Ghi số CI (run id) vào `changes/BENCH3D-16.md`. |
| 8 | Nit | MNT | Dòng `Prompt:` tách khỏi `Co-Authored-By:` bằng dòng trống nên `git interpret-trailers`/`%(trailers)` không thấy nó (CI vẫn xanh vì đọc thân). | 4 commit L5 | Để `Prompt:` và `Co-Authored-By:` cùng khối trailer cuối. |

Không có P0/P1. Hai P1/P2 của Codex review cho L5 (phát hiện 1, 3) đã sửa, có test.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3 | 0,45 |
| PERF | 10% | 3 | 0,30 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,33 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1, điểm 4,33 ≥ 4,0. L5 cứu phòng hở mặt ngoài bằng đường bao căn, có test âm cho sân, vành khung ảnh, hành lang; hai lỗi Codex review chỉ ra (phủ phòng kín, biên hở không giao cho L4) đã sửa và có test tích hợp với `close_envelope_gaps`. CI GitHub Actions trên đúng SHA đầu nhánh xanh 24/24, độ phủ gói và tổng ≥ 90/90.

Điều kiện để merge:
1. **Merge PR #43 trước.** Sau đó cập nhật nhánh này từ `main` (lấy `0397ed30`, `dfbd9586` của #43 — cùng chạm `close_envelope_gaps` nhận closer của L5; `merge-tree` không xung đột) và chờ CI chạy lại xanh, **đặc biệt `perf`** (`test_build_layer__perf_under_30_seconds` < 30 s; nếu testcase > 28 s thì xử lý finding #2 trước khi merge).
2. Ghi nợ #1 (cắt phòng hở qua cột), #2 (perf còn dư ~8 %), #5 (khấc góc) vào `changes/BENCH3D-16.md` hoặc đợt DEBT kế tiếp; #3, #4, #6 sửa được trong vài dòng, nên gom vào cùng đợt.
