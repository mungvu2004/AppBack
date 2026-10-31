
## bd — nối đầu tường lơ lửng (bước 10e)

- `packages/vision/walls/vectorize.py`: bước 10e `_bridge_dangling_ends` sau 10c/10d, trước `_rotate`. Đầu tường
  ngang/dọc không chạm tường nào, nhìn thẳng ra trước gặp tường khác hở mặt-tới-mặt ≤ 1,5 × bề dày lớn → kéo tới
  tim (tường vuông góc) hoặc đầu mút gần (tường thẳng hàng, bề dày lệch ≤ 1,25 lần); tường gặp đầu tiên thắng nên
  không kéo xuyên tường; góc L hở thì kéo nốt tường kia. Chưa có thông tin cửa ở bước này nên khe dài hơn để lại.
- Đo 14 ca (`F:/runs/r4-bd/KET-QUA.txt`): ch-09 đầu lơ lửng 13 → 10; ca khác không đổi; số cửa, phòng, xiên,
  không chuẩn không ca nào xấu đi. ch-04 chưa đỡ: khe 470–1090 mm theo phương tường cần biết cửa (bước sau).
- Test: `packages/vision/walls/tests/test_bridge_ends.py`.
