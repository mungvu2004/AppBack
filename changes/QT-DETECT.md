# QT-DETECT — bộ dò, gợi ý mực dư, ô mở (chẩn đoán quy trình lần 2: A1 nhanh, A7, A10, B7, B11)

- Bộ dò: lớp tắt (`stair`, `None` của model miền) che trước argmax → anchor sofa mà stair nhỉnh điểm ra lớp kế tiếp thay vì mất hộp; `None` của COCO giữ cách cũ.
- Bộ dò: sau NMS theo nhãn thêm khử trùng khác nhãn (IoU ≥ 0,6, hoặc lồng ≥ 85 % mà diện tích chênh < 1,5 lần → giữ điểm cao hơn); cặp được chồng: bàn-ghế, chậu-buồng tắm, bàn-giường, chậu-tủ bếp, mọi cặp có ô mở. Chỉ bật khi truyền `labels` (bước pipeline); đánh giá mAP không đổi.
- `UPSCALE_MAX` 2,6 → 4,0 (trần `MASK_MAX_PIXELS` vẫn chặn): bản vẽ có cửa < 27 px nay phóng đủ tới cỡ lúc train.
- Gợi ý mực dư: tắt khi tỉ lệ chưa đáng tin (trước ước từ p75 bề dày tường, sai ±30 % nên lọc cỡ theo mét sai); `MAX_SUGGESTIONS` 15 → 5. Bỏ mảnh dạng dòng chữ: khung mực sát có tỉ số cạnh < 0,35 và cạnh ngắn < 250 mm (khung nới 5 px làm dòng chữ 0,2 m lọt `MIN_SHORT_M`).
- Ô mở: cửa đôi hẹp < 600 mm giữ thành cửa đơn thay vì bỏ; tầm gắn tường = max(dày/2 + 150, 0,25 x cạnh dài hộp).
- Ô mở: cửa đôi hẹp trên tường qua khe nay giữ tường đó (mang cửa đơn) thay vì bỏ.
- Đo: chỉ test đơn vị (mảng numpy giả); chưa chấm lại bench/345 bản giữ lại.
