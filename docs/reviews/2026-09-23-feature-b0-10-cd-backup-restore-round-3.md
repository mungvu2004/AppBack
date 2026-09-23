# Review merge `feature/b0-10-cd-backup-restore` → main — **lượt 3**

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` **độc lập** (worktree `b0-10-review3`, không phải tác giả, không phải người điều phối; không sửa mã, không merge) · Commit đầu nhánh: `6c5e37e`
- Phán quyết lượt 2: `docs/reviews/2026-09-23-feature-b0-10-cd-backup-restore-round-2.md` (**APPROVE**, 4,55/5 trên `872fce1` — 0 P0/P1, 1 P2, 3 P3, 4 Nit)
- Phạm vi lượt này: `git diff 872fce1..6c5e37e` — **4 tệp, +63/−6** (đóng N2, N3, N6, N7 của lượt 2), cộng soát hồi quy toàn bộ bất biến [9] trên `main...HEAD` và ý kiến về bằng chứng `NO-117` mới trong `backend/dieu-phoi/chay/B0-10/REPORT.md`.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, tự chạy tại chỗ trên `6c5e37e`, container `appback-verify-b0-10-review3-verify-run-88f53638b3f5`, lượt 1/1 (mã thoát lấy bằng `docker wait`, không lấy từ báo cáo tác giả).
- Bước 5: **2556 passed, 10 skipped, 1 deselected** (344,2 s) — đúng +1 test so với lượt 2, khớp đúng một test mới của N3.
- Độ phủ (số của lượt chạy này): tổng **dòng 99,07 % · nhánh 97,37 %**; tập file bị chạm **100,00 % · 100,00 %**. Cả hai ngưỡng 90 % đều đạt.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị perf bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt |
| 7 | H1 H3 H4 H5 | đạt. H4/H5 `không áp dụng` **hợp lệ** — B3-05/B4-01 chưa hợp nhất (BE-00 §12) |
| 8 | openapi | đạt (8174 byte) |

Điều kiện dừng sớm (§2): **không có**. Cây sạch (`git status --porcelain` rỗng); `changes/B0-10.md` có; **12/12** dòng đầu commit đúng Conventional Commits và **12/12** có trailer `Prompt: B0-10`; diff `main...HEAD` không chạm `docs/charter/*`, `openapi.json`, `uv.lock`, `tools/**`, `APPFRONT_SHA`; không thêm `pragma: no cover`, `# noqa` trần, `# type: ignore` trần, `skip`/`xfail`, không hạ ngưỡng.

## 1. Đối chiếu 4 finding của lượt 2 — 3 đóng, 1 **đóng hụt**

Tự kiểm trong mã, không tin bảng của tác giả.

| # lượt 2 | Mức | Trạng thái | Bằng chứng tự kiểm |
|---|---|---|---|
| N2 (TEST-02/K23) | P3 | **đóng** | `test_drill.py:14-20` thêm `_FAKE_DOCKER_BODY`/`_bin_dir()`; hai test ở `:31,:50` nay truyền `bin_dir=_bin_dir(tmp_path)`, nên `trap cleanup EXIT` của `drill.sh` gọi `docker` **giả** chứ không phải `docker` thật trên `PATH` — kịch bản xoá volume của một lượt `drill.sh`/compose chạy song song trên máy dev đã bị chặn. Xem thêm R3 (Nit) về việc test vẫn chưa *khẳng định* được điều đó. |
| N3 (R-05) | P3 | **đóng hụt — xem R1** | Test mới `test_deploy_default_swap_settle_s_covers_nginx_resolver_ttl` (`test_deploy.py:293-318`) có, đọc `valid=(\d+)s` từ **cả hai** template thật và không chép tay hằng số. Nhưng nó trích mặc định của `lib.sh` bằng `re.search` trên toàn tệp, mà bản vá N6 vừa chèn **một lần xuất hiện thứ hai đứng trước** — nên test đang chốt chuỗi in ra ở chế độ `--dry-run`, **không** chốt `sleep` thật. Ràng buộc mà N3 muốn khoá vẫn hở. |
| N6 (MNT-06) | Nit | **đóng** | `lib.sh:86` thêm `plan "chờ nginx tự dịch lại DNS (${APPBACK_API_SWAP_SETTLE_S:-11}s)"` đúng giữa hai dòng `plan` cũ; `test_deploy.py:104` nới danh sách thứ tự thành `[pull, migrate, scale api=2, healthy, "dịch lại DNS", xoá, smoke]`. Kế hoạch in ra nay khớp thứ tự thật (`:120` `sleep` rồi `:121-124` `stop`/`rm`). |
| N7 (R-07) | Nit | **đóng** | `restore.sh:149-150` thêm đúng chú thích đề xuất. Tự kiểm mốc dòng: guard `case "$storage" in s3 \| local)` thật sự ở `:83`, còn `docker compose stop` ở `:122` và `DROP DATABASE` ở `:126` — chú thích không trỏ sai dòng. |
| N8 (TEST-03/R-01) | Nit | **còn mở** | `deploy/backup/tests/test_restore.py:254` vẫn `monkeypatch` không annotation. Vô hại (Nit lượt 2, không bắt buộc), ghi lại ở R4. |

**Hồi quy bất biến [9] — tự kiểm lại trên `6c5e37e`, không hồi quy nào:**

- migrate (`deploy.sh:40`) vẫn **trước** `swap_api` (`:45`); `swap_api` vẫn chờ `new_id` healthy (`lib.sh:113`) **rồi** mới `sleep` settle (`:120`) **rồi** mới `docker stop`/`rm` container cũ (`:121-124`) — dòng `plan` của N6 nằm trong nhánh `DRY_RUN`, không đụng đường chạy thật; hết giờ healthy thì xoá container **mới**, giữ cũ (`:114-116`).
- Không `alembic downgrade` ở đâu: `grep -rn downgrade deploy/` chỉ ra hai **chú thích** (`restore.sh:156`, `rollback.sh:3`); `restore.sh` chỉ `upgrade head`.
- **0** biểu thức `${{` trong bất kỳ khối `run:` nào của `.github/workflows/*.yml` (quét lại bằng bộ phân tích thụt lề, không grep thô) — luật siết ở lượt 2 vẫn đúng.
- 3 `uses:` đều ghim SHA 40 ký tự (`actions/checkout@3d3c42e5…`, `docker/setup-buildx-action@f87e5991…`, `crazy-max/ghaction-github-runtime@04d248b8…`); không `continue-on-error`, không `pull_request_target`.
- `packages: write` **chỉ** ở `images` (`deploy.yml:41`) và `promote` (`:148`); `staging`/`production`/`rollback` không có.
- `concurrency` ở **từng job**, không ở mức workflow; cả 5 nhóm `cancel-in-progress: false` (`:36-38, :96-98, :142-144, :177-179, :224-226`).
- `notify.yml`: `permissions: {}` (`:11`), **không `uses:` nào** ⇒ không checkout mã của PR fork; 5 giá trị `github.event.workflow_run.*` đều đi qua `env:` (`:17-22`) ⇒ an toàn với `workflow_run` từ fork.
- `restore.sh`: kiểm SHA-256 toàn bộ tệp manifest ở `:50-73` — **trước** `docker compose stop` (`:122`) và `DROP DATABASE` (`:126`). Thứ tự [2] giữ nguyên.
- `shellcheck -x` (trong bước 5, `test_shellcheck.py`) quét bằng glob nên tự phủ các dòng mới của `lib.sh`/`restore.sh`: 0 cảnh báo.
- Secret: không `set -x`, secret chỉ giãn **trong** container, khoá ssh vào `$RUNNER_TEMP` + `chmod 600` + `trap rm -f`; bản sao lưu không chứa giá trị secret.

## 2. Finding mới lượt 3

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| **R1** | **P3** | TEST-04 / R-05 | **Bản vá N6 vô hiệu hoá test của N3.** `re.search(r"APPBACK_API_SWAP_SETTLE_S:-(\d+)", lib_sh)` lấy **lần xuất hiện đầu tiên** trong tệp. Trước vòng này lần đầu tiên là `sleep "${APPBACK_API_SWAP_SETTLE_S:-11}"`; N6 vừa chèn chuỗi `plan` chứa cùng mẫu ở `lib.sh:86`, **đứng trước** `:120`. Từ nay test chốt hằng số trong **câu thông báo của `--dry-run`**, không chốt độ dài `sleep` thật. Đã chứng minh tại chỗ: hạ mặc định của `sleep` ở `:120` xuống `2` mà giữ nguyên chuỗi `plan` ⇒ test vẫn **xanh** (`assert 11 >= 10 + 1`), trong khi deploy thật quay lại 502 của `NO-116`. Đúng kịch bản mà N3 được dựng ra để chặn, chỉ đổi tác nhân từ B0-08 sang chính B0-10. | `deploy/scripts/tests/test_deploy.py:303` | Gộp với R2: khai báo mặc định **một lần** ở đầu `lib.sh` cạnh `IMAGE_REGISTRY` — `: "${APPBACK_API_SWAP_SETTLE_S=11}"` (**không** dấu `:` trong toán tử, theo đúng bài học `NO-114`), rồi dùng `$APPBACK_API_SWAP_SETTLE_S` trần ở `:86` và `:120`. Khi đó mẫu regex chỉ còn **một** chỗ khớp và test tự khoá lại đúng hằng số. Nếu không muốn đổi `lib.sh`: neo regex vào dòng lệnh thật — `r'sleep "\$\{APPBACK_API_SWAP_SETTLE_S:-(\d+)\}"'` — hoặc `re.findall` + khẳng định mọi lần xuất hiện bằng nhau. |
| **R2** | Nit | R-07 | Hằng số `11` nay nằm ở **ba** nơi độc lập: `lib.sh:86` (chuỗi `plan`), `lib.sh:120` (`sleep` thật), `deploy/scripts/README.md:272` (bảng biến môi trường). Ba bản sao của một ràng buộc vận hành (`>= TTL nginx + 1s`) là đúng thứ R-07 cấm, và nó vừa gây ra R1 chứ không chỉ là vấn đề thẩm mỹ. | `deploy/scripts/lib.sh:86,120`, `deploy/scripts/README.md:272` | Như R1: một nguồn duy nhất ở đầu `lib.sh`. README có thể giữ giá trị vì là tài liệu người đọc, nhưng khi đó nên là chỗ **duy nhất** còn chép tay. |
| **R3** | Nit | TEST-05 | `_bin_dir()` dựng `docker` giả bằng `fake_bin`, mà thân chuẩn của `fake_bin` mở đầu bằng `printf … >> "$FAKE_LOG"`. Hai test của `test_drill.py` **không** đặt `FAKE_LOG`, nên mỗi lần gọi stub in `bash: : No such file or directory` ra stderr và **mất dòng log** (stub vẫn `exit 0`, đã kiểm tại chỗ — test không vì thế mà hỏng). Hệ quả: test *ngăn* được `docker` thật nhưng **không khẳng định** được là đã ngăn; ai lỡ bỏ `bin_dir` sau này thì test vẫn xanh và `docker compose down -v` thật lại chạy. | `deploy/scripts/tests/test_drill.py:18,34,54` | Đặt `FAKE_LOG` (như các test khác của nhánh) rồi khẳng định dương: `assert any("compose down -v" in l for l in read_log(log))`. Biến một biện pháp phòng ngừa thành một bất biến có test. |
| **R4** | Nit | R-01 | Tồn từ N8 lượt 2, chưa sửa: thiếu annotation `monkeypatch: pytest.MonkeyPatch`. Lọt cổng vì `[tool.mypy] files` của `pyproject.toml` không gồm `deploy/` (vấn đề tiền tồn tại của B0-01, không do nhánh này gây ra). | `deploy/backup/tests/test_restore.py:254` | Thêm annotation. Riêng việc đưa `deploy/` vào tầm `mypy` là việc của B0-01, không phải nhánh này. |

Không có finding **P0**, **P1** hay **P2** mới. Không phát hiện hồi quy nào so với lượt 2.

## 3. Ý kiến về bằng chứng `NO-117` của vòng sửa 2 (thông tin cho người dùng, không chặn merge)

`REPORT.md` (mục vòng sửa 2) ghép mốc thời gian từng phản hồi không-2xx với `docker events`: **4/7** lỗi của hai lượt đo trùng trong **≤ 130 ms** với sự kiện `network disconnect <mạng compose>` phát ra khi `swap_workers()` (`lib.sh:131`, `docker compose up -d --no-deps worker beat`) **tái tạo** `worker`/`beat`; **3/7** còn lại không khớp sự kiện mạng nào.

**Có phải hiện tượng Docker Desktop/WSL hay không — trả lời: một phần, không phải toàn bộ.**

- Cơ chế là **thật và không riêng của Docker Desktop**. Khi một container rời bridge network, Docker viết lại bảng chuyển tiếp của bridge và các luật `iptables` theo mạng; gói tin đang bay của **các container khác** trên cùng bridge (kể cả `web`, vốn không bị đụng) có thể rơi trong vài chục ms. Đây là hành vi của Linux bridge, có trên cả VPS thật.
- **Độ lớn thì bị môi trường khuếch đại.** Trên máy đo, toàn bộ engine nằm trong VM WSL2 với một bridge ảo và `docker-proxy`, đồng thời chạy tới 2 container `verify-run` song song và ~7 dịch vụ có healthcheck `exec` mỗi 5 s. **3/7** lỗi không khớp sự kiện mạng nào gần như chắc chắn thuộc nhóm tranh CPU của chính máy đo và sẽ không tái hiện trên VPS chuyên dụng.
- **Kết luận thực dụng:** trên VPS Linux thật, kỳ vọng phần dư **nhỏ hơn, không bằng 0**. Vì vậy **không nên đóng `NO-117` theo số của máy này theo bất kỳ chiều nào** — phải đo lại trên VPS trước M1, đúng như dòng nợ đang ghi.

**Biện pháp trong `so_huu` B0-10 (`deploy/scripts/**`) — có, nhưng chỉ giảm, không triệt:**

1. **Đảo thứ tự: gọi `swap_workers` TRƯỚC `swap_api`** (`deploy.sh:45-46`, sửa 2 dòng). Không xoá được khoảng nghẽn bridge, nhưng đẩy nó ra **ngoài** cửa sổ `api` đang đổi, nên hai nhiễu không chồng lên nhau và một request trúng nghẽn vẫn còn một `api` khoẻ để thử lại (và sẽ được cứu hẳn nếu B0-08 thêm `proxy_next_upstream`). An toàn về lược đồ: `migrate` chạy ở `deploy.sh:40`, trước cả hai. **Đây là biện pháp duy nhất đáng làm trong B0-10.**
2. **Không tái tạo `worker`/`beat` khi ảnh không đổi.** Compose đã tự no-op khi cấu hình không đổi, nên chỉ có ích cho lượt deploy lại **cùng tag** (`drill.sh`, rollback về bản đang chạy). Nếu muốn chắc: so ảnh của `docker compose ps -q worker` với ảnh đích trước khi gọi `up`. Phạm vi hẹp, giá trị thấp.
3. **Tách và giãn:** `up -d --no-deps worker`, ngủ ngắn, rồi `beat` — chia đôi lượng xáo trộn bridge đồng thời, đổi lấy ~2 s mỗi lượt deploy. Cải thiện biên.
4. Dời `run_smoke` ra sau một khoảng settle chỉ làm **đẹp phép đo**, không giúp lưu lượng thật — không nên làm.

**Không biện pháp nào làm điều [8] "không gián đoạn" trở thành đúng theo nghĩa đen.** Bản vá đúng vẫn là `upstream` + `proxy_next_upstream error timeout http_502 http_503` ở `deploy/nginx/templates/{dev,prod}/app.conf.template` — **thuộc B0-08, nằm trong khối [12] "KHÔNG ĐƯỢC SỬA" của B0-10**. Điểm đáng chú ý: **một** bản vá đó đóng **cả hai** nguyên nhân (đua bí danh DNS lúc tạo `api` mới, **và** nghẽn bridge lúc tái tạo `worker`/`beat`), vì cả hai đều hiện ra dưới dạng **một** lần `connect()` upstream hỏng mà một lượt thử lại sẽ sống sót. Đó là lý do không nên đổ thêm công vào B0-10 cho việc này.

Ghi chú sổ nợ: `DEBT.md:137` (`NO-117`, trên `main`, thuộc người điều phối) đã được cập nhật một phần — nay nêu giả thuyết DNS-alias và trỏ FIX B0-08 — nhưng **chưa** ghi nguyên nhân thứ hai (nghẽn bridge khi `swap_workers` tái tạo `worker`/`beat`) mà `REPORT.md:29` vừa chứng minh, và vẫn để chủ là B0-10. Nên viết lại thành **nguyên nhân kép**, chủ **B0-08**, giữ mức. Ngoài diff nhánh, không chặn merge.

## 4. Test so với điều [8]

Test của vòng này giữ đúng tinh thần lượt 2 ở hai chỗ: test TTL đọc `valid=` từ **cả hai** template thật thay vì chép hằng số, và test thứ tự `--dry-run` chốt vị trí tương đối chứ không chốt văn bản đầy đủ. Một chỗ hụt — phía `lib.sh`, regex bắt nhầm lần xuất hiện (R1), nên nửa "chốt mặc định thật" của ràng buộc chưa có test. Đây là lỗi *độ chặt của test*, không phải lỗi mã chạy: `sleep "${APPBACK_API_SWAP_SETTLE_S:-11}"` ở `:120` **đang đúng** với `valid=10s` hiện tại của cả hai template (tự kiểm: `dev:30`, `prod:29`). Vì vậy R1 là P3 chứ không phải P1 — không có lỗi vận hành nào đang hiện hữu, chỉ mất một lưới an toàn cho tương lai.

## 5. Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 4 | 0,60 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 | 0,40 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 3 | 0,15 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,55 / 5** |

TEST giữ 4: N2 đóng (+), nhưng N3 đóng hụt (R1) và R3 bù trừ hết. MNT giữ 4: N7 đóng (+), nhưng R2 thêm một bản sao hằng số (−).

## PHÁN QUYẾT: APPROVE

Vòng sửa 2 đóng **3/4** finding của lượt 2 đúng như đề xuất, không hồi quy bất biến [9] nào, và cổng tự chạy tại chỗ **mã thoát 0** ngay lượt đầu (2556 test, độ phủ 99,07 % dòng / 97,37 % nhánh, tập file bị chạm 100 %/100 %). Không có P0, P1 hay P2 mới. Phán quyết **APPROVE** của lượt 2 giữ nguyên hiệu lực.

Finding duy nhất đáng nói là **R1**: hai bản vá của cùng vòng này (N3 dựng test, N6 thêm một dòng `plan`) vô tình triệt tiêu nhau, vì `re.search` bắt lần xuất hiện đầu tiên và dòng `plan` mới đứng trước dòng `sleep` thật. Mã chạy **không sai** — `sleep` mặc định 11 s vẫn phủ `valid=10s` của cả hai template — nên đây là mất lưới an toàn cho tương lai, không phải lỗi vận hành, và không chặn merge. Đáng ghi nhận là nó cũng minh hoạ đúng thứ R-07 cảnh báo: bản sao thứ ba của một hằng số vận hành là thứ đã phá cái test được dựng riêng để canh hằng số đó.

**Duyệt merge nhánh này.** Ba việc theo sau, không việc nào chặn:

1. **Một FIX nhỏ cho B0-10** gom R1 + R2 + R3 + R4: đưa mặc định `APPBACK_API_SWAP_SETTLE_S` về **một** khai báo ở đầu `lib.sh` (việc này tự động sửa R1 và R2 cùng lúc), đặt `FAKE_LOG` + khẳng định dương trong `test_drill.py`, thêm annotation `monkeypatch`.
2. **FIX cho B0-08** (`deploy/nginx/templates/{dev,prod}/app.conf.template`): `upstream` + `proxy_next_upstream error timeout http_502 http_503`. Đóng **cả hai** nguyên nhân của `NO-117` bằng một thay đổi — đây là việc duy nhất làm điều [8] "không gián đoạn" thành đúng.
3. **Viết lại `NO-117`** trên `main` theo nguyên nhân **kép** đã chứng minh (đua bí danh DNS của `api` mới + nghẽn bridge khi `swap_workers` tái tạo `worker`/`beat`), đổi chủ sang **B0-08**, và **không đóng nó bằng số đo trên Docker Desktop** — phải đo lại trên VPS Linux thật trước M1.

Trước khi bật `production` lần đầu: giám sát và retry ở tầng gọi API, đúng như lượt 2 đã nêu.
