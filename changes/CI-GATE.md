# CI-GATE — cổng đầy đủ chạy trên GitHub Actions thay máy dev

- `ci.yml`: thêm job `changes` (PR chỉ đổi tài liệu → tám job cổng "skipped"; `changes` hỏng → vẫn chạy đủ, fail-closed);
  ghim `ubuntu-24.04`; checkout AppFront ở `mungvu999-ctrl/AppFront` (repo đã chuyển 02/11/2026).
- `notify.yml`: lọc ở mức job, lượt ngoài `main` không chiếm runner. `dependabot.yml`: `open-pull-requests-limit: 2`.
- MinIO đã lưu trữ bản cộng đồng (quay.io 401, dl.min.io 410): ảnh `minio` và `mc` chuyển sang
  `ghcr.io/mungvu999-ctrl/` (`pinned_images.py`, compose ci/dev/prod); `mc` dựng từ mã nguồn (`mc.Dockerfile`,
  workflow `minio-images.yml`), `minio` là bản sao nguyên ảnh cũ.
- Không đổi mã sản phẩm, API, DB, migration, hợp đồng FE–BE. Đề xuất: F:/App/docs/ci-gate/DE-XUAT.md.
- Cổng áp dụng: lint/type, test `tools/ci/tests`. Migration/hợp đồng: không áp dụng.
