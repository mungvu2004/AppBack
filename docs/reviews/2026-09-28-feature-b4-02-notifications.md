# Review merge feature/b4-02-notifications → main

- Ngày: 2026-09-28 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `4bfc60247f18`
- Phạm vi diff: `git diff f46ad16...4bfc602` — 30 file, +2742 / −5. Worktree riêng tại `4bfc602`, `git status --porcelain` rỗng.
- Cổng: phạm vi **đầy đủ** — lượt đầu của nhánh đi review (R-33b điều kiện 1; diff cũng chạm `packages/db/**`,
  `docs/contracts/**` và thêm file `.py` mới → điều kiện 2 và 3).
  `bash tools/verify/run.sh verify` **mã thoát 0** (log: `backend/dieu-phoi/chay/B4-02/review/verify-r1.log`).
- Độ phủ (lượt đầy đủ, tự chạy): tổng dòng **99,56 %** · nhánh **98,48 %**;
  `apps/api/notifications` dòng **100,00 %** · nhánh **97,83 %**; tập file bị chạm dòng 100,00 % · nhánh 97,83 %.
  Mọi gói bị chạm ≥ 90/90: `project_members` 100/100, `streams` 100/100, `packages/db` 96,94/95,76,
  `packages/testing` 99,50/98,61.

## Bảng cổng (trạng thái lấy từ mã thoát thật của lượt này, không chép báo cáo tác giả)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | 9 contract kept, 0 broken (794 file, 6030 phụ thuộc) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | **5702 passed**, 0 failed, 7 deselected, 27 ph 09 |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; 68 thao tác đã mount, thiếu 0 |
| 6 | `lint_migrations` → `migrate_check` | đạt | 17 revision; **đúng 1 head**; 10/10 kiểm gồm "model khớp DB", "tên CHECK khớp model" |
| 7 | `tools.contract.check` | đạt | H1 1614 mẫu · H1 ngữ cảnh 59 · H3 10 khoá/3 vai · H4 25 mã/26 khoá · **H5 6 khung SSE** |
| 8 | `apps.api.core.openapi` | đạt | 210 925 byte |

`case_gate` cho bốn `op` của prompt — **thiếu = 0**, không miễn:

| `op` | Bắt buộc | Tìm thấy | |
|---|---|---|---|
| `notifications_list` | C01 C04 C05 C12 C13 C15 C17 C25 | y hệt | đạt |
| `notifications_mark_read` | C01 C02 C03 C04 C05 C10 C12 C13 C22 C25 | y hệt | đạt |
| `notifications_mark_all_read` | C01 C02 C03 C04 C05 C10 C12 C13 C22 C25 | y hệt | đạt |
| `notifications_accept_invite` | C01 C02 C03 C04 C05 C08 C10 C12 C13 C17 C22 C23 C25 | y hệt | đạt |
| `streams_open_notifications` (S2 của B4-01) | S01 S02 S03 S04 S05 S07 S09 | y hệt | đạt |

`XLEN events:user:{u}`: log không in được vì pytest nuốt stdout của test qua. Thay vào đó các giá trị được **khẳng
định trong test** (mạnh hơn bản in): `test_notify__J09` = 0 sau rollback; `test_notify__one_xadd_across_sweep_k32`
= 1 sau `notify`+commit và **vẫn** 1 sau quét bù; `test_sink__invite_through_n3_reaches_list_and_stream` = 1 sau N3
lặp hai lần.

## Điều kiện dừng sớm (§2) — không cái nào chạm

- Cây sạch; 6 commit, dòng đầu đều đúng Conventional Commits ≤ 72 ký tự, đều có trailer `Prompt: <chủ>`
  (hai cặp FIX thêm `Fix: FIX-109` / `Fix: FIX-110`).
- `changes/B4-02.md` có (7 dòng).
- File cấm: `docs/charter/*`, `tools/contract/APPFRONT_SHA`, `uv.lock` **không** bị chạm.
  `docs/contracts/openapi.json` do người điều phối làm mới ở commit `docs(contract)` riêng, và diff của nó là
  **0 dòng xoá** — chỉ thêm đúng 4 đường `/api/notifications…` và 3 schema `NotificationOut`,
  `NotificationMarkReadBody`, `NotificationEmptyBody`; không đường hay schema cũ nào đổi.
- Không `pragma: no cover`, không `pragma: no branch`, không `skip`/`xfail` mới, không hạ ngưỡng. Bốn chú thích
  bỏ qua trong toàn bộ diff **đều có mã và lý do**: `# noqa: S603` (×2, `subprocess` của test ranh giới),
  `# type: ignore[import-untyped]` (`testcontainers.redis`), `# noqa: PT011`.

## Hai FIX trên cùng nhánh — soát riêng

Cả hai đã được người dùng duyệt (`docs/fixes.md` dòng 978–999, tiền lệ FIX-107/108) và mỗi FIX một commit riêng
chỉ chạm đúng file test được nêu:

- **FIX-109** (`15e5b66` + `a7f2d1a`, `apps/api/project_members/tests/test_sinks.py`, `Prompt: B2-02`) — **không**
  nhập module B4-02: test dò qua `extensions.discover(SINKS_SUBMODULE, sinks.ATTR)` và chỉ khẳng định chủ sở hữu
  khớp `apps.api.*.invite_sinks`. Assert **chặt hơn** trước chứ không nới: thêm "đúng một chủ sở hữu". Xanh trên
  `main` (chưa có `invite_sinks.py` → `_NoopSink`, nhánh `if` bỏ qua) lẫn trên nhánh (đi vào nhánh `if`).
- **FIX-110** (`9f3398f` + `f1a98f0`, `apps/api/streams/tests/test_registry.py`, `Prompt: B4-01`) — đổi
  `build_registry(None)` (dò repo thật) thành `build_registry(_app_with())` (bảng override rỗng, helper có sẵn
  trong file), giữ **nguyên ba assert** `AnyEvent` / không `policy` / không `snapshot`. Kết quả không còn phụ thuộc
  việc B4-02 có tồn tại trên đĩa hay không → xanh ở cả hai phía. `core_test_env` thêm ở `f1a98f0` là vì
  `extensions.override` đọc cấu hình lõi.

Cả hai vẫn nằm trong `apps/api/{streams,project_members}/**` mà [12] cấm, nhưng đó chính là ngoại lệ FIX đã duyệt,
và **mã sản phẩm** của B2-02 / B4-01 không đổi một dòng nào.

## Ba "lệch khỏi prompt" tác giả tự khai — đánh giá từng cái

**(a) Thân #20 kiểm bằng validator `mode="before"` để `field` luôn là `"ids"` — chấp nhận.**
[6] đòi "`ids` 1–`MARK_MAX` phần tử, mỗi phần tử 1–64 ký tự; sai → 422 `field:"ids"`". Khai bằng ràng buộc
Pydantic thường sẽ cho `loc` là `("body","ids",3)` → `field:"ids.3"`, trái yêu cầu. Validator gộp cả mảng ở một
chỗ là cách duy nhất giữ đúng hợp đồng, và nó còn đọc `MARK_MAX` lúc chạy nên `settings_env` đổi được trần.
Giá phải trả có thật → finding 3.

**(b) Bus đồng bộ cache theo URL broker, không hàm reset — chấp nhận, cache này có tải trọng thật.**
`packages/messaging/redis.py:152 _sync_client` **không** cache, nên thiếu `@cache` ở `_sync_bus` thì mỗi thông báo
dựng một `redis.Redis` + pool mới trong luồng sau commit. Khoá theo URL là đúng: `streams_redis_sync()` đọc
`get_messaging_settings().redis_broker_url` ngay lúc gọi, nên hai giá trị luôn khớp nhau. Không cần hàm reset vì
đổi URL tự sinh khoá mới — và `test_notify__J10` **chứng minh** điều đó: nó đổi `REDIS_BROKER_URL` từ container đã
dừng sang Redis dùng chung giữa chừng rồi khẳng định XADD tới nơi. Đua `functools.cache` (hai luồng cùng trượt)
vô hại: `SyncEventBus.__init__` chỉ băm script, `redis.Redis.from_url` nối lười, nên bản bị bỏ chưa mở socket nào.
Vẫn còn một vết nhỏ về hình thức → finding 8.

**(c) Migration viết tay theo khuôn b3-05 — chấp nhận, đã được cổng chứng minh.**
`r20260928_b4_02` ↔ `down_revision = "r20260928_b3_05"`, **đúng 1 head**, `downgrade` đủ, expand thuần (chỉ
`create_table` + `create_index`). Tôi đối chiếu từng hằng số với `packages/db/models/notifications.py`:
`one_of()` **không** sắp xếp và `_sql_list()` **có** sắp xếp — cả hai đều cho ra đúng chuỗi trong migration
(`KINDS` theo thứ tự khai, `FLOOR_PLACES` theo a→z). Bước 6 chạy "model khớp DB" và "tên CHECK khớp model" đều đạt,
nên rủi ro lệch tay bằng 0.

## Soát trọng tâm (đã tự đọc mã, không dựa vào báo cáo)

- **`notify`** (`service.py:105`): `_check` chạy trước mọi thứ và chỉ ném `ValueError`; `clean_label` đổi
  whitespace **trước** rồi mới bỏ `Cc`/`Cf` (đúng thứ tự — `\n`, `\t` là khoảng trắng chứ không phải rác, `U+200B`
  là `Cf` và `str.isspace()` trả `False` nên bị bỏ đúng); `pg_insert(...).on_conflict_do_nothing(
  index_elements=[dedupe_key]).returning(...)`; dòng đã có mà `stream_id IS NULL` **vẫn** đăng ký `publish`
  (`service.py:153-154`, J10); không `commit` ở bất kỳ đâu.
- **K17/K18/K32/K36**: không có XADD nào trong giao dịch — đường duy nhất là `on_after_commit`; chỉ gọi
  `publish_once` với khoá `dedupe_scope() = "notifications:" + dedupe_key` và `ttl_s = DEDUPE_TTL_S`; callback
  **không** chạm DB (test khẳng định `stream_id is None` ngay sau `notify`+commit). `except AppError` là đúng biên:
  `packages/messaging/redis.py:237 redis_errors()` dịch lỗi phụ thuộc thành `AppError` 503, còn lỗi lệnh/script
  cố ý nổi lên (R-16) và khung `hooks.py` vẫn chặn nó lại. Lịch quét bù đọc bằng session ngắn → **đóng session** →
  XADD → session ngắn `UPDATE … WHERE stream_id IS NULL`; cửa sổ đúng `(now − WINDOW, now − AFTER]`;
  `NotificationsSettings._window_within_dedupe` kiểm `WINDOW × 2 ≤ TTL` lúc nạp.
- **`trim`**: bước 1 xoá dòng ẩn `created_at < now − HIDDEN_PURGE_AFTER_S` (`~visible_to_owner()`), bước 2
  `row_number() OVER (PARTITION BY user_id ORDER BY created_at DESC, id DESC) > KEEP_MAX`; cả hai đi theo lô,
  một commit mỗi lô, dừng khi `rowcount < batch`.
- **Dây (K01/K02)**: `notification_wire` là **một** nguồn cho cả REST (`router.py:29,54`) và SSE
  (`stream_providers.py` dùng cùng `NotificationOut`); không có `userId`, `dedupeKey`, `streamId`; `floorId` và
  `excerpt` **vắng khoá** khi NULL — hai tầng bảo đảm: `payload.py:24-27` không đặt khoá, và
  `WireModel._drop_none` (`apps/api/core/wire.py:107`) bỏ trường `None`; `createdAt` qua `WireDatetime` →
  `.sssZ`. Không câu nào trong `messages.py` kết thúc bằng `objectLabel` (có test chốt).
- **#19–#22**: `visible_to_owner()` là **một** `EXISTS` tương quan (dự án chưa xoá mềm **và** còn thành viên) nằm
  trong đúng một truy vấn cùng `ORDER BY created_at DESC, id DESC` và `LIMIT LIST_MAX`. #20 bỏ qua id lạ/của người
  khác vì `user_id` nằm trong `WHERE`. #21 **không** lọc hiển thị → gồm cả dòng ẩn, đúng [6]. #22: `is_id` sai mẫu
  → 404, không thấy/của người khác/bị ẩn → 404, `kind ≠ projectInvite` → 422 `NOTIFICATION_NOT_INVITE`, idempotent
  (chỉ ghi khi đang `is_read = False`), **không** đụng `ProjectMembership` (có test so sánh trước/sau).
  #20, #21 trả 204 thân rỗng (`response_class=Response`, test khẳng định `response.content == b""`).
- **Sink**: `user_id == actor_id` → `return` sớm; tên người thêm lọc `deleted_at IS NULL` nên người đã xoá mềm cho
  `None` → câu vô danh; khoá `projectInvite:{project}:{user}:{%Y%m%d%H}` theo `astimezone(UTC)`; chạy thẳng trong
  giao dịch của N3, XADD nằm ở callback sau commit → rollback là không dòng, không sự kiện (J09).
- **Model/revision**: CHECK 3 `kind`, 9 `place`, luật tầng, luật `projectInvite`; FK `project_id` ON DELETE
  CASCADE; `dedupe_key` UNIQUE; đúng hai index như [5].
- **Bảy file [8] "Nhập"**: `test_boundary__worker_modules_import_without_web_libraries` chặn `fastapi`, `jwt`,
  `argon2` trong `sys.modules` của **tiến trình con** rồi nhập từng module — chặn được cả đường gián tiếp. Cộng
  thêm contract `apps.api.*.jobs` của `lint-imports`.
- **Test**: phủ **đủ** mọi dòng "Test đặt tên theo việc" của [8]. Dùng Postgres/Redis thật, `testcontainers`
  dừng container thật ở J10, không `fakeredis`; sink chạy qua N3 thật với phiên đăng nhập thật và luồng S2 mở
  sẵn, ghi qua `record_stream_frames` cho H5; tên đúng `test_<operationId>__<caseid>` và `test_<hàm>__J0x`.
- **SEC**: không IDOR (mọi truy vấn kẹp `principal.user_id`), không mass assignment (`extra="forbid"` hai chiều),
  không nhận người nhận/người thực hiện từ thân (K05), log chỉ mang `notification_id`.

## Finding

Không có P0, không có P1.

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | CON-03 | `scalar_one()` trên đường khử trùng giả định dòng xung đột **luôn** đọc lại được. Đúng ở READ COMMITTED (engine không đặt `isolation_level` nên đây là mặc định): `ON CONFLICT DO NOTHING` chờ giao dịch kia rồi câu `SELECT` sau lấy ảnh chụp mới. Nhưng nếu sau này ai nâng isolation lên REPEATABLE READ thì `notify` ném `NoResultFound` → 500 cho N3 / task hỏng, mà không có test nào chốt giả định này | `apps/api/notifications/service.py:152` | `scalar_one_or_none()` rồi trả `None` khi không thấy (ngữ nghĩa "đã có người khác lo" vẫn đúng), hoặc thêm comment R-05 nêu rõ ràng buộc "chỉ đúng ở READ COMMITTED" |
| 2 | P3 | PERF-05 | `overflow` không lọc trước theo người: mỗi vòng lô dựng lại `row_number()` trên **toàn bảng** rồi mới `LIMIT batch`, nên lịch dọn là O(N) mỗi lô × (số dòng thừa / batch). Vô hại hôm nay (mỗi người ≤ `KEEP_MAX` cộng phần trôi giữa hai lượt), nhưng không có comment nêu ngưỡng và đường nâng cấp như R-05 đòi cho quyết định "thuật toán chậm có chủ ý" | `apps/api/notifications/jobs.py:103-114` | Thêm comment nêu ngưỡng; hoặc hẹp `ranked` lại bằng `WHERE user_id IN (SELECT user_id FROM notifications GROUP BY user_id HAVING count(*) > KEEP_MAX)` |
| 3 | P3 | API-04 | Hệ quả của lệch (a): schema `NotificationMarkReadBody` trong `docs/contracts/openapi.json` chỉ còn `{"ids": {"type":"array","items":{"type":"string"}}}` — mất `minItems` 1, `maxItems` `MARK_MAX`, `maxLength` 64. Ràng buộc vẫn được BE thi hành đầy đủ (có test C02 cho cả 7 ca) và được ghi ở `description`, nhưng client sinh từ OpenAPI không thấy | `apps/api/notifications/schemas.py:39-48` → `docs/contracts/openapi.json:2196-2213` | Bù bằng `json_schema_extra={"minItems":1,"maxItems":…,"items":{"maxLength":64}}` trên trường `ids`, giữ nguyên validator |
| 4 | P3 | MNT-03 | `_fixture_pair` và `_pair` là **cùng một hàm** (tạo người dùng + dự án của họ) chép sang hai file test, trong khi `tests/support.py` chính là chỗ chung đã có sẵn — R-07 đòi tách ngay ở lần thứ hai | `apps/api/notifications/tests/test_notify.py:40` và `tests/test_jobs.py:47` | Dời một bản vào `tests/support.py`, hai file cùng nhập |
| 5 | P3 | MNT-05 | Nhánh khoảng 713 dòng mã sản phẩm (chưa kể test và `openapi.json`), quá ngưỡng 400 dòng logic của §1 | cả nhánh | **Không đáng tách**: đơn vị giao việc là một prompt = một module theo BE-00 §2, tách ra sẽ cắt ngang hợp đồng `notify`/route/lịch vốn phải ra cùng lúc. Tôi đã đọc toàn bộ diff nên mục tiêu "review được" của MNT-05 vẫn đạt; ghi lại cho đủ, không chấm P2 |
| 6 | Nit | MNT-01 | `notify` dài 51 dòng, quá R-08 đúng 1 dòng (chữ ký 14 dòng vì 12 tham số keyword) | `apps/api/notifications/service.py:105-155` | Không cần sửa; nếu đụng lại thì tách khối `.values(...)` thành `_row_values(...)` |
| 7 | Nit | TEST-02 | `suppress(Exception)` trong finalizer của fixture `dead_redis` là bắt ngoại lệ rộng ([9] cấm) | `apps/api/notifications/tests/test_notify.py:208` | Hẹp lại thành lỗi `docker`/`testcontainers` cụ thể, hoặc kiểm trạng thái container trước khi `stop()` |
| 8 | Nit | MNT-04 | `_sync_bus(broker_url)` **không dùng** tham số của nó (chỉ để làm khoá cache) — đọc dễ tưởng là bỏ sót | `apps/api/notifications/service.py:44-50` | `SyncEventBus(streams_redis_sync(MessagingSettings(redis_broker_url=broker_url)))`, hoặc đổi tên tham số thành `_cache_key` và nói rõ trong docstring |

## Sổ nợ (§5)

Tác giả khai "Nợ và việc chưa làm: không" — tôi đối chiếu `DEBT.md`: **không có** dòng `NO-` nào mang B4-02, và
cũng không có nợ nào của nhánh này phải ghi, nên khai đó đúng. `DEBT.md` hiện **không** có nợ `P0`/`P1` nào còn
trạng thái mở (⬜), nên không có gì chặn merge theo R-35/R-38. Tám finding trên đều là `P3`/`Nit` nên theo ma trận
không bắt buộc phải có dòng `DEBT.md`; nếu muốn theo dõi thì finding 1, 2, 3 đáng một dòng gộp.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 4 | 0,60 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 4 | 0,40 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 4 | 0,40 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,55 / 5** |

## PHÁN QUYẾT: APPROVE

Không P0, không P1, điểm 4,55 ≥ 4,0. Cổng đầy đủ do chính phiên review chạy lại thoát 0 với cả 8 bước cộng 5b
đạt, 5702 test qua, độ phủ mọi gói bị chạm và tổng đều vượt 90/90, `case_gate` thiếu 0 cho cả bốn `op`, H1/H3/H4/H5
đạt và `migrate_check` xác nhận đúng một head cùng "model khớp DB". Ba điểm lệch khỏi prompt đều có lý do đứng
được và hai trong ba được chính test chốt lại. Phần nghiệp vụ khó nhất — một lần XADD qua `publish_once`, callback
sau commit không ghi DB, lịch quét bù không giữ session khi gọi Redis, và đường giao lại sau khi Redis chết — được
kiểm bằng Postgres/Redis thật với container bị dừng giữa chừng, đúng tinh thần K23/K32/K36. Tám finding còn lại là
`P3`/`Nit`, không cái nào chặn merge; nên xử lý finding 1 và 3 ở một FIX nhẹ sau khi gộp.

Merge được. Việc merge thuộc phiên gọi review này, không phải phiên này.
