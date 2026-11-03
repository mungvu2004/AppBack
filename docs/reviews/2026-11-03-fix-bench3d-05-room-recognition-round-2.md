# Review merge fix/bench3d-05-room-recognition → main (lượt 2)

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh: 6160eb8bc694 (PR #35, `MERGEABLE`; trên phán quyết lượt 1 8342cad0; merge-base = `origin/main` 08947af4e21d)
- Phạm vi kiểm: đích, theo R-33b lượt ≥ 2. Diff vòng sửa `8342cad0..6160eb8b` chỉ chạm logic đặt tên phòng trong `rooms.py`, test và `changes/BENCH3D-05.md`; không chạm phụ thuộc, migration, hợp đồng FE hay cổng, nên không rơi vào điều kiện (2)–(7). CI vẫn chạy đầy đủ nên dẫn số đầy đủ.
- Cổng: phạm vi đầy đủ (CI GitHub Actions run 41560560885). Run này là workflow CI, head `6160eb8bc6949bd2eb1f39ebf3c4fba6ccd0a2f2` = đầu nhánh (checkout `61a6aa5`, tức merge của 6160eb8b vào 08947af4), kết luận `success`, không job nào khác `success`. CodeQL (run 41560560879) và Commits (run 41560560779) trên cùng SHA: `success`. Shard unit từ 3113 lên 3115 test passed so với run lượt 1 41558927655, nghĩa là hai test mới đã chạy. Reviewer không chạy cổng hay pytest tại chỗ (người dùng duyệt dùng CI vì máy đang chụp 3D).
- Độ phủ (job `coverage` 125671588962, artifact `cov-*` của chính run 41560560885; `coverage_gate`: đạt; `case_gate`: đạt): tổng dòng 99,31% · nhánh 97,50%. Gói bị chạm `apps/worker/pipeline_build`: 98,27% / 93,36%. Đều ≥ 90/90. Số trùng lượt 1 đến hai chữ số thập phân vì gói lớn và các dòng mới đều được phủ; đã kiểm artifact là của run này.

## Phạm vi

- Cây sạch, HEAD = `origin/fix/bench3d-05-room-recognition`. Commit mới `6160eb8b fix(rooms): keep text trust honest and guard open-space guesses`, đúng Conventional Commits, có `Prompt: BENCH3D-05`.
- 3 tệp, +77/−16. Không pragma, `noqa`, `type: ignore`, skip/xfail; không hạ ngưỡng; không chạm tệp cấm.

## Soát các finding lượt 1

| # lượt 1 | Mức | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 nhãn chữ bị đè vẫn tin cậy 1,0 | P2 | **Đã giải** | `rooms.py:931-935`: nguồn là `"text"` chỉ khi `text is not None and text == label` (`RoomLabel` là dataclass, so sánh theo giá trị), còn lại là `"inferred"`. Test `test_rooms.py:922-924` khẳng định "SANH" 20 m² thành `livingRoom` với `confidence < 1.0`. Nếu quay lại `"text" if text` thì phòng tường kín có tin cậy 1,0 (đúng như test hành lang mới khẳng định `== 1.0`), nên test này **chặn được** hồi quy. |
| 2 nhánh dự phòng tính cả nhãn hình học | P2 | **Đã giải** | `rooms.py:639`: `read_level` thay `any(named)`, truyền từ `build_rooms` (`:927-929`). Test `test_level_named_only_by_geometry_gets_no_living_room_guess` (`test_rooms.py:956-971`): tầng không chữ, không đồ đạc, có hộp kỹ thuật 2 m² và phòng 20 m², khẳng định `[("other", …), ("utility", "hộp kỹ thuật")]`. Với mã cũ, hộp kỹ thuật làm `any(named)` đúng và phòng 20 m² thành `livingRoom`, nên test **chặn được**. |
| 3 hành lang rộng → phòng khách chỉ dựa một mẫu | P2 | **Đã giải** (còn P3 mới #1 bên dưới) | `rooms.py:632-637`: "corridor" chỉ đổi khi `_depth_mm > _CORRIDOR_DEPTH_MM` (2,5 m). Ngưỡng có lý do miền (hành lang 1,2–2 m) và cách xa mẫu bench ch-11 (sâu 3,6 m), nên không chỉnh khít theo ca. Test `test_long_narrow_hall_stays_a_hall` (`test_rooms.py:948-953`): hành lang có chữ 14 × 1,5 m = 21 m² giữ `corridor`, tin cậy 1,0; mã cũ cho `livingRoom`, nên test **chặn được**. Bếp không bị chặn theo hình dạng; chấp nhận vì ngưỡng 18 m² của bếp có lý do miền riêng. |
| 4 nhánh lô gia hẹp/lộ chạy cả tầng có chữ, không test âm | P3 | **Chấp nhận làm nợ** | Docstring `_FACADE_MM` (`rooms.py:118-125`) nay khớp mã ("mọi tầng đã đọc được") và ghi rủi ro ô thang/giếng trời. `changes/BENCH3D-05.md:8` ghi nợ kèm lý do: cn-07 cần nhánh này trên tầng có chữ, và chưa có cách phân biệt rẻ. Lý do đứng được, không phải "để sau": tên suy có nguồn `inferred` (0,6) nên vào hàng duyệt, sai thì người duyệt sửa được, không mất dữ liệu. |
| 5 chỉ mô phỏng trên chính layer r2 | P3 | **Chấp nhận làm nợ** | `changes/BENCH3D-05.md:8` ghi rõ chưa chấm trên tập giữ lại. Nên chấm `bench-can-ho` trong lượt bench kế. |
| 6 docstring `_open_space_labels` | Nit | **Đã giải** | `rooms.py:621-627`: dòng tóm tắt đứng riêng. |

## Finding mới
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG | `_depth_mm` lấy cạnh ngắn của hộp bao xoay nhỏ nhất. Hành lang hình L/T (rất hay gặp ở hành lang chung tầng điển hình: hai nhánh rộng 1,5 m dài 8 m và 6 m) có hộp bao sâu ~6 m > 2,5 m, nên vẫn thành phòng khách khi tầng không có chữ "phòng khách". Nay nguồn là `inferred` (0,6, vào hàng duyệt) nên tác động giảm, nhưng luật "hành lang hẹp giữ nguyên" chỉ đúng cho hành lang thẳng. | `apps/worker/pipeline_build/rooms.py:636` | Đo bề rộng thật thay vì hộp bao, ví dụ `shapely.Polygon(outline).buffer(-_CORRIDOR_DEPTH_MM / 2).is_empty` (không chứa nổi hình tròn đường kính 2,5 m thì là hẹp), kèm một test hành lang L 21 m². Ghi vào `changes/BENCH3D-05.md` nếu để lượt sau. |
| 2 | Nit | MNT | `_CORRIDOR_DEPTH_MM` không có docstring thuộc tính riêng; phần giải thích nằm trong docstring của `_OPEN_SPACE_M2`, đặt ngay trên nó (cùng kiểu Nit #7 của review BENCH3D-03). | `apps/worker/pipeline_build/rooms.py:135-138` | Khi chạm lại, chuyển đoạn "Hành lang chỉ đổi khi…" xuống dưới `_CORRIDOR_DEPTH_MM`. |

Không P0/P1/P2.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,88 / 5

## PHÁN QUYẾT: APPROVE

Cả ba P2 lượt 1 được sửa đúng chỗ gốc, mỗi cái kèm một test fail được với mã cũ: tên đè nhãn chữ nay là `inferred`, nhánh dự phòng cần tầng đã đọc được chữ hoặc đồ đạc, hành lang hẹp giữ nguyên. Ngưỡng mới 2,5 m có lý do miền và cách xa mẫu bench, không chỉnh khít theo ca. P3 #4 và #5 lượt 1 được ghi nợ trong `changes/BENCH3D-05.md` với lý do đứng được, chấp nhận. CI GitHub Actions run 41560560885 trên đúng SHA đầu nhánh `success`, độ phủ ≥ 90/90. Còn một P3 (hành lang hình L/T qua hộp bao xoay) và một Nit, không chặn merge.
