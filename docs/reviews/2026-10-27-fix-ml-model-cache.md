# Review merge fix/ml-model-cache → main

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review · Commit đầu nhánh: 46809ad7890a
- Cổng: phạm vi đích — diff chỉ chạm `deploy/docker/ml.Dockerfile` + `changes/FIX-2457.md`, không mã Python nên `verify` không phủ; kiểm chính là `docker build -f deploy/docker/ml.Dockerfile .` (cpu) mã thoát 0 (log: F:/runs/f14-build/review-ml1.log)
- Độ phủ: không đo (phạm vi đích) — không có file Python đổi
- Bằng chứng: `/opt/models` của ảnh dựng lại và của `appback-ml:f14-cuda` (main) giống hệt: 7 mục, 160 MB, cùng sha256 trên toàn bộ tệp.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | MNT | `for name in $(...)` không có dấu nháy; tên ghim hiện không có khoảng trắng nên đúng | ml.Dockerfile:93 | không cần |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| Tổng hợp (thay đổi build nhỏ, không đổi hành vi, kiểm SHA vẫn chạy mỗi build, có changes/) | — | 4,5 | — |
Tổng: 4,5 / 5

## PHÁN QUYẾT: APPROVE
Sửa đúng gốc (bước tải đứng sau COPY mã, không cache). Lỗi tải vẫn làm build hỏng, bản ghim cũ trong cache không lọt vào ảnh. Không P0/P1/P2.
