# BENCH3D-03 — công năng phòng: lô gia mặt ngoài, giường/tủ áo theo diện tích

- `apps/worker/pipeline_build/rooms.py` `build_rooms`: phòng chưa có tên (chữ, rìa, đồ đạc) 2–15 m², ≥ 3 m cạnh trên mặt ngoài nhà (biên bao lồi của đường khép, dung sai 2·`ROOM_SNAP_MM`), không giường/thiết bị vệ sinh → `loggia` (nguồn "inferred"). Chỉ khi tầng có ít nhất một nhãn chữ (tầng không đọc được chữ nào không đoán).
- `_fixture_labels`: máy giặt + ≥ 3 m mặt ngoài (không buồng tắm đứng) → lô gia trước luật thiết bị vệ sinh (chậu giặt ở lô gia không còn thành phòng tắm); máy giặt trong WC giữa nhà vẫn là phòng tắm.
- Giường chỉ làm phòng ngủ ở 6–25 m² (vùng gộp 40 m² có giường không thành phòng ngủ); tủ áo đơn lẻ chỉ làm phòng ngủ từ 8 m² (`_WARDROBE_BEDROOM_MIN_M2`, trước 6).
- `packages/vision/dimensions/rooms.py`: "sân phơi", "giặt phơi" → `loggia` (trước `utility`; chủ dự án chốt).
- Đo trên bench-3d r1 (ước bằng biên bao tim tường): 21 phòng "khác" có đáp án bị đổi, 18 đúng (lô gia/ban công/giặt phơi), 3 sai (ch-01 phòng khác 5,8 m², cn-09 khách-bếp 13,9 m², cn-19 kho 3,8 m²).
- Không đổi API, DB, migration, hợp đồng FE–BE.
- Cổng áp dụng: lint/type, test apps/worker/pipeline_build, packages/vision/dimensions. Migration/hợp đồng: không áp dụng.
