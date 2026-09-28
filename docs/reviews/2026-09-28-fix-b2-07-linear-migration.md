# Review merge fix/b2-07-linear-migration → main

- Ngày: 2026-09-28 · Reviewer: phiên /merge-review (độc lập, worktree riêng `b2-07-review2` @ `f10dae5`) · Commit đầu nhánh: `f10dae5fbd7a`
- Cổng: phạm vi **đầy đủ** — R-33b (1) lượt đầu của nhánh đi review **và** (2) diff chạm `packages/**` (migration).
  `bash tools/verify/run.sh verify` mã thoát **0** (log: `backend/dieu-phoi/chay/B2-07/R2/verify-full.log`, dòng `EXIT=0`).
- Độ phủ: tổng dòng **99,55%** · nhánh **98,48%** | `packages/db` dòng **96,80%** · nhánh **95,76%** | tập file bị chạm dòng **100,00%** · nhánh **100,00%** — đều ≥ 90/90.
- Test: **5.490 passed**, 7 deselected (`perf`), 0 failed, 25:14.

## 1. Phạm vi

`git diff main...HEAD` — đúng 2 file, +2 −29 dòng:

| File | Thay đổi |
|---|---|
| `packages/db/migrations/versions/r20260928_b2_07_measure_tpl.py` | `down_revision`/`Revises:` `r20260928_b2_06` → `r20260928_b3_04` (2 dòng) |
| `packages/db/migrations/versions/r20260928_merge_w08_1_merge_heads.py` | xoá (27 dòng) |

`main` (`f5dc65b`) hơn gốc nhánh (`75e8d17`) chỉ ở `DEBT.md` → gộp không xung đột, và **cây sau gộp khác cây đã qua
lượt đầy đủ đúng một file `DEBT.md`** ⇒ R-33b cho phép bỏ verify tích hợp sau gộp.

Điều kiện dừng sớm (§2 của skill): cây sạch (`git status --porcelain` rỗng); `changes/B2-07.md` có sẵn; dòng đầu
`fix(db): chain the b2-07 revision after b3-04` (45 ký tự) đúng Conventional Commits;
`git log -1 --format='%(trailers:key=Prompt,valueonly)'` in `B2-07` ⇒ khối trailer đúng R-36b; không đụng file cấm
(`docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock` đều không nằm trong diff); không `pragma: no cover`,
không `type: ignore`, không `noqa` trần, không `skip`/`xfail` mới, không hạ ngưỡng cổng.

## 2. Soát trọng tâm

**Chuỗi revision thẳng, đúng một head** — dựng lại bản đồ cha–con từ 15 file `versions/*.py`: 15 revision / 14
`down_revision`; tập `revision \ down_revision` = `{r20260928_b2_07}` (đúng **1 head**); `down_revision \ revision` = ∅
(không parent treo); `uniq -d` trên tập parent = ∅ (**không điểm rẽ nhánh**, chuỗi tuyến tính hoàn toàn).
Đuôi chuỗi: `… → r20260928_b2_06 → r20260928_b3_04 → r20260928_b2_07 (head)`.

**Bước 6 đạt, đúng chỗ đã hỏng ở `75e8d17`** — `lint_migrations: đạt (15 revision)`; `migrate_check` 10/10 bước con:

```
đúng 1 head  đạt   |  downgrade -1  đạt   |  downgrade base  đạt   |  model khớp DB     đạt
upgrade head đạt   |  upgrade head trên DB có dữ liệu đạt |  chỉ còn alembic_version đạt
seed ci hai lần đạt|  upgrade head lại đạt                |  tên CHECK khớp model    đạt
```

Hai bước `đúng 1 head` và `downgrade -1` chính là hai bước sinh `CommandError('Ambiguous walk')` ở verify tích hợp
@`75e8d17`; `packages/db/tests/test_migrate_check.py::test_main_on_repo_migrations` và
`::test_main_starts_postgres_when_url_missing` chạy đúng vòng kiểm ấy trên migration thật của repo, nên bộ test hiện
có **chính là test hồi quy** cho sửa này — không cần thêm test mới (R-13…R-15 đã thoả).

**Không còn tham chiếu `merge_w08_1`** — `grep -rn "merge_w08"` ngoài `.git`: chỉ còn dòng lịch sử NO-249 trong
`DEBT.md`. Các hit `tools/tests/test_lint_migrations*.py`, `test_steps.py` là `r20260918_merge_w08_*` (ngày khác,
chuỗi tổng hợp kiểm regex `MERGE_REVISION_RE`), không trỏ tới revision đã xoá. `tools/verify/steps.py:456`
(`cmd_merge_heads`) chỉ dùng regex, không phụ thuộc file.

**Đổi thứ tự không đổi ngữ nghĩa** — `r20260928_b2_07` tạo `measurements`, `property_templates`, FK **chỉ** sang
`projects` (`r20260923_b2_01`); `r20260928_b3_04` tạo `versions`, FK sang `floors` (`r20260923_b2_03`) và `projects`.
Không bảng nào của cặp này trỏ sang bảng của cặp kia ⇒ không FK chéo, tổ tiên của cả hai đều đứng trước trong chuỗi ở
**cả hai** thứ tự. `downgrade()` của b2_07 bỏ đúng hai bảng nó tạo; bước `chỉ còn alembic_version` xác nhận.
Vẫn expand thuần (`lint_migrations` đạt).

**Đổi `down_revision` của revision đã vào `main` là đúng hiến chương, không phải ngoại lệ** — BE-00 §6.1 ghi thẳng:
*"Worker **không** tạo revision merge: rebase lên nhánh tích hợp mà có 2 head thì đổi `down_revision` của revision
**của chính mình** về head của nhánh tích hợp, rồi chạy lại verify."* `r20260928_b2_07` là revision của một prompt
worker, nên nối thẳng là thao tác chuẩn; revision merge viết tay ở `75e8d17` mới là chỗ lệch. §6.1 *"mỗi prompt tối đa
một revision"* cũng chỉ còn đúng sau khi xoá file merge. Không có rủi ro "revision đã phát hành": `75e8d17` nằm trên
`main` vài giờ, chưa triển khai ở đâu, và `migrate_check` dựng Postgres mới mỗi lượt.

## 3. Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P3** | DB-01 / R-34 | NO-249 **ghi** được sự thật "revision merge không qua `downgrade -1`" nhưng **đề xuất sửa** vẫn chỉ là `script.py.mako` in `down_revision` bằng `repr(...)`. Sửa đúng như viết thì `run.sh merge-heads` chạy được, sinh ra revision merge, rồi bước 6 vẫn đỏ `Ambiguous walk` — nợ đóng mà lỗi còn. BE-00 §6.1 hiện vẫn kê `merge-heads` là đường chính thức của người điều phối. | `DEBT.md:270`; mâu thuẫn với `packages/db/migrate_check.py:177` (`("downgrade -1", … , "-1")`) và file bị xoá `r20260928_merge_w08_1_merge_heads.py` | Mở rộng đề xuất NO-249 thành một trong hai, rồi mới đóng: (a) `migrate_check` giải `downgrade -1` thành **revision cụ thể** qua `ScriptDirectory.get_revision("head").down_revision` khi head có nhiều cha; hoặc (b) bỏ hẳn `cmd_merge_heads` + `MERGE_REVISION_RE` và sửa câu tương ứng ở BE-00 §6.1 (file của người điều phối). |
| 2 | Nit | MNT | Trailer `Co-Authored-By: Claude <noreply@anthropic.com>`; 8 commit gần nhất trên `main` đều dùng `Claude Opus 5` / `Claude Opus 5.5`. Không luật nào chặn (`Prompt:` vẫn parse được), chỉ lệch quy ước. | `f10dae5` thân commit | Sửa giá trị trailer lúc squash vào `main`. |

Không có finding **P0**, **P1**, **P2**.

## 4. Sổ nợ

- NO-249 đã được mở rộng trên `main` (`f5dc65b`) với đúng nguyên nhân gốc và luật tạm thời *"hai head → nối thẳng
  revision của prompt vào sau, không dùng `merge-heads`"* ⇒ R-34 thoả cho vòng sửa này; nhánh không sửa `DEBT.md` là đúng.
- Nợ mở còn lại của B2-07 (NO-246, NO-247, NO-248) đều **P3** ⇒ không chặn merge (R-38).
- Finding #1 ở trên là nợ **nên bổ sung vào dòng NO-249 có sẵn** (đổi cột đề xuất), không mở `NO-` mới.

## 5. Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 4 | 0,40 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 5 | 0,15 |
| **Tổng** | **100%** | | **4,90 / 5** |

DB/API xuống 4 vì finding P3 #1 (nợ đóng hụt), không phải vì bản thân migration. Nit #2 không trừ điểm.

## PHÁN QUYẾT: APPROVE

Diff là sửa **gốc**, không vá triệu chứng (R-19): thay vì nới `migrate_check`, nó bỏ thứ mà hiến chương vốn không cho
worker tạo ra, đưa cây revision về đúng dạng tuyến tính mà BE-00 §6.1 quy định. Phạm vi nhỏ nhất có thể — 2 file, +2
−29 — và toàn bộ phần xoá là revision không thao tác, nên không có mã nghiệp vụ nào đổi. Cổng đầy đủ mã thoát 0 với
5.490 test qua, độ phủ mọi mức ≥ 90/90, và bước 6 chạy trọn 10 bước con trên chính hai bước từng hỏng. Được merge vào
`main` (squash, một prompt — R-36); khuyến nghị sửa trailer `Co-Authored-By` lúc squash và mở rộng cột đề xuất của
NO-249 theo finding #1 trước khi đóng nợ ấy.
