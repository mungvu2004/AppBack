# Review merge fix/qa04-dimensions → main (lượt 2)

- Ngày: 2026-10-14 · Reviewer: phiên /merge-review · Commit đầu nhánh: 0b6270663323
- Cổng: phạm vi đầy đủ — diff vòng sửa chạm R-33b (2) sàn cứng `packages/domain/**` (`spatial/__init__.py` xuất `DELETED`), `docs/charter/*`, `docs/contracts/**`; (3) file test `.py` mới; (5) hình dạng dây #35; (6) lịch sử nhánh viết lại. `bash tools/verify/run.sh verify` mã thoát 0, bước 0–8 đều đạt (log: `F:/worktrees/AppBack/_logs/review2-qa04-dim-verify.log`; pytest 8456 passed)
- Độ phủ: tổng dòng 99,45% · nhánh 97,96% | `apps/api/spatial_write` 99,53% · 98,08% · `packages/domain` 100% · 100% · tập file bị chạm 99,45% · 98,00%

## Phạm vi

4 commit, 11 tệp, +434/−37 (`.py`: +244/−35, dưới trần 400 dòng logic). Cây làm việc sạch. Lịch sử viết lại: cây `HEAD^{tree}` =
`fix/qa04-dimensions-r1-backup^{tree}` (`9037afa7`). Không có pragma, `noqa` trần, `type: ignore`, skip/xfail mới, không hạ ngưỡng.

## Điều kiện dừng sớm (skill §2) — không chạm

| commit | dòng đầu | `Prompt` | khác |
|---|---|---|---|
| `3afe4b09` | feat(spatial-write) | `QA-04` | |
| `1629e213` | docs(contracts) | `QA-04` | `openapi.json` do người điều phối sinh bằng `run.sh openapi` (tiền lệ lượt 1); bước 8 đạt |
| `a338487a` | docs(review) | `QA-04` | |
| `0b627066` | docs(charter) | `QA-04` | chỉ `docs/charter/HOP-DONG-MOI.md` + `docs/decisions.md`; `Charter-Approved: backend/dieu-phoi/chay/QA-04/charter-ban-11.md` |

Bản duyệt `F:/App/AppBack/backend/dieu-phoi/chay/QA-04/charter-ban-11.md` có thật (thư mục `backend/` bị gitignore). Dòng 3 ghi người dùng
duyệt nguyên văn ngày 2026-10-14. Đối chiếu năm chỗ sửa với diff `HOP-DONG-MOI.md`: khớp từng chữ.

## Finding lượt 1 — trạng thái

| # lượt 1 | Trạng thái | Bằng chứng |
|---|---|---|
| 0 P1 mypy + cổng chưa chạy hết | đã sửa | `_dimension(level_id, source: str, reviewed: bool)` gọi `review(source=…, reviewed=…)`; bước 3 đạt, bước 5b–8 đạt |
| 1 P1 CON-01 nhật ký kích thước | đã sửa | `writer.py:605-646` `_diff_dimensions`/`_dimension_marks` đưa vào `_write_log`. Test `test_put_dimensions_logs_rows_per_dimension_id`, `test_put_dimensions_stale_base_conflicts` (409, `remoteChanges` = `("dimension","M-TESTDIM001")`) đỏ trước sửa (`_logs/qa04r2-red.log`: `set() == {…}`, `200 == 409`), xanh ở HEAD (`qa04r2-green.log` và cổng đầy đủ) |
| 2 P1 API-01 hiến chương | đã sửa | HOP-DONG-MOI Bản 11 + QD-001, commit chỉ tài liệu có `Charter-Approved:` |
| 3 P2 LOG-01 trùng `id` | đã sửa | `_check_human_dimensions` (`writer.py:279-291`) → 422 `VALIDATION` `field: body.dimensions.<i>.id`; test đỏ trước sửa (`200 == 422`) và xanh ở HEAD |
| 4 P2 R-36/R-36b trailer | đã sửa | bảng trên |
| 5 P3 R-01 docstring | đã sửa | `test_routes_dimensions.py:60` có docstring |

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | CON-01 | Lượt ghi chỉ đổi **thứ tự** kích thước làm `_unchanged` sai, nên vẫn tăng revision, nhưng `_diff_dimensions` và `_dimension_marks` đều rỗng, nên 0 dòng nhật ký. Người cầm base cũ ghi đè thứ tự đó mà không gặp 409. Lượt ghi vừa đổi trường theo dõi của D1 vừa chỉ đổi `reviewed` của D2 thì không có dấu chạm cho D2 (`dimension_changes or marks`). 409 vẫn nổ, nhưng `remoteChanges` không nêu D2. Cả hai giống hệt lớp (`has_untracked_changes` / `_touch_marks`, `writer.py:587-603`), và Bản 11 ghi "như thực thể của lớp". Tác động thấp. | `apps/api/spatial_write/writer.py:657-659` | Không chặn. Nếu cần thì sửa chung cho lớp lẫn kích thước: dấu chạm theo từng thực thể, không theo cả lượt. |
| 2 | Nit | MNT | Bản 11 dẫn `writer.py:472-478` cho phép quy đổi tỉ lệ của thân, nhưng hàm `_sent_dimensions` nằm ở `:477-483`. Câu chữ đã được duyệt nguyên văn nên không sửa trong nhánh này. | `docs/charter/HOP-DONG-MOI.md` §4 #35 | Bản hiến chương sau dẫn tên hàm thay vì số dòng. |

Đã kiểm, không thành finding:
- SEC: `dimensions` đi qua `WireRequest` strict + `Dimension` miền. Người gửi được kiểm trùng id, A5, `levelId`, và các lỗi đều có `field`. Luật pipeline (`_check_arguments`) chỉ áp cho `SYSTEM_PIPELINE`.
- CON: mọi lượt ghi có kích thước khác (ngoài thứ tự) đều sinh ≥ 1 dòng. `remote_changes_since` không đổi.
- LOG: gỡ `override_value_mm` → dòng `MISSING` (`removed=true`), đúng CHECK `removed_matches_value`. Mục mới không ghi override vắng. `_drop_missing_refs` bỏ `touched`; việc gỡ ref nay đi qua diff `reference_ids`.
- PERF: đường pipeline/N19 và tính lại tỉ lệ nay ghi một dòng cho mỗi trường kích thước đổi. Nhật ký vẫn đi qua `_log_insert` chia khúc, không truy vấn mới.
- API: FE `spatialLayer.ts` khớp như lượt 1. Bước 7 H1–H5 và bước 8 openapi đạt.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4 | 0,60 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |

Tổng: 4,82 / 5

## PHÁN QUYẾT: APPROVE

Cả sáu finding của lượt 1 đã được sửa, có bằng chứng chạy: test đỏ trước sửa, xanh ở HEAD, và cổng đầy đủ thoát 0. Không còn P0/P1/P2. Còn một P3 và một Nit, đều không chặn merge và không bắt buộc ghi `DEBT.md`.
Merge: squash một prompt (`QA-04`), giữ khối trailer `Prompt: QA-04` / `Bug: BUG-577` / `Charter-Approved: …` trong commit gộp. Cây sau gộp phải trùng cây `0b627066` (cộng file phán quyết này). Nếu không trùng thì chạy verify tích hợp đầy đủ trên `main` (R-33b).
