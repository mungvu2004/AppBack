# CI-GATE — cổng đầy đủ chạy trên GitHub Actions thay máy dev

- `ci.yml`: thêm job `changes` (PR chỉ đổi tài liệu → tám job cổng "skipped"; `changes` hỏng → vẫn chạy đủ, fail-closed);
  ghim `ubuntu-24.04`; checkout AppFront ở `mungvu999-ctrl/AppFront` (repo đã chuyển 02/11/2026).
- `notify.yml`: lọc ở mức job, lượt ngoài `main` không chiếm runner. `dependabot.yml`: `open-pull-requests-limit: 2`.
- Không đổi mã sản phẩm, API, DB, migration, hợp đồng FE–BE. Đề xuất: F:/App/docs/ci-gate/DE-XUAT.md.
- Cổng áp dụng: lint/type, test `tools/ci/tests`. Migration/hợp đồng: không áp dụng.
