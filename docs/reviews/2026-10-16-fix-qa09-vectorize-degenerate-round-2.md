# Review merge fix/qa09-vectorize-degenerate → main (lượt 2)

- Ngày: 2026-10-16 · Reviewer: phiên /merge-review · Commit đầu nhánh: 87ebd3c336ff (merge-base = `origin/main` 58bb5294a09a, nhánh không chậm sau `main`)
- Cổng: phạm vi đích — lượt 2, diff vòng sửa (`6d0a80b0..87ebd3c3`) chỉ là `changes/QA-09.md`, một docstring và bỏ một assert thừa,
  không chạm R-33b đk 2–7. Reviewer tự chạy dưới stack-lock (f14 **không** dừng, các bước này không cần):
  `bash tools/verify/run.sh verify --steps 1,2,3,4` **mã thoát 0** (log: `.cache/src-out/verify/20261016T101446Z-87ebd3c336ff.log`;
  bản ghi ngoài `F:/worktrees/AppBack/qa09-vectorize-r2.log`) — ruff format, ruff check, mypy --strict, lint-imports đều `đạt`;
  `pytest packages/vision/walls/tests/test_vectorize.py` qua `run.sh shell`: 43 passed, mã thoát 0.
- Độ phủ: không đo (phạm vi đích) — file đổi: `packages/vision/walls/vectorize.py` dòng 99,2% (367 câu, thiếu 3) / nhánh 97,2% (108 nhánh, 3 dở),
  đo bằng `pytest --cov=packages/vision/walls --cov-branch packages/vision/walls/tests/` (181 passed; bản ghi `F:/worktrees/AppBack/qa09-vectorize-r2cov.log`).
  Lượt 1 đầy đủ ở `9f01255c` thoát 0 (8506 test, tổng 99,47/98,00); mã logic không đổi từ đó.

## Phạm vi lượt 2

1 commit `87ebd3c3 docs(vision): changes note for QA-09 and _finalise docstring order`, 3 file, +10/−2:
`changes/QA-09.md` (mới), `packages/vision/walls/vectorize.py:566` (docstring), `packages/vision/walls/tests/test_vectorize.py` (−1 assert).
Cây sạch; không file cấm, không `pragma`/`noqa`/`type: ignore`/`skip`/`xfail` mới.

## Soát finding lượt 1

| # lượt 1 | Trạng thái | Bằng chứng |
|---|---|---|
| 1 Dừng sớm BE-00 §13.2 | đã sửa | `changes/QA-09.md` nêu trước/sửa/test/không đổi dây, khớp diff và BUG-LOG-P09 |
| 2 Dừng sớm R-36b | đã sửa ở `87ebd3c3`; điều kiện gộp | `git log -1 --format='%(trailers:key=Prompt,valueonly)' 87ebd3c3` in `QA-09`. `9f01255c` vẫn thiếu, nhưng gộp squash thay thông điệp |
| 3 Nit R-01 docstring | đã sửa | `vectorize.py:566` "Kẹp biên, làm tròn, bỏ đoạn suy biến SAU làm tròn …" |
| 4 Nit TEST assert thừa | đã sửa | `test_vectorize.py:320` chỉ còn `walls == ()` và `short == 1` |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | R-36b | Thân commit squash phải mang khối trailer liền nhau `Prompt: QA-09` + `Bug: BUG-P09-008` + `Co-Authored-By` (commit `9f01255c` và `6d0a80b0` trong nhánh không thay được) | lúc gộp | Sau squash kiểm `git log -1 --format='%(trailers:key=Prompt,valueonly)'` in `QA-09` |

Không có P0/P1/P2/P3.

## Kiểm sổ nợ

Không nợ mới; không dòng `DEBT.md` cần thêm.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 5 | 0,15 |

Tổng: 5,00 / 5

## PHÁN QUYẾT: APPROVE

Hai điều kiện dừng sớm của lượt 1 đã gỡ, hai Nit đã sửa; bản sửa gốc ở `_finalise` không đổi từ lượt 1 (cổng đầy đủ thoát 0).
Lượt đích ở `87ebd3c3`: bước 1–4 đạt, `test_vectorize.py` 43 passed, `vectorize.py` 99,2/97,2 ≥ 90/90.
Điều kiện gộp: **squash**, thông điệp squash có khối trailer `Prompt: QA-09` đọc được (Nit #1). Nếu `main` đổi trước lúc gộp,
chạy lại cổng trên cây tích hợp.
