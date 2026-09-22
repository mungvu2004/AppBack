# Review merge feature/b1-02-permissions-activity-log → main

- Ngày: 2026-09-22 · Reviewer: phiên /merge-review · Commit đầu nhánh: 88e36b3d5f16
- Cổng: `bash tools/verify/run.sh verify` mã thoát 0, chạy trên đúng 88e36b3d5f16. Log ngoài repo: `%TEMP%/verify-b1-02-m.docker.log` (bước 1–8 và 5b đạt; 2206 qua / 0 hỏng / 10 bỏ qua; bước 7: H1 đạt, H3 đạt 10 khoá × 3 vai, H4/H5 không áp dụng vì B3-05/B4-01 chưa hợp nhất — đúng BE-00 §12).
- Độ phủ: tổng dòng 99,36% · nhánh 97,52%; `apps/api/access` 100 · 100; `packages/domain` 100 · 100; `packages/testing` 99,16 · 100; `packages/db` 98,84 · 97,22. Đo riêng: `packages/domain/permissions`, `apps/api/access`, `packages/testing/fixtures/access.py` đều 100% dòng · 100% nhánh.
- Tính độc lập: lượt verify và commit merge `88e36b3` (merge thuần, 0 dòng sửa tay) đều do chính phiên gộp này làm; mã do các phiên W1, D, E viết. Người điều phối cân nhắc việc này khi áp R-37.

## Điều kiện dừng sớm
- Cây sạch; 5 commit `main..HEAD`, dòng đầu đúng Conventional Commits, cả 5 có trailer `Prompt: B1-02` (kiểm bằng `%(trailers:key=Prompt)`).
- Có `changes/B1-02.md`.
- Không file cấm: 19 file đều mới (`A`), đều thuộc khối [10]; không đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`.
- Không `pragma`, không `noqa` trần, không `skip`/`xfail` mới. Cả 4 `type: ignore` đều có mã (`arg-type`, `index`). Không hạ ngưỡng.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | ~~P2~~ rút lại | R-34 | Finding sai: reviewer đọc `DEBT.md` của nhánh (base cũ), trong khi `main` đã có NO-097..NO-100 (commit `69d59a1`) phủ đủ các nợ. Nợ "chưa route nào gọi `record_activity`" là việc của các prompt chủ route, không phải nợ. | `DEBT.md` (main) | Không cần làm gì. |
| 2 | P3 | MNT-03 / R-07 | `Role = Literal["admin","engineer","viewer"]` khai lại, trùng `apps/api/core/auth.py:19`. `ROLES` cũng có hai bản (tuple ở domain, frozenset ở core). Lệch nhau thì H3 vẫn xanh nhưng `Principal.role` và `can()` hiểu hai tập vai khác nhau. | `packages/domain/permissions/matrix.py:15,29` | FIX cho chủ `apps/api/core`: `auth.py` nhập `Role`/`ROLES` từ `packages.domain.permissions` (domain chỉ phụ thuộc `packages.core`, nên chiều nhập này hợp lệ). |
| 3 | P3 | LOG-02 / SEC-05 | `project_id` nhận chuỗi bất kỳ. `actor_id` được kiểm `is_id`, còn `project_id` thì không, nên id rác chỉ lộ ra khi đọc nhật ký. | `apps/api/access/activity.py:50` | Khi B2-01 chốt tiền tố thì thêm `is_id("prj", project_id)` và một test âm. |
| 4 | Nit | MNT-04 | Comment ghi "để thử CHECK", nhưng test thực ra kiểm `_check_kind` (ném `ValueError` trước `db.add`), không chạm tới CHECK của DB. | `apps/api/access/tests/test_activity.py:136` | Sửa comment thành "để thử `_check_kind`". |
| 5 | Nit | TEST-01 | `object_code` chỉ có test cho quá trần; chưa có test rỗng / chỉ khoảng trắng. Nhánh đó vẫn được phủ qua `object_label`, vì cả hai đi chung helper `_normalized`. | `apps/api/access/tests/test_activity.py` | Thêm `""`/`"   "` vào một parametrize cho `object_code`. |
| 6 | Nit | PERF-02 | `activity_rows` đọc không `LIMIT`. Đây là fixture chỉ dùng trong test, trên DB test nhỏ. | `packages/testing/fixtures/access.py:50` | Giữ nguyên; ghi chú nếu có ai dùng nó cho bảng lớn. |

Đã soát, không có finding: SEC (vai chỉ lấy từ `CurrentPrincipal`; có test `test_role_in_request_body_is_ignored`; nhật ký không ghi token hay thân request — K05/K11/K34); CON (`record_activity` không commit, có test rollback; purge xoá theo lô bằng `DELETE … WHERE id IN (SELECT … LIMIT)`, chạy lặp vô hại — J06); LOG-03 (`Clock` được tiêm, không `datetime.now()`); PERF (purge dùng `ix_activity_log_at`; `@cache` của `_role_gate` có không gian khoá hữu hạn); DB (expand thuần, có downgrade, migrate_check up/down/up đạt, CHECK khớp model, không FK `actor_id` có lý do); ranh giới (`activity`/`jobs`/`kinds` không nhập `fastapi`, có test tiến trình con kiểm; `__init__` không nhập module con); TEST (Postgres/Redis thật, `FakeClock`, J01/J06 đúng tên, test âm cho `actor_id`/`kind`/độ dài/NFD/khoá không phải cấp hệ thống).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |

Tổng: 4,82 / 5

## PHÁN QUYẾT: APPROVE
Không có P0/P1. Cổng đạt đủ 8 bước với mã thoát 0 trên đúng commit đầu nhánh. H3 đạt với 0 ô lệch. Mọi phần của B1-02 phủ 100% dòng và 100% nhánh. Finding #1 đã rút lại vì `main` đã có NO-097..NO-100. Hai P3 (#2, #3) chính là NO-097 và NO-100. **NO-100 đang 🔧**: nhánh `feature/b1-02-project-id-check` phải gộp vào nhánh này trước khi merge, và phần gộp thêm đó cần một lượt review lại. Ba Nit không chặn merge. Merge bằng squash (nhánh chỉ một prompt), giữ trailer `Prompt: B1-02`.
