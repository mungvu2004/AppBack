# UX-R4 — đợt sửa UX vòng 4 (AppBack/AI)

## bb — U34: sửa nhãn đồ theo kích thước thật

- `apps/worker/pipeline_build/rooms.py`: `relabel_by_size` chạy trong `build_furniture`, đo hộp ở tỉ lệ `final` (mm):
  `chair`/`other` cỡ giường (ngắn 900-2000, dài 1900-2200) → `kind="bed"`, trừ khi tâm nằm trong phòng khách, bếp,
  WC, hành lang, lô gia (bộ sofa + bàn trà cũng cỡ giường); `chair` dài ≥ 1400, ngắn 600-1100 → `kind="chair"` +
  `variant="sofa"`. Hợp đồng `Furniture.kind` không có sofa nên dùng `variant` có sẵn (thư viện xếp sofa vào nhóm ghế).
- Tỉ lệ chưa tin (`project_default` hay ước từ bề dày tường): vẫn đổi, `confidence` hạ về `LOW_CONFIDENCE_CAP`.
- Bàn, tủ bếp và các nhãn khác không đụng. Đo 14 ca bench: 12 món ghế → sofa, 0 giường; bảng `F:/runs/r4-bb/KET-QUA.txt`.
- Lệch: FE vẫn ghi chữ theo `kind` ("Ghế") cho sofa; đổi chữ cần FE đọc `variant`.
