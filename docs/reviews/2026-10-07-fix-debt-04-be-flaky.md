# Review merge fix/debt-04-be-flaky → main

- Ngày: 2026-10-07 · Reviewer: phiên /merge-review riêng (R-37), không phải tác giả · Commit đầu nhánh: `1f889330ebb0`
- Phạm vi: DEBT-04 cụm B, gồm NO-403 (FIX-491, B5-01) và NO-404 (FIX-492, B5-06c).
  - So với base `2ee6e7e`. `main` @ `2892033` chỉ thêm một commit sửa `DEBT.md`.
  - 6 commit, 7 tệp, +68/−20. Chỉ đổi tệp test và `changes/DEBT-04.md`.
  - `git status --porcelain` rỗng.
- Cổng: phạm vi **đích**.
  - Lý do: đã có lượt đầy đủ trên `420dc78`. `run.sh verify` mã thoát **0** (8411 passed, bước 0–8 đạt). Log ở `.cache/src-out/verify/20261007T062034Z-420dc7893b87.log` **của worktree** (không nằm dưới `F:/App/AppBack/.cache`), trùng với bản `B/verify.log`.
  - Delta `420dc78..1f88933` (372a0ba, 1f88933) chỉ chạm `apps/ml/runtime/tests/*`, không chạm điều kiện (2)–(7) của R-33b. Người gọi cũng cấm chạy lại lượt đầy đủ.
  - Kiểm đích, chạy tại chỗ `run.sh shell < rv.sh` trên `1f88933`, trước đó đã kiểm `docker ps | grep appback-verify` rỗng:
    - `ruff format --check` 0, `ruff check` 0, `mypy` 0 (24 tệp) trên `apps/ml/runtime/tests` và `apps/worker/pipeline_steps/tests`;
    - pytest `-n 4` sáu tệp test đổi/liên quan: 61 passed, rc 0;
    - `-m perf test_sweep_rules.py`: 1 passed, rc 0.
- Độ phủ: không đo (phạm vi đích). File đổi đều là tệp test, mà `pyproject.toml:117` đặt `omit = ["*/tests/*"]`, nên không thuộc tập đo. Lượt đầy đủ @420dc78 có `coverage_gate: đạt`.

## Kiểm điều kiện dừng sớm
Không điều kiện nào khớp:
- Cây sạch.
- Có `changes/DEBT-04.md`.
- 6 commit đúng mẫu, dòng đầu ≤ 72 ký tự.
- Trailer `Prompt:` đủ: B5-01 / B5-06c / DEBT-04, kèm `Fix:` và `Debt-Prompt: DEBT-04`.
- Mỗi commit chỉ chạm tệp của một chủ (K27).
- Không đụng tệp cấm.
- `git diff 2ee6e7e...HEAD | grep -E '^\+.*(TODO|FIXME|ponytail:|skip|xfail|noqa|pragma|type: ignore|sleep|retries|rerun)'` rỗng (rc 1).

## Đột biến và tải — reviewer tự chạy (không dùng số của tác giả)
| # | Đột biến / tải (bản chép `/tmp/w`, HEAD `1f88933`) | Kết quả |
|---|---|---|
| RM2 | `lease._acquire`: `if token is not None:` → `if True:` (lấy dù bận) | `m04_contention`, `test_held_lease__second_process_waits_for_first` **đỏ** (rc 1) |
| RM6 | `held_lease` không trả khoá (`ops.release_quietly(token)` → `pass`) | hai test trên **đỏ** (rc 1). Trên base (TTL 600) khoá tự hết hạn nên đột biến này lọt qua hai test đó. **Bản sửa làm test mạnh hơn.** |
| RM4 | `sweep.LLEN_TIMEOUT_S = 1e-6` | `test_sweep_resends_remaining_families_when_walls_used` **đỏ** (×30 vẫn ≈ 0) |
| RM7 | `sweep.LLEN_TIMEOUT_S = 20.0` (nới trần sản xuất) | `test_sweep_hang_returns_within_budget` **đỏ**. `REAL_LLEN_TIMEOUT_S` chụp đúng hằng thật nên trần sản xuất vẫn được kiểm. |
| L1 | tải `REP=10 HOGS=40` (plugin `B/rep.py`): contention + held_lease | 19 passed, **1 failed** (`m04_contention[1]`), không ghi được lý do (xem #3) |
| L1b | lặp lại L1 | 20 passed (rc 0) |
| L3 | contention `REP=10 HOGS=40` | 10 passed (rc 0) |
| L2 | `m04_renew` + `m04_lost` `REP=10 HOGS=40` (2400/600) | 20 passed (rc 0) |

## Trả lời ba trọng tâm

**(1) Nới TTL và nhân trần ×30: đây là sửa gốc, không phải che chập chờn.**

NO-403, thời hạn TTL/renew:
- Test hỏng vì một tham số chỉ có trong test: TTL 600 ms chỉ chịu được ≈ 450 ms nghẽn.
- Mã sản xuất dùng mặc định 60 000/20 000 (`gpu.py:102`). Mất khoá khi bị nghẽn quá `ttl − renew` là hành vi fail-closed có chủ ý (`lease.py:134-147`), không phải lỗi.
- Người giữ khoá trong test tranh chấp nay dùng đúng thời hạn sản xuất. Test vẫn kiểm độc quyền:
  - không assert nào đổi;
  - không thêm retry hay sleep. `m04_renew` vẫn ngủ 2,5 TTL như trước, chỉ đổi giá trị;
  - RM2 đỏ;
  - test còn bắt thêm được một lỗi trước đây lọt qua (RM6).
- Gia hạn vẫn được kiểm ở `m04_renew`/`m04_lost` với 2400/600: RM1 của tác giả đỏ, và L2 20/20 dưới tải.
- Khối [9] cấm "nới assert, hạ ngưỡng, retries, sleep". Thay đổi này không thuộc loại nào trong đó. `B/spec.md` cho phép sửa thời hạn của fixture nếu chứng minh bằng đột biến, và điều kiện đó đã đạt.

NO-404, trần `LLEN`:
- Vá `LLEN_TIMEOUT_S` trong `clean_queues` (`apps/worker/pipeline_steps/tests/helpers.py:331`) tách được test **luật** khỏi trần đồng hồ tường.
- Trần thật vẫn được kiểm: hai test hàng treo và test perf ghim lại hằng chụp lúc nạp module (`test_sweep_rules.py:280-281`). RM4 và RM7 đều đỏ.
- Không có cơ chế che nào.
- Giới hạn, đã nêu ở `mutation.md`: hạ hằng xuống 0,1 s thì không test nào bắt. Trước khi sửa cũng vậy, nên không phải hồi quy.

**(2) Lệch số chốt B5-01 [8] (`B5-01.md:128`, 600/150): chấp nhận được.**
- Con số ở [8] là tham số test, không phải hợp đồng.
- Bất biến của [8] được giữ: tỉ lệ 4:1, `renew × 2 < ttl` (`check_timing`), và `m04_renew` vẫn giữ khoá quá 2,5 TTL.
- Lý do lệch dựa trên số đo: base đỏ 8/20 dưới HOGS=40 (`repro-base-raw.log`).
- Lệch đã ghi ở docstring hằng và ở "Lệch khỏi prompt".
- Còn thiếu: dấu vết chấp thuận câu hỏi 1 trong `B/hoi.md` (xem Nit #6).

**(3) Dòng NO-404: không nên ✅, cũng không nên ➖. Nên giữ mở (⬜, chuyển DEBT-05).**

Không có bằng chứng đỏ → xanh cho chính test của dòng nợ. Cùng mô hình HOGS=40 REP=20:
- base: 2/20 đỏ (`repro-base-raw.log`);
- nhánh: vẫn **2/20 đỏ** (`repro-fix-raw.log`).

Một trong hai lượt đỏ trên nhánh mang **đúng triệu chứng của dòng nợ**: `sweep_queue_unreadable` → hàng ML rỗng. Lý do của lượt đó là trần nối 2 s của client redis-py (`packages/messaging/redis.py:39`, `CONNECT_TIMEOUT_S = 2.0`). Như vậy:
- Nhân ×30 không nâng sức chịu lên 30 s. Trần bị chạm khi nối nguội chỉ dời từ 1 s (`wait_for`) sang 2 s (nối) và 5 s (đọc).
- Lượt đỏ thứ hai thuộc `packages/db/hooks.py:42` (`CALLBACK_TIMEOUT_S = 2.0`).

Vì sao không ➖: ➖ là "chấp nhận, không sửa", trong khi nợ này có bản sửa và phần dư còn sửa được (chủ đã biết). Vì sao không ✅: ✅ là "đã giải quyết", không đúng khi test còn đỏ cùng triệu chứng dưới mô hình tái hiện của chính tác giả.

Cách ghi sổ đề xuất:
- Giữ NO-404, sửa câu chữ gốc: "trần đồng hồ tường trên đường quét: `wait_for` 1 s (FIX-492 đã gỡ), nối Redis 2 s, callback sau commit 2 s".
- Ghi FIX-492 là phần đã làm.
- Phần còn lại giao chủ `packages/messaging` / `packages/db` ở DEBT-05.

Bản sửa vẫn đáng merge: nó gỡ trần chặt nhất và sửa rò client ở J10.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | R-35 (FIX.md luật 1) · TEST | NO-404 thiếu bằng chứng đỏ → xanh. Dưới cùng mô hình HOGS=40, base 2/20 đỏ, nhánh vẫn 2/20 đỏ. Một lượt mang đúng triệu chứng `sweep_queue_unreadable` → hàng rỗng, do trần nối 2 s. Khối [6] của `B/fix-492.md` ghi "base đỏ, nhánh xanh", trái với `B/tai-hien-NO-404.md` và `repro-fix-raw.log`. Docstring `clean_queues` ngụ ý sức chịu ×30, nhưng trần thật nay là trần nối 2 s và đọc 5 s của client. | `apps/worker/pipeline_steps/tests/helpers.py:323-331`; `B/fix-492.md` [6]; `B/bao-cao.md` bảng "Từng nợ" | Không đóng NO-404 ✅. Giữ ⬜ → DEBT-05 với câu chữ gốc đã sửa (xem trọng tâm 3). Sửa [6] của `fix-492.md` thành "đỏ 2/20 → 2/20, chữ ký `wait_for` không còn; phần dư do trần 2 s khác chủ" trước khi chép sang `docs/fixes.md`. Không cần sửa mã ở nhánh này. |
| 2 | P2 | R-34 · MNT | Năm mục "Nợ mới" trong `B/bao-cao.md` chưa có dòng nào trong `DEBT.md`: `main` @ `2892033` không có NO-405 trở đi. Năm mục: (a) câu chữ NO-404; (b) `packages/db/hooks.py:42` 2 s và `packages/messaging/redis.py:39` 2 s; (c) `apps/worker/pipeline_steps/jobs.py:37` rò client; (d) `apps/ml/training_runner/tests/test_runtime.py:390-400`, `test_slot.py:22-23` cùng bệnh NO-403; (e) worker xdist chết, torch không giới hạn luồng. | `DEBT.md` (thiếu dòng) | Điều phối ghi đủ năm dòng, đủ cột, **cùng lúc** đóng NO-403 khi merge. Mục (b) trỏ ngược NO-404. |
| 3 | P3 | TEST | Trên HEAD, dưới HOGS=40, `m04_contention` đỏ 1/30 lượt của reviewer (L1 9/10, L1b 10/10, L3 10/10). Lượt đỏ không giữ được traceback nên chưa rõ lý do. Với TTL 60 s, chữ ký NO-403 (`DID NOT RAISE` + `lease_lost`) chỉ xảy ra khi nghẽn > 40 s, nên khả năng cao là trần nối Redis 2 s (base của tác giả cũng có 1 lượt `Timeout connecting to server`). | `apps/ml/runtime/tests/test_device_gpu.py:87-114` | Không chặn. Khi đóng NO-403 ✅ thì ghi phần dư "1/30 dưới HOGS=40, lý do chưa rõ, nghi trần nối 2 s" và gộp theo dõi vào dòng mới (b) của #2. |
| 4 | P3 | R-07 · MNT | `HOLD_TTL_MS = 60_000`, `HOLD_RENEW_MS = 20_000` chép tay mặc định của `gpu_slot` (`gpu.py:102`). Docstring gọi đó là "thời hạn mặc định", nhưng nếu mặc định đổi thì hằng test lệch đi mà không ai hay. | `apps/ml/runtime/tests/helpers.py:29-30` | Bỏ hai hằng. Người giữ gọi `gpu_slot(wait_s=0)` để dùng mặc định thật; `_HOLDER` của `test_lease.py` bỏ `ttl_ms`/`renew_every_ms`. Làm ở DEBT-05 hoặc FIX kế của B5-01. |
| 5 | Nit | TEST | `test_held_lease__second_process_waits_for_first` không còn giữ khoá "qua nhiều TTL" ở tiến trình khác (docstring đã sửa đúng). Đột biến "không gia hạn" giờ chỉ còn `m04_renew`/`m04_lost` bắt. | `apps/ml/runtime/tests/test_lease.py:56-58` | Chấp nhận. Gia hạn là cùng mã trong và ngoài tiến trình, và RM1 của tác giả vẫn đỏ ở `m04_*`. |
| 6 | Nit | R-27 / quy trình | Lệch B5-01 [8] (600/150 → 2400/600 và 60 000/20 000) được tác giả tự chọn phương án A (`B/hoi.md` câu 1), chưa thấy dấu vết duyệt. | `apps/ml/runtime/tests/helpers.py:21-30` | Điều phối ghi "duyệt phương án A" vào FIX-491 khi chép sang `docs/fixes.md`. |
| 7 | Nit | OBS | `B/bao-cao.md` ghi đường log verify dưới `F:/App/AppBack/.cache/...`, nhưng tệp nằm ở `.cache` của worktree `debt04-b`. | `B/bao-cao.md` mục Cổng | Sửa đường khi chép sang `docs/fixes.md`, vì worktree bị dọn thì log mất; `B/verify.log` là bản giữ lại. |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 3 | 0,21 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 3 | 0,09 |

Tổng: 4,80 / 5

## PHÁN QUYẾT: APPROVE
Không có P0/P1, điểm 4,80 ≥ 4,0.

Mã của nhánh là sửa gốc, không che chập chờn:
- không assert nào đổi, không thêm retry/sleep/skip;
- trần sản xuất vẫn được kiểm (RM4, RM7 đỏ);
- test tranh chấp mạnh hơn trước (RM6 đỏ, trên base lọt qua);
- NO-403 có bằng chứng đỏ → xanh: base 8/20 đỏ; nhánh 20/20 (tác giả) và 29/30 (reviewer) dưới cùng mô hình tải.

Hai P2 thuộc phần sổ, không thuộc mã. Điều phối phải làm **khi merge**:
1. Đóng NO-403 ✅ FIX-491, kèm ghi chú phần dư (#3).
2. **Không** đóng NO-404 ✅. Giữ ⬜ → DEBT-05 với câu chữ gốc đã sửa, FIX-492 ghi là phần đã làm. Sửa khối [6] của `fix-492.md` (#1).
3. Ghi năm dòng "Nợ mới" vào `DEBT.md` (#2).

Merge thuộc phiên gọi. Reviewer không merge, không push.
