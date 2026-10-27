# Review merge fix/apt-thin-walls → main

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review · Commit đầu nhánh: 6359e53fe837 (đã có `origin/main` f802403c qua f0988a97; `main` sau đó thêm a82ebd76 PERF-03, chỉ chạm `apps/ml`, `deploy`, không giao `rooms.py`)
- Cổng: phạm vi **đầy đủ** (lượt review 1, R-33b điều kiện 1). Reviewer tự chạy `VERIFY_NAME=review-thin bash tools/verify/run.sh verify` tại 6359e53f, **mã thoát 0**, bước 0–8 đạt; bước 5: 8984 passed trong 544 s. Log: `.cache/src-out/verify/20261027T145857Z-6359e53fe837.log` (bản sao `F:/runs/bench-can-ho/verify-thin-review.log`). Khớp log tác giả `20261027T143644Z-6359e53fe837.log`.
- Độ phủ: tổng dòng 99,48% · nhánh 97,95%. Đơn vị bị chạm `apps/worker/pipeline_build` 98,78/94,07; tập file bị chạm 98,50/93,75.

## Điều kiện dừng sớm

- Cây sạch, HEAD trùng `origin/fix/apt-thin-walls`.
- Có `changes/FIX-2455.md`, `changes/FIX-2456.md`.
- 3 commit không phải merge đúng Conventional Commits, có `Prompt: SB-APT-ROOMS` và `Fix: FIX-2455|FIX-2456`.
- Diff chỉ chạm `apps/worker/pipeline_build/rooms.py`, test của nó và hai ghi chú `changes/`: không đụng charter, `openapi.json`, `APPFRONT_SHA`, `uv.lock`. Không pragma, skip/xfail, `type: ignore`, `noqa` mới. 261 dòng thêm (logic ~165) < 400.

## Bench căn hộ (reviewer tự chấm lại)

`python -I probe/rooms_score.py run9|run10` trên `layer.json` sẵn có (`score.py` cần API f14 đang tắt, không chạy):
main → nhánh: riêng 75 → 77, gộp 22 → 23, thiếu 12 → 9, đúng công năng 67 → 70, thừa 7 → 7. Khớp báo cáo.
Theo bản: ch-08 3 → 5 riêng, ch-09 6 → 7, ch-10 7 → 8, ch-12 7 → 5; 10 bản còn lại không đổi.

ch-12: main có `phòng khách` 19,14 m² + `hành lang` 3,41 m²; nhánh có một `phòng khách` 22,18 m² (Tiền sảnh + PK/bếp/ăn
gộp), `phòng ngủ 2` 9,27 → 12,4 m², `lô gia` 6,66 → 3,77 m². Thêm đường khép không thể gộp hai ô `polygonize` đã kín, nên
ở main hai phòng này là phòng mọc từ nhãn (`_seeded_outlines`) trong vùng hở; đường khép cửa mới làm vùng đó kín thành một
ô chứa hai nhãn, và `build_rooms` không tách một ô kín theo nhiều nhãn. Đây là giới hạn có sẵn bị lộ ra, không phải đoạn
khép sai. **Không chặn merge**: tổng bench tăng ở mọi cột, chỉ một bản tụt. Ghi nợ ở finding #3.

## Đã soát, không có finding

- `_door_closers`: lệch ngang tính đúng theo trục (`axis[0]` lấy Δy, `axis[1]` lấy Δx); tường dài 0 cho `along = 0`; tia
  loại tường chủ và tường chạm đầu tia (≤ `ROOM_SNAP_MM`), nên góc chữ L không tự khép vào chính nó; `intersection` chỉ
  gọi trên tường đã `intersects`. Cửa sổ trên tường ngoài mà tường đã dò xuyên qua: đoạn đè tường > nửa bị bỏ. Chỉ thêm
  đường, không bớt — không làm hở phòng đã kín.
- `_rim_outlines`: biên bao lồi suy biến (đường thẳng hàng) trả `[]`; chỉ chia ô trong dải 6 m, tra bằng `STRtree` (K18).
  Nhãn chữ thắng nhãn rìa (`text or rim or fixture`). `rim_keys` so theo bộ điểm: ô rìa bị loại khi chồng phòng > 50 %
  nên không trùng outline của phòng kín.
- PERF: `test_build_layer__perf_under_30_seconds` (20k tường, 5k hộp tịnh tiến từ bản thật, có `window`) đạt; bước 5b
  của lượt này đạt (1 test, cả bước 14,3 s).
- `_room_lines` thêm tham số có mặc định, mọi chỗ gọi cũ vẫn đúng; `build_rooms` truyền `detections, scaling`.
- Docstring đủ cho mọi hàm/hằng mới (R-01, R-02). Không đổi migration, API, hợp đồng FE.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG-01 | Ô rìa được giữ khi phần chồng lên phòng đã có ≤ 50 % diện tích ô. Phòng mọc từ nhãn (tia 6 m) có thể tràn qua khe vào ô rìa, khi đó lô gia mới chồng lên phòng đó tới một nửa — hai phòng đè nhau trong `layer`. Không có test cho trường hợp chồng một phần. | `apps/worker/pipeline_build/rooms.py:342-344` | Hạ ngưỡng (vd ≤ 5 %) hoặc lấy `face.difference(union phòng)` rồi kiểm lại `_RIM_M2`/`_RIM_FILL`; thêm một test phòng mọc từ nhãn chồng một phần ô rìa. |
| 2 | P3 | TEST-01 | Ba điều kiện FIX-2456 thêm để hộp `window` trên tường ngoài không đẻ dải thừa (đoạn đè tường > nửa, lệch ngang > min(300, ¼ cạnh dài) + ½ cạnh ngắn, hộp phía sau đầu tường) chỉ có test đường chính (`test_window_box_closes_glass_partition_from_a_stub_inside_it`), không có ca âm khẳng định số phòng không đổi. Bench "thừa 7 → 7" là bằng chứng ngoài repo. | `apps/worker/pipeline_build/tests/test_rooms.py:476` | Thêm 1 test: hình chữ nhật kín, hộp cửa sổ nằm trên tường ngoài (tường dò xuyên qua, và tường hở đúng khe cửa sổ) → số phòng như khi không có hộp. |
| 3 | P3 | OBS-01 / R-34 | Tụt ch-12 (riêng 7 → 5, Tiền sảnh gộp vào phòng khách) đã biết nhưng không ghi trong `changes/FIX-2455.md` hay `FIX-2456.md`; nguyên nhân gốc (một ô kín chứa hai nhãn khác công năng không được tách) chưa có dòng nợ. | `changes/FIX-2455.md` | Thêm một dòng "Tụt đã biết" vào ghi chú và một dòng nợ cho đợt sau: tách ô kín có ≥ 2 nhãn khác công năng (vd theo đường nối cửa/đường chia Voronoi giữa hai tâm nhãn). |
| 4 | Nit | MNT-02 | `_door_closers` ~75 dòng, một vòng lồng hai tầng với 6 điều kiện loại; biến `door` và hằng `_DOOR_*` nay dùng cả cho `window`. | `rooms.py:156-232` | Tách thân vòng trong thành `_closer_from_tip(...)`; đổi `door` → `opening`. |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 4 | 0,40 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |

Tổng: **4,60 / 5** · P0: 0 · P1: 0 · P2: 0 · P3: 3 · Nit: 1

## PHÁN QUYẾT: APPROVE

Cổng đầy đủ do reviewer tự chạy thoát 0, độ phủ đơn vị bị chạm ≥ 94% nhánh. Bench reviewer chấm lại tăng ở mọi cột (riêng +2, thiếu −3, công năng +3, thừa giữ 7). Tụt ch-12 là giới hạn có sẵn (ô kín nhiều nhãn không tách) bị lộ khi khe cửa được khép, không chặn merge. Không P0/P1/P2, điểm 4,60 ≥ 4,0. Ba P3 và Nit vào đợt nợ kế, chủ SB-APT-ROOMS. Gộp bằng merge commit như các nhánh trước; main mới chỉ thêm a82ebd76 (PERF-03, không giao file).
