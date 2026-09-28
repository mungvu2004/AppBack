# Review merge feature/b3-05-rule-config → main

- Ngày: 2026-09-28 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `7c7379785458`
- Nhánh: `feature/b3-05-rule-config` (3 commit: `affc836` feat · `bec1cd6` docs(contract) · `7c73797` test)
- Cổng: phạm vi **đầy đủ** — lượt đầu của nhánh đi review (R-33b điều kiện 1; diff còn thêm file `.py`,
  chạm `packages/db/**` và `docs/contracts/**`, thêm route mới → thêm điều kiện 2, 3, 5).
  `bash tools/verify/run.sh verify` mã thoát **0** (log: `verify-b3-05-review.log`, chạy trong worktree review).
- Độ phủ: tổng dòng 99,55% · nhánh 98,51% | `apps/api/rules` dòng 100,00% · nhánh 100,00% ·
  `packages/db` 96,71% / 95,76% · tập file bị chạm 100,00% / 100,00%. Test: **5410 qua, 0 hỏng**, 7 deselected (`perf`).

## E.10 — bảng cổng (mã thoát thật của lượt review này)

| Bước | Việc | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (15 revision; 10/10 kiểm con đạt, gồm "đúng 1 head", "model khớp DB", "tên CHECK khớp model") |
| 7 | H1 H3 H4 H5 | đạt |
| 8 | `openapi` | đạt |

Bảng con bước 7 (AppFront @ `9cf0b0bfffbd`): Smoke đạt (23 module schema, 83 mục bản đồ) · Bản đồ đủ đạt (83/83) ·
Thao tác đã mount đạt (62/83) · **H1 đạt (1440 mẫu)** · H1 ngữ cảnh đạt (59 mẫu) · **H3 đạt (10 khoá, 3 vai)** ·
**H4 đạt (25 mã, 26 khoá ngưỡng — hết `không áp dụng`)** · H5 đạt (4 khung SSE).

`case_gate` hai `op` của prompt, **thiếu = 0**:

| op | Bắt buộc | Tìm thấy | KQ |
|---|---|---|---|
| `rules_read_config` | C01 C04 C05 C06 C08 C12 C13 C17 C25 | đủ 9 | đạt |
| `rules_replace_config` | C01 C02 C03 C04 C05 C06 C07 C08 C09 C09b C12 C13 C14 C16 C17 C18 C25 | đủ, C16 theo `waive` của `cases.toml` | đạt |

## Đối chiếu độc lập (không lấy từ báo cáo tác giả)

- **Thứ tự 25 mã** — H4 chỉ so **tập** (`tools/contract/h4.py:29,44` dùng `set`), nên thứ tự phải soát tay. Đã đối chiếu
  từng biến `*Rule` với thứ tự khai trong `BUILT_IN_RULES` (`registry.ts:702-711`), `GEOMETRY_RULES`
  (`geometry/index.ts:1146-1154`), `FUNCTION_RULES` (`function/index.ts:1133-1141`), `FITOUT_RULES`
  (`fitout/index.ts:419-423`): `RULE_CODES` (`catalog.py:17-47`) khớp `ALL_RULES` (`defaults.ts:47-52`) **đúng thứ tự**,
  25 mã, không có `GENERAL`.
- **26 khoá ngưỡng** — 18 khoá tường minh + 8 khoá `room.minArea.*`. Từng `rule_code`, `min`, `max` **và từng số dòng
  trong chú thích** của `catalog.py:73-92` đã đối chiếu với `thresholdSpecs.ts:75-92,95-387`: khớp tuyệt đối, không
  lệch một dòng. `GENERAL_THRESHOLD_CODE = 'GENERAL'` (`config.ts:160`) ✓.
- **Preset** (`test_rejections.py:129-147`) — `corridor.minClearWidthMm` (không phải `stairwell.`) là đúng:
  `thresholdByDefault` (`presets.ts:53-63`) lấy spec **đầu tiên** có `defaultValue === 900`, mà cả hai khoá đều mặc
  định 900 (`function/index.ts:117,124`) và `corridor.` đứng trước (`thresholdSpecs.ts:279` < `:293`). Bộ văn phòng và
  nhà xưởng khớp `presets.ts:90-157` từng giá trị.
- **Quyền** — `ruleset.edit` = `{admin: True, engineer: False, viewer: False}` (`packages/domain/permissions/matrix.py:53`);
  N22 dùng đúng nó, **không** `project.settings.edit` (`router.py:33`). K08: người ngoài → 404 `resource:"project"`.
- **openapi** — diff `docs/contracts/openapi.json` có **0 dòng xoá**, thêm đúng 1 đường
  `/api/projects/{project_id}/rule-config` và **9** schema (`ProjectRuleConfigOut`, `RuleCodeKey`, `RuleConfigBodyIn`,
  `RuleConfigOverrideIn`, `RuleConfigOverrideOut`, `RuleConfigWriteIn`, `RuleSeverityName`, `ThresholdKey`,
  `ThresholdValue`) — đúng giới hạn đã giao.
- **K07 / C09b** — `service.py:109-127` đúng khuôn `INSERT … ON CONFLICT DO NOTHING` + `UPDATE … WHERE revision = :base
  RETURNING` trong một giao dịch, không so `revision` bằng Python. C09b (`:142`) đủ ba điều kiện; mọi trường hợp còn
  lại, kể cả `baseVersion > revision`, ra 409 `remoteChanges: []` (`:144`, có test `C09_no_row`). Băm đúng công thức
  [6] (`:102-107`). Nhật ký + `touch_project` chỉ chạy trên nhánh thắng, không có ở C09b.
- **Điều kiện dừng sớm**: cây sạch; `changes/B3-05.md` có; ba dòng đầu commit đúng Conventional Commits + trailer
  `Prompt: B3-05`; không đụng `docs/charter/*`, `uv.lock`, `tools/contract/APPFRONT_SHA`; không có `pragma: no cover`,
  `pragma: no branch`, `type: ignore` không mã, `# noqa` trần, `skip`/`xfail` mới, không hạ ngưỡng. → không REJECT.
  (`docs/contracts/openapi.json` do người điều phối làm mới trong phạm vi bàn giao, đã kiểm nội dung ở trên.)
- **[8] "Test đặt tên theo việc"** — phủ **đủ mọi dòng**: danh mục (3), từ chối (mỗi mã một test + biên + `NaN`
  `Infinity` `-Infinity` `1e999` + hai lỗi cùng lúc), preset ×2, bền K22 qua `db_sessionmaker` mới, dây `0` và
  `WALL-THICKNESS`, C09b khác người, lọc khoá cũ (3 đường: N21, PUT lại, C09b), CASCADE. Postgres thật, C14 hai
  client thật (`test_concurrency.py`, base 0 và 1).
- **R-01** — mọi hàm trong `apps/api/rules/**` và `packages/db/models/rules.py` có docstring.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | DB-01 / R-33b(6) | **Gốc nhánh cũ hơn `main`.** Nhánh cắt từ `e91b283`, khi đó head alembic là `r20260928_b3_04`. Từ đó `main` đã nhận `r20260928_b2_07` và revision merge `r20260928_merge_w08_1` (head hiện tại). Hệ quả lúc gộp: (a) `down_revision = "r20260928_b3_04"` trỏ vào một tổ tiên, không phải head → **hai head alembic** trên `main` (`r20260928_merge_w08_1` và `r20260928_b3_05`), bước 6 "đúng 1 head" sẽ hỏng; (b) `docs/contracts/openapi.json` của nhánh có **53** đường, **thiếu 3** đường `measurements`/`templates` của B2-07 đã ở trên `main` (**55** đường) → gộp thẳng là lùi hợp đồng; (c) cây sau gộp khác cây vừa qua lượt đầy đủ. **Không phải lỗi tác giả** (đúng head lúc cắt nhánh), nhưng bỏ qua thì `main` không xanh. | `packages/db/migrations/versions/r20260928_b3_05_rule_configs.py:22`; `docs/contracts/openapi.json` | Người điều phối, **sau** squash: nối thẳng `down_revision = "r20260928_merge_w08_1"` (không dùng `run.sh merge-heads` — NO-249 ghi lệnh này hỏng và `migrate_check` `downgrade -1` không đi qua revision merge thứ hai); rồi `run.sh openapi` trên `main` → chép ra `docs/contracts/openapi.json` (bản hợp nhất phải có **cả** 3 đường B2-07 lẫn đường `rule-config`) → commit `docs(contract)` → verify tích hợp **đầy đủ**. Không giải xung đột JSON bằng tay, sinh lại. Mẫu: review B2-07 finding #1. |
| 2 | P3 | LOG-01 | Bộ lọc khi trả chỉ bỏ **mã** và **khoá ngưỡng** lạ, không bỏ **trường lạ** của override. `RuleConfigOverrideOut` là `WireModel` → `extra="forbid"` (`apps/api/core/wire.py:46`), nên một dòng `rule_configs` mang trường ngoài `{enabled, severity, thresholds}` (sau một FIX thu hẹp schema, hoặc jsonb vá tay) làm `RuleConfigOverrideOut(**o)` ném `ValidationError` → **500** ở N21 thay vì trả phần còn hợp lệ. Đúng tình huống mà bộ lọc sinh ra để chịu ([6] "Lọc khi trả"). Cùng đường: `thresholds` là `null`/không phải dict → `AttributeError`. Chỉ tới được bằng SQL trực tiếp hoặc bản mã cũ hơn, nên P3. | `apps/api/rules/service.py:45,48`; `apps/api/rules/schemas.py:70` | Lọc cả tên trường theo `RuleConfigOverrideOut.model_fields`, và bỏ `thresholds` khi không phải `dict`. Cần một dòng `DEBT.md` nếu để sau. |
| 3 | Nit | MNT-01 | `replace_config` dài **51 dòng** tính cả chữ ký và docstring (46 dòng mã) — sát trần R-08 / MNT-01 "hàm ≤ 50 dòng". Tuỳ cách đếm mà vượt hay không. | `apps/api/rules/service.py:94-144` | Tách phần dựng băm hoặc phần ghi thành hàm riêng, như `project_settings` đã làm (`_try_write`, `body_digest`). |
| 4 | Nit | MNT-03 | `service.py` dựng lại khuôn ghi-có-version + C09b của `apps/api/project_settings/service.py:47-119`. **Không tính R-07**: [6] của B3-05 quy định SQL khác (INSERT + UPDATE luôn, thay vì rẽ nhánh theo `base == 0`) và công thức băm khác (`model_dump` cả thân, thay vì `body_digest` ép `Decimal`→`str`), nên gọi lại bản của B2-02 sẽ sai hợp đồng. | `apps/api/rules/service.py:94-144` | Ghi nhận: người dùng thứ ba của khuôn này thì đưa lên `packages/db` (cùng họ NO-247). Không cần sửa trong nhánh này. |

Không có finding **P0** hay **P1**.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 4 | 0,60 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 3 | 0,30 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,62 / 5** |

## PHÁN QUYẾT: APPROVE (4,62 / 5)

Nhánh làm đúng hợp đồng N21/N22 và đúng khuôn GV của `project_settings`. Phần rủi ro nhất — danh mục 25 mã + 26 khoá
gương FE — đã được soát tay từng dòng (H4 chỉ so tập, không so thứ tự) và khớp tuyệt đối, kể cả mọi số dòng trong chú
thích dẫn nguồn. Ghi là nguyên tử một giao dịch đúng K07, C09b đủ ba điều kiện, 409 luôn `remoteChanges: []` kể cả khi
`baseVersion > revision`, quyền dùng đúng `ruleset.edit`. Cổng đầy đủ thoát 0 với `apps/api/rules` phủ 100%/100% và
`case_gate` hai `op` không thiếu case. Không P0/P1.

**Điều kiện trước khi gộp** (việc của người điều phối, finding #1 — không chặn `APPROVE`, nhưng `main` sẽ đỏ nếu bỏ qua):

1. Sau squash: nối `down_revision` của `r20260928_b3_05_rule_configs.py` vào head hiện tại của `main`
   (`r20260928_merge_w08_1`). Không dùng `run.sh merge-heads` (NO-249).
2. `run.sh openapi` trên `main` → chép ra `docs/contracts/openapi.json` → commit `docs(contract)`. Bản hợp nhất phải có
   cả 3 đường `measurements`/`templates` của B2-07 lẫn đường `rule-config`.
3. Verify tích hợp **đầy đủ** trên `main` sau hai bước trên (bước 8 chạy chế độ `--compare`).

**Nên ghi `DEBT.md`** (tác giả báo "Nợ: Không", chưa có dòng nào cho B3-05): finding #2 — bộ lọc khi trả không bỏ
trường lạ của override → N21 có thể 500 trên dòng jsonb ngoài schema hiện tại.
