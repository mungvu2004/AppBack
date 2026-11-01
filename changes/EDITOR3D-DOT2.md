# EDITOR3D-DOT2 — lưu đủ các sửa của màn 3D (AppFront `feat/editor3d-dot2`)

- `domain/spatial/model.py`:
  - `Room.dressing_off`: id `DRESS-…` của đồ AI tự bày mà người dùng đã xoá, tối đa 200; vắng khoá khi rỗng. Mở lại thì FE
    không bày lại các món này.
  - `Room.ceiling_material: MaterialRef | None`: màu trần sơn trong 3D.
  - `Opening.door_style: 'pocket' | 'folding' | None`: chỉ nhận trên cửa đi `swing='sliding'` (validator).
  - `Opening.reversed`: hướng mở/lùa đảo so với luật `swingDirectionOf`; vắng khoá khi False.
- `spatial_read/wire.py` (`RoomOut`, `OpeningOut`), `spatial/diff.py` (nhật ký trường), `spatial/samples.py`
  (`PASCAL_FIELDS`, để test khứ hồi PUT/N16 có sẵn phủ trường mới).
- Không migration: tầng là tài liệu JSONB.
- **Cần người điều phối**: xuất lại `openapi.json`, nâng `tools/contract/APPFRONT_SHA` lên AppFront master có
  `feat/editor3d-dot2` (RoomSchema `dressingOff`/`ceilingMaterial`, OpeningSchema `doorStyle`/`reversed`).
- Giới hạn: id `DRESS-` sinh theo id phòng/đồ neo; dò lại tầng đổi id thì danh sách cũ không khớp, đồ hiện lại (không hỏng
  dữ liệu). Cửa barn/garage và cửa sổ hất/chớp chưa có chỗ trên dây (FE vẫn báo "chưa lưu").
