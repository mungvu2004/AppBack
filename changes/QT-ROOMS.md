# QT-ROOMS — tên phòng tiếng Anh, công năng từ đồ, đổi loại theo cỡ, gán phòng theo diện tích giao

- B6 (packages/vision/dimensions/rooms.py): khoá tiếng Anh ≥ 5 chữ khớp nguyên từ (kitchen, bedroom, store…), xét sau khớp nguyên khoá Việt, trước khớp gần đúng; dòng tiêu đề (plan, apartment, m2, m², > 4 từ) không là tên phòng; thêm "loggu" cho lô gia.
- Tủ áo → phòng ngủ chỉ khi tủ dài ≥ 900 mm và phòng không có máy giặt / thiết bị vệ sinh.
- B10 `relabel_by_size`: sofa góc (cạnh ngắn tới 1600), băng ghế (dài ≥ 1000, ngắn < 600, cách bàn ≤ 900 mm → `variant="bench"`), chỉ đổi loại khi tỉ lệ đã tin, bỏ luật giường → thảm (giường giữ là giường).
- B8 `build_furniture`: phòng của đồ = phòng giao hộp nhiều nhất; giao < 30 % và tâm ngoài hợp phòng nới 300 mm → `suggested=True` (đồ ngoài căn), không xoá.
- Vì sao: chẩn đoán quy trình lần 2–3 (GIAI-PHAP §3.3, 3.10, 3.11; x1 E3): bản vẽ tiếng Anh ra "phòng khác", tiêu đề thành phòng, sofa góc/băng ghế sai loại, đồ sơ đồ vị trí rơi vào căn.
- Test hiện có đổi có chủ ý: tỉ lệ chưa tin không còn đổi loại (trước: đổi + hạ confidence); YOLO `bed` ở phòng khách giữ giường (trước: thảm).
- Không đổi API, DB, migration, hợp đồng FE–BE (`bench`, `suggested` đã có trong mô hình).
