# Review merge feature/b6-03b-training-runner → main — lượt 2

- Ngày: 2026-10-02 (UTC, `date -u`) · Reviewer: phiên `/merge-review` (lượt 2, phiên độc lập R-37)
- Lượt 1: **REQUEST CHANGES 4,36/5** trên `93eab65` — `docs/reviews/2026-10-01-feature-b6-03b-training-runner.md`
- Commit đầu nhánh lượt này: **`91ff59a`** (lượt review mở ở `cc6a333`; điều phối đẩy thêm hai commit **trong lúc**
  lượt này đang chạy, để đóng hai finding mới M1 và M3 mà tôi vừa nêu — delta ấy được soát ở mục riêng bên dưới)
- Phạm vi soát: `git diff 93eab65..91ff59a`, tức bốn commit:
  - `bca828f` *test(ml-training): fix review round 1 findings 1-9*
  - `cc6a333` *style(ml-training): blank lines and the real `_wait` predicate type*
  - `d3f20a8` *test(ml-training): cover the stop reason beating a late trainer error* ← đóng M1
  - `91ff59a` *test(ml-training): clear the ml settings cache around every test* ← đóng M3
- Diff tổng: 8 tệp, **chỉ** `apps/ml/training_runner/**` (`reporter.py`, `runner.py`, `slot.py`, `watchdog.py`,
  `tests/support.py`, `tests/test_runner.py`, `tests/test_runtime.py`, `tests/test_tasks.py`). Không chạm migration,
  route, `openapi.json`, `docs/charter/*`, `uv.lock`, `DEBT.md`, tệp của prompt khác (K27 sạch).
- Phạm vi review: chỉ vòng sửa. Phần đã đạt ở lượt 1 **không** soát lại (R-33b).

## Chứng cứ cổng

Không chạy lại cổng đầy đủ (chỉ thị điều phối). Chứng cứ dùng, theo **mã thoát thật**:

| Nguồn | sha | Nội dung | Kết quả |
|---|---|---|---|
| `backend/dieu-phoi/chay/B6-03b/M/gate-2.log` | `93eab65` | `run.sh verify` đầy đủ, 8 bước | mã thoát **0** (bảng E.10 lượt 1) |
| `M/pre-5.log` (`M/pre.sh`, `set -euo pipefail`) | `cc6a333` | `collect-only -n 6` · `ruff format --check .` · `ruff check .` · `mypy` · `lint-imports` · `coverage run -p no:randomly -m "not perf" apps/ml/training_runner` · `pytest -n 4 --dist loadfile` cùng phạm vi · **`pytest -n 6 -m "not perf" apps/ml` hai lượt liên tiếp** · soát `case_gate` của module | mọi lệnh **0** (chuỗi `pipefail` chạy tới `PREFLIGHT OK cc6a333`): 1247 tệp đã format · `All checks passed!` · `no issues found in 1043 source files` · `Contracts: 10 kept, 0 broken` · 85 passed (52,81 s) · 85 passed (32,83 s) · **323 passed** (61,76 s) · **323 passed** (70,93 s) |
| `R2/repro-1.log` + `R2/repro-1.sh` (reviewer, **một** container `run.sh shell`) | **`91ff59a`** | tái hiện finding 1 bằng lệnh đích của lượt 1, cập nhật theo tên test mới: bốn `test_run_training_job_m04_*` (một cái tham số hoá ×2) chạy **trước** `test_start_training_runner__J01` trong **cùng một tiến trình**, `-p no:randomly` | **6 passed trong 15,19 s**, `EXIT=0` (`repro-1.log:107-108`) — lượt 1 cùng lệnh này cho **1 failed, 1 passed** |
| `M/pre-7.log` | `91ff59a` | tiền kiểm của điều phối, chạy song song lượt repro này | ngoài phạm vi phán quyết này |
| `M/gate-3.log` | `91ff59a` | `run.sh verify` đầy đủ | **chưa chạy** lúc viết phán quyết (điều phối chạy một mình sau lượt repro) |

Độ phủ `apps/ml/training_runner` đo trên `cc6a333` (`pre-5.log:140-156`): **795 câu lệnh / 11 thiếu → 98,6 % dòng**,
**150 nhánh / 9 dở → 94,0 % nhánh**; `reporter.py` 99 %, `runner.py` 95 %, `slot.py` 100 %, `watchdog.py` 100 %. Trên
ngưỡng 90/90 của cả hai số. `d3f20a8` thêm test cho đúng dòng thiếu mà con số ấy để lộ (`runner.py:406`), nên độ phủ
trên `91ff59a` chỉ có thể cao hơn — con số chính thức là của cổng 3.

## Trạng thái finding 1-9 của lượt 1

| # | Mức | Trạng thái | Đã làm gì, và có đúng đề xuất không |
|---|---|---|---|
| 1 | **P1** | **ĐÓNG** | Đúng fixture đề xuất (`autouse`, `yield` rồi `reset_ml_settings_cache()`), và ở `91ff59a` còn mạnh hơn đề xuất: fixture chuyển sang `tests/support.py`, xoá cache **cả trước và sau** mỗi test, hai tệp test nhập lại (xem M3). Thứ tự tháo đúng: fixture `autouse` dựng **trước** `monkeypatch` nên tháo **sau** nó → cache bị xoá khi biến môi trường đã trả về. Chứng minh đúng hai điều kiện lượt 1 đặt ra: lượt đích `-p no:randomly` xanh (`R2/repro-1.log`, 6 passed trên `91ff59a`; lượt 1 là 1 failed) **và** `pytest -n 6 -m "not perf" apps/ml` xanh **hai lượt liên tiếp** (323 passed ×2) |
| 2 | P2 | **ĐÓNG** | `test_runner.py:148-164`: fixture `harness` nhận `tmp_path`+`monkeypatch` và `monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))` — đúng idiom `test_purge_stale_tmp_removes_old_dirs` mà lượt 1 chỉ ra. **Có hiệu lực thật**, đã truy mã sản phẩm: `runner.py:86` quét `Path(tempfile.gettempdir()).glob("training-*")` và `runner.py:242` gọi `tempfile.mkdtemp(prefix=…)` (CPython tra `gettempdir` theo tên toàn cục của chính module `tempfile`, nên bản vá ăn cả hai chỗ). Ba chỗ `assert set(_tmp_dirs()) <= before` (`__J04`, `__J05`, `_watchdog`) đều chạy **trong tiến trình** (`harness.run()`, `harness.exits`), nên khẳng định vẫn còn răng chứ không thành đúng-hiển-nhiên |
| 3 | P2 | **ĐÓNG** | Đúng cả hai đề xuất. Script tiến trình con ra hằng module `_CANCEL_WHILE_WAITING_SCRIPT` → `test_run_training_job_cancel_while_waiting` còn **32 dòng**. `test_run_training_job_m04` (~100 dòng) tách thành bốn hàm test (`…_waits_for_a_busy_slot`, `…_cpu_skips_the_gpu_lock`, `…_cuda_holds_both_locks`, `…_fails_when_a_lock_is_lost` tham số hoá cpu/slot + cuda/gpu) dùng chung bàn thử `M04` + fixture `m04`; hàm dài nhất còn lại của tệp là 32 dòng. Năm kịch bản của bản cũ giữ đủ cả năm; `len(gpu_calls) == 1` vẫn đúng vì mỗi test có danh sách riêng. `cases.toml` không khai mã M (NO-294) nên đổi tên không ảnh hưởng `case_gate` — đã soát bằng `preflight.py` ngay trên sha này |
| 4 | P3 | **ĐÓNG** | `reporter.py` nhập `MAX_METRIC_POINTS` từ `packages.ml_contracts.payloads`, bỏ `max_len = 500`; docstring sửa theo. Rủi ro lượt 1 nêu (B5-01 hạ trần → `ValidationError` mà `_send_or_log` chỉ bắt `AppError`) **đã hết**: cỡ lô bám theo chính hằng hợp đồng. `_FLUSH_EVERY_POINTS = 100 < 500` nên nhánh chia lô vẫn chưa bao giờ sinh quá một lô, nhưng nay đó là linh hoạt vô hại chứ không còn là lỗi chực chờ |
| 5 | P3 | **ĐÓNG, tốt hơn đề xuất** | `reporter.py:140` `thread.join(JOIN_TIMEOUT_S)`. Hơn thế, hằng dồn về **một** nguồn: xoá `slot.JOIN_TIMEOUT_S`, giữ `watchdog.JOIN_TIMEOUT_S` (thêm docstring nói rõ vai trò), `slot.py` và `reporter.py` cùng nhập từ đó. Không tạo vòng nhập (`watchdog.py` chỉ dùng thư viện chuẩn); `lint-imports` xanh |
| 6 | P3 | **ĐÓNG** | `runner.py:403-409`: `except PermanentError` nay ánh xạ `TRAINING_CANCELLED` → `INTERNAL` khi lượt chưa có lý do dừng, kèm chú thích dẫn [2]. Có test mới `test_run_training_job_maps_a_trainer_claimed_cancel_to_internal` ghim cả ba điều: `error_code == INTERNAL`, log `training_failed` mang `INTERNAL`, **không** `put` trọng số |
| 7 | P3 | **ĐÓNG** | `test_main_ignores_override_outside_test_env` đổi `assert code in {0, 1}` thành `assert code == 0` **và** thêm `assert "training_trainer_override_ignored" in stderr` + không có object trọng số — đúng đề xuất "so dòng log", nay phân biệt được "override bị bỏ qua" với "override được nạp" |
| 8 | P3 | **ĐÓNG** | Docstring module `test_runtime.py` viết lại hẳn: bốn tầng test và dịch vụ thật của từng tầng, không còn câu tả trạng thái nhánh trước khi gộp |
| 9 | Nit | **ĐÓNG, có lý do đứng được** | `_wait(predicate: Callable[[], object])`, bỏ `# type: ignore[operator]`. Khác đề xuất (`Callable[[], bool]`) nhưng **đúng hơn**: nơi gọi truyền hàm trả danh sách thông điệp và điều kiện là "đã không rỗng"; khai `bool` sẽ buộc bọc `bool(...)` ở mọi nơi gọi. Docstring nói rõ lý do |
| 10 | Nit | không phải sửa | Lượt 1 đã ghi nhận, không đổi |

**Điều kiện `APPROVE` của lượt 1:** (1) bắt buộc P1 — đạt, kèm đúng hai bằng chứng được đòi; (2) bắt buộc P2 —
finding 2 và 3 **sửa thật** chứ không ghi nợ; (3) finding 4-8 và hai Nit — sửa hết dù không bắt buộc. Đủ cả ba.

## Finding mới của vòng sửa, và delta `cc6a333..91ff59a`

| # | Mức | ID | Mô tả | Trạng thái sau delta |
|---|---|---|---|---|
| M1 | P3 | TEST-02 | Việc tách `return … if … else …` thành `if` thật **làm lộ** một nhánh chưa có test: `self._stopped(reason)` khi `PermanentError` nổ lúc lượt **đã** có lý do dừng (`runner.py:406`, trong danh sách thiếu ở `pre-5.log:147`). Không phải hồi quy — là sự thật bị che trước đó — nhưng chính khối `except` mà finding 6 vừa sửa lại có một nửa không test | **ĐÓNG** ở `d3f20a8`: `test_run_training_job_lets_the_stop_reason_beat_a_trainer_error` đặt `_canceller` rồi một móc ném `PermanentError(TRAINING_METRICS_MISSING)` **sau** nó, và ghim `status == "cancelled"`, `error_code is None`. Đã truy để chắc test **thật sự** chạm dòng ấy chứ không đi đường khác: `TinyTrainer.train` chạy **hết** `on_epoch` rồi mới `_maybe_stop()` (`support.py`), nên móc thứ hai nổ trước khi trainer kịp tự ném `TrainingStopped`; còn `_canceller` ngủ `2 × training_cancel_poll_s` nên luồng đọc huỷ chắc chắn đã kịp bật `stop.reason` — cùng cơ chế ba test cũ (`__J04`, `_watchdog`, `…claimed_cancel…`) đã dựa vào, nên xác định chứ không bấp bênh |
| M2 | Nit | TEST-02 | `_runner_env(..., ml_device: str = "cpu")` dùng cho cả hai nơi gọi, nên `cancel_while_waiting` lặng lẽ đổi từ `ML_DEVICE="auto"` (bản cũ) sang `"cpu"`. Mọi khẳng định vẫn đỏ được nếu thứ tự [6] vỡ (`resolve_device`/`trainers`/`gpu_slot` đều bị vá thành `AssertionError`), nhưng `assert outcome["torch"] is False` yếu đi: ở `cpu` một runner hỏng vẫn có thể không nhập `torch`, còn ở `auto` thì quyết định thiết bị **buộc** phải nhập `torch` — đó đúng là điều test muốn ghim | **CÒN MỞ** — Nit, không chặn merge. Sửa: truyền `ml_device="auto"` ở nơi gọi của `cancel_while_waiting` (`test_runtime.py:304`); tham số đã có sẵn, một chữ |
| M3 | Nit | TEST-02 | Fixture khôi phục cache chỉ dọn **một chiều** (sau `yield`), nên vẫn hở chiều ngược: hai test của prompt khác đặt `ML_DEVICE=cuda` mà không xoá cache — `apps/ml/objects/tests/test_tasks.py:367`, `apps/ml/text/tests/test_tasks.py:310` — nếu cache đang nguội lúc chúng chạy thì `cuda` bị ghim và chảy **vào** `test_runtime.py` | **ĐÓNG** ở `91ff59a`, đúng đề xuất và rộng hơn: fixture chuyển sang `tests/support.py`, `reset_ml_settings_cache()` **trước và sau** `yield`, docstring nêu đúng hai nguồn rò tôi chỉ ra; `test_runner.py` và `test_runtime.py` nhập lại tên fixture (`# noqa: F401` có lý do) nên `autouse` phủ cả hai tệp — không tạo `conftest.py` lồng (CLAUDE.md cấm). Nguồn rò ở `apps/ml/objects`, `apps/ml/text` ngoài cột sở hữu của prompt (K27) nên điều phối ghi `NO-312`, đúng cách |
| M4 | Nit | TEST-02 | `tests/test_tasks.py` nhập `support` nhưng **không** nhập tên `ml_settings_cache`, nên hàng rào `autouse` không phủ tệp ấy. Rủi ro thấp (task mở tiến trình con nên cache của tiến trình pytest ít quyết định kết quả) nhưng nó là tệp thứ ba cùng module và cách sửa là một dòng | **CÒN MỞ** — Nit, không chặn merge. Sửa: thêm `ml_settings_cache` vào danh sách nhập của `test_tasks.py` |

Không có finding mới nào mức P0/P1/P2, ở cả `cc6a333` lẫn delta. Diff vòng sửa **không** gây lỗi mới ở mã sản phẩm:
ba thay đổi sản phẩm duy nhất (`reporter.join` có trần, hằng `JOIN_TIMEOUT_S` một nguồn, ánh xạ `TRAINING_CANCELLED`)
đều thu hẹp hành vi theo hướng an toàn hơn, không chạm đường thành công, và đều có test. Delta `cc6a333..91ff59a` chỉ
chạm tệp test; `support.py` nhập `pytest` và `apps.ml.runtime.settings` — đúng tầng (tệp dưới `tests/`), không vi phạm
ranh giới nhập nào, và không có mã sản phẩm nào nhập `tests.support`.

## Nợ nên ghi (`DEBT.md`; **không** ghi trong lượt review này — R-37, nhánh không chạm `DEBT.md`)

- `NO-<nnn>` (Nit, chủ B6-03b): M2 — `cancel_while_waiting` mất `ML_DEVICE=auto`, một chữ để trả lại.
- `NO-<nnn>` (Nit, chủ B6-03b): M4 — `tests/test_tasks.py` chưa nhập hàng rào `ml_settings_cache`.
- `NO-<nnn>` (Nit, chủ `apps/ml/runtime`): `apps/ml/runtime/gpu.py:32` vẫn giữ bản sao thứ ba của `JOIN_TIMEOUT_S = 5.0`;
  `training_runner` đã dồn về một nguồn, `runtime` thì chưa (R-07).
- `NO-312` (điều phối đã ghi): nguồn rò cache ở `apps/ml/objects/tests/test_tasks.py:367` và
  `apps/ml/text/tests/test_tasks.py:310`. Gốc rễ là `get_ml_settings` dùng `lru_cache` toàn tiến trình mà không có
  hàng rào `autouse` dùng chung — nên nhắc trong dòng nợ ấy.
- Nợ lượt 1 (`NO-305`, `NO-308`, `NO-309`, `NO-310`) đã có dòng trong `DEBT.md` trên `main`, không đổi.

## Điểm

| Miền | Trọng số | Lượt 1 | Lượt 2 | Tích | Vì sao đổi |
|---|---|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 5 | 1,25 | vòng sửa không chạm mặt tấn công |
| CON – Concurrency & dữ liệu | 15 % | 5 | 5 | 0,75 | không đổi |
| LOG – Tính đúng đắn | 15 % | 4 | **5** | 0,75 | finding 6 đóng, có test; thêm test cho nhánh "lý do dừng thắng" |
| PERF – Hiệu năng | 10 % | 5 | 5 | 0,50 | không đổi |
| RES – Chịu lỗi | 10 % | 4 | **5** | 0,50 | finding 5 đóng, hằng `JOIN_TIMEOUT_S` về một nguồn |
| DB, API – Migration & contract | 10 % | 5 | 5 | 0,50 | diff không chạm |
| TEST – Kiểm thử | 7 % | 1 | **4** | 0,28 | P1, P2 và M1, M3 đóng với đúng bằng chứng được đòi; chưa cho 5 vì M2 và M4 còn mở |
| OBS, OPS – Vận hành | 5 % | 4 | **5** | 0,25 | finding 8 đóng |
| MNT – Bảo trì | 3 % | 3 | **5** | 0,15 | finding 3 và 4 đóng |
| **Tổng** | **100 %** | **4,36** | | **4,93 / 5** | |

## PHÁN QUYẾT: APPROVE WITH COMMENTS (4,93/5)

Chín finding của lượt 1 đều đã đóng, tám trong chín đóng **đúng** đề xuất chứ không bằng một dòng nợ; cái thứ chín
(Nit 9) lệch đề xuất nhưng lệch theo hướng đúng hơn và có lý do viết rõ trong mã. Lỗi chặn merge duy nhất của lượt 1
— bộ test tự làm bẩn `lru_cache` của `get_ml_settings` — được sửa đúng chỗ và chứng minh bằng đúng hai bằng chứng
lượt 1 đòi: lệnh đích `-p no:randomly` nay **6 passed, EXIT=0** trên `91ff59a` (lượt 1 cùng lệnh: 1 failed), và
`pytest -n 6 -m "not perf" apps/ml` xanh **hai lượt liên tiếp**. Hai P2 cũng sửa thật: thư mục tạm riêng cho từng
lượt (đã truy tới `runner.py:86` và `:242` để chắc bản vá có hiệu lực, và các khẳng định `_tmp_dirs` vẫn chạy trong
tiến trình nên không mất răng), và hai hàm test quá dài tách thành bốn test cộng một bàn thử giữ đủ cả năm kịch bản.
Bốn finding tôi nêu mới đều P3/Nit; hai cái đáng nhất (M1 — một nửa khối `except PermanentError` chưa test; M3 —
hàng rào cache một chiều) đã được đóng ngay trong lượt này ở `d3f20a8` và `91ff59a`, và tôi đã truy đủ để tin rằng
test của M1 thật sự chạm dòng ấy chứ không đi đường khác. Hai cái còn mở (M2, M4) mỗi cái sửa một chữ, không chặn
merge và nên thành hai dòng nợ.

**Điều kiện duy nhất còn lại trước khi gộp:** `run.sh verify` đầy đủ trên `91ff59a` (cổng 3) phải có mã thoát 0 —
bảng trên ghi rõ bước ấy **chưa chạy** lúc viết, và E.10 cấm báo "đạt" cho bước chưa chạy. Phần rủi ro còn lại đã
khoanh được: `pre-5.log` chứng minh **bước 1-4** xanh trên `cc6a333` (chuỗi `set -euo pipefail` chạy tới cuối) và
delta sau đó chỉ thêm một test cùng một fixture; bước 5 xanh trên phạm vi `apps/ml` ba lượt khác nhau (tuần tự,
`--dist loadfile`, `-n 6` ×2) với độ phủ module 98,6 % dòng / 94,0 % nhánh; bước 5b được soát bằng `preflight.py`
trên sha này và `cases.toml` không đổi; còn bước 6, 7, 8 (migration, hợp đồng, openapi) **không thể** đổi kết quả so
với cổng 2 xanh trên `93eab65`, vì toàn bộ diff nằm trong `apps/ml/training_runner/**` và không có revision, route
hay lược đồ nào. Nếu cổng 3 đỏ vì một lý do ngoài ba điều đó thì phán quyết này không còn áp dụng và phải mở lượt 3.

Bốn dòng nợ ở mục trên nên vào `DEBT.md` — **không** sửa trong lượt này, và không cái nào chặn merge.
