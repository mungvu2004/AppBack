# Review merge `feature/b2-05a-preprocess-quality` → main — lượt 2

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` (worktree riêng `b2-05a-review2`, tách ở sha chấm)
- Commit đầu nhánh: `f33e6bab2610` — `docs(vision): add missing docstrings`
- Lượt 1: `docs/reviews/2026-09-23-feature-b2-05a-preprocess-quality.md` — `REQUEST CHANGES` ở
  `a927fdd1785e`, 4,34/5, chặn vì **một** P1.
- Phạm vi soát kỹ của lượt này: `git diff a927fdd...f33e6ba` = **15 file**, +124 / −13 dòng, toàn
  bộ trong `packages/vision/{preprocess,quality}/`. Điểm ở mục 6 chấm lại **cả nhánh** sau vòng sửa
  (`git diff main...HEAD` = 27 file, ≈ 1.440 dòng mã nguồn + ≈ 2.054 dòng test).
- Cổng: `bash tools/verify/run.sh verify` chạy tại chỗ trong phiên này, **mã thoát 0**
  (container `appback-verify-b2-05a-review2-verify-run-…`, log giữ bằng `docker logs -f`).
- Độ phủ (số của chính lượt chạy này): tổng dòng **99,12 %** · nhánh **97,49 %**;
  `packages/vision` dòng **100,00 %** · nhánh **100,00 %**; tập file bị chạm **100 % / 100 %**.

## 1. Bảng cổng E.10 — lấy từ mã thoát thật của phiên review

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt (439 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (341 file) |
| 4 | `lint-imports` | đạt (9 hợp đồng giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 3 test) |
| 6 | `lint_migrations` → `migrate_check` | đạt (5 revision, 10 mục) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt (H4, H5 `không áp dụng` — B3-05/B4-01 chưa hợp nhất) |
| 8 | `openapi` | đạt |

Bước 5: **2789 qua · 10 bỏ qua · 4 bị loại** trong 372,81 s. Bước 5b: **3 test perf qua** trong
36,80 s. Khớp đúng con số tác giả báo.

**10 "bỏ qua" đã tự truy lại trong log lượt này**, không thuộc diff: cả 10 nằm ở đúng một dòng
`apps/api/core/tests/test_common.py ssssssssss [63%]` — tập tham số rỗng của `_protected()` /
`_idempotent()` vì B3-05/B4-01 chưa hợp nhất, đúng ngoại lệ BE-00 §12. Diff vòng sửa **không** thêm
`skip`/`xfail`/`pragma: no cover`/`noqa` trần nào (grep toàn `packages/vision`: 0 `pragma`, 0 `skip`,
0 `xfail`; hai `# noqa: S603` duy nhất ở `quality/tests/test_boundary.py:42,66` đã có lý do và có từ
lượt 1).

## 2. Kiểm từng finding của lượt 1

### Finding 1 — [P1] NO-121 `PdfiumError` lọt khỏi gói → **ĐÃ SỬA, sửa ở gốc**

Cách sửa: một context manager dùng chung `_open_page` (`packages/vision/preprocess/pdf.py:63-80`)
thay hai khối `try/finally` trùng nhau ở `_page_size_pt` và `_render_page` (R-07 + R-19 — một chỗ
sửa cho cả hai đường, không vá riêng dòng tái hiện được).

Đối chiếu từng đòi hỏi của lượt 1:

| Đòi hỏi | Kết quả |
|---|---|
| Bao **trọn** `pdf[i]`, `get_size`, `render`, `to_numpy` | **Đạt.** `try` bọc cả `pdf[page_index]` **và** `yield`, nên ngoại lệ ném từ thân `with` được `gen.throw()` đưa về đúng điểm `yield` rồi rơi vào `except` (`pdf.py:73-80`). Hai chỗ gọi đều đặt **mọi** lời gọi pdfium trong thân `with`: `page.get_size()` (`:91`), `page.render(...)` + `bitmap.to_numpy()` (`:128-129`) |
| `raise … from` | **Đạt** (`pdf.py:80`) — đã chốt bằng `__cause__` trong phép tái hiện dưới đây |
| Đóng trang trong `finally` | **Đạt** (`pdf.py:77-78`), và `finally` nằm **trong** `try` ngoài nên trang vẫn đóng trước khi đổi lỗi |
| Dưới `PDF_LOCK` | **Đạt.** Cả ba hàm công khai mở khoá trước `_open_document` và nhả sau `pdf.close()` trong `finally` (`:55`, `:100-105`, `:145-152`); `_open_page` chỉ được gọi từ `_page_size_pt`/`_render_page`, cả hai chỉ chạy bên trong khoá |
| Không `except Exception` | **Đạt.** `grep -rnE "except (Exception\|BaseException)\|except:" packages/vision/` → 0 kết quả |
| Test U07 mới chốt đúng | **Đạt** (xem dưới) |

**Tự tái hiện trong container verify của phiên này** (không dùng test của tác giả):

```
== 1. trang hỏng: /Type/Page → /Type/Bad ở trang cuối của PDF 3 trang ==
  pdf_page_count(data)      : ok(3)
  pdf_page_size_pt(data, 2) : VisionError(FILE_CORRUPT) cause=PdfiumError
  render_pdf_page(data, 2)  : VisionError(FILE_CORRUPT) cause=PdfiumError
  pdf_page_size_pt(data, 0) : ok((595.0, 842.0))        <- trang lành không bị vạ lây
  render_pdf_page(data, 0)  : ok(RgbImage(...))

== 2. đường THÂN `with` (monkeypatch để ném PdfiumError giữa chừng) ==
  PdfPage.get_size    ném PdfiumError -> VisionError(FILE_CORRUPT) cause=PdfiumError
  PdfPage.render      ném PdfiumError -> VisionError(FILE_CORRUPT) cause=PdfiumError
  PdfBitmap.to_numpy  ném PdfiumError -> VisionError(FILE_CORRUPT) cause=PdfiumError

== 3. các đầu vào xấu khác ==
  rỗng / rác 512B : FILE_TYPE_MISMATCH (chặn ở sniff, chưa tới pdfium)
  cụt 50 %        : FILE_CORRUPT cause=PdfiumError
  chỉ %PDF-1.7    : FILE_CORRUPT cause=PdfiumError
  xref hỏng       : ok — pdfium dựng lại được bảng xref, không phải lỗi
```

Mục 2 là bằng chứng mà **test của tác giả chưa có**: ca U07 mới chỉ chạm đường *mở trang*
(`FPDF_LoadPage` trả NULL). Đường *thân* `with` chỉ được chứng minh ở đây, bằng monkeypatch ngoài
bộ test — xem Nit 2. Đường thân là thật, không phải giả định: `pypdfium2/_helpers/bitmap.py:88`
ném `PdfiumError("Failed to get bitmap buffer (null pointer returned)")` và `_helpers/page.py:85`
ném `PdfiumError("Failed to get page rotation.")`, cả hai nằm sau khi `FPDF_LoadPage` đã thành công.

**Không còn đường nào khác trong `pdf.py` để `PdfiumError` lọt.** Ba lời gọi pdfium ngoài
`_open_page` là `pdfium.PdfDocument(data)` (đã bắt từ lượt 1, `:46-50`), `len(pdf)` (`:58`, `:88` —
`FPDF_GetPageCount` trả thẳng `int`, không ném) và `pdf.close()` trong `finally` (`AutoCloseable`,
không ném `PdfiumError`). Không module nào khác của `packages/vision` nhập `pypdfium2`.

**Test U07 mới có chốt đúng.** `test_pdf.py:149-186`:

- `_pdf_with_broken_last_page` thay `/Type/Page/Parent` → `/Type/Bad /Parent` bằng `rpartition`
  (đúng trang **cuối**), có `assert len(old) == len(new)` giữ offset `xref` và `assert sep` để test
  gãy to nếu `synthetic.make_pdf` đổi cách sinh — không phải "hoặc ok hoặc lỗi".
- Chốt `pdf_page_count == 3` **rồi** mới chốt `FILE_CORRUPT` cho cả `render_pdf_page` và
  `pdf_page_size_pt` (`_INDEXED_CALLS`) — đúng yêu cầu "chạy qua cả ba hàm công khai".
- Test thứ hai chốt trang 0 vẫn đọc khổ và dựng được: chứng minh bản sửa không biến cả tài liệu
  thành hỏng, tức không vá bằng cách nới lỗi ra.

### Finding 2 — [P2] NO-122 thiếu docstring → **ĐÃ SỬA**

Tự quét AST (module + `ClassDef` + `FunctionDef` + `AsyncFunctionDef`) trên **27 file**
`packages/vision`: **0 thiếu docstring** (`test_perf.py` dùng cú pháp generic PEP 695 nên phải quét
riêng, cũng 0 thiếu). Lượt 1 đếm 48 hàm thiếu; diff vòng sửa thêm đúng nhóm đó, gồm cả 6
`__post_init__`/`__init__` ở `types.py:38,71,105`, `errors.py:32`, `assess.py:64`, `metrics.py:39`.

**R-02 (docstring không kể lại code): đạt.** Đọc cả 2 file mã nguồn và 5 file test được thêm
docstring: các câu nói **bất biến được giữ và lỗi được ném** chứ không đọc lại lệnh —
`errors.py:32` ("mã lạ → `ValueError` vì gõ sai mã là lỗi lập trình, không phải lỗi dữ liệu vào cần
trả 422"), `metrics.py:39` ("vùng tràn sẽ vẽ ra ngoài ảnh ở FE"), `assess.py:64` ("người giữ
`Finding` không đổi được con số mà FE sẽ hiện"). Docstring test nói **vì sao ca đó tồn tại**:
`test_classify_skew__poor_at_exact_attention_threshold` ghi "biên 5 độ dùng `<` chứ không `<=`
(`thresholds.ts:162-170`)" — trỏ thẳng về nguồn hợp đồng, đúng kiểu docstring R-02 muốn. Không câu
nào thuộc loại "hàm này trả về X" nhắc lại `return X`.

### Nit 4 lượt 1 — 5 `# type: ignore[...]` thiếu lý do → **ĐÃ SỬA**

`grep -rn "type: ignore" packages/vision/` trả **7 dòng, cả 7 đều có mã lỗi và lý do**: 2 dòng
`pdf.py:16-17` (có từ lượt 1) và đúng 5 dòng lượt 1 nêu (`test_errors.py:37`,
`test_geometry.py:121`, `test_types.py:71,96`, `test_assess.py:236`). Không xuất hiện
`# type: ignore` trần nào mới.

### Finding 3 lượt 1 — [P2 → P3] MNT-05 nhánh > 400 dòng → **giữ nguyên, chấp nhận**

`NO-123` trên `main` đã ghi ➖ với lý do đứng được (khối [10] định nghĩa đúng một đơn vị bàn giao;
đường nâng cấp: tách theo gói nếu vượt 800 dòng). Không phải nợ mở.

### Nit 5 lượt 1 — test nhập `_bbox_region` → **giữ nguyên**, vẫn chỉ là Nit.

## 3. Diff vòng sửa có thêm hành vi ngoài phạm vi không? — Không

Lọc diff bỏ dòng docstring/comment còn đúng ba nhóm thay đổi: (a) `import Iterator`/`contextmanager`
+ `_open_page`, (b) hai khối `try/finally` đổi thành `with _open_page(...)`, (c) hai hàm test U07
mới + helper. 13 dòng bị xoá đều là hai khối `try/finally` cũ và hai đuôi `# type: ignore` không lý
do. Không hằng số, ngưỡng, chữ ký hàm hay `__all__` nào đổi — `__all__` của hai gói không nằm trong
diff. Không tệp nhị phân, không file cấm (`docs/charter/*`, `openapi.json`, `uv.lock`,
`APPFRONT_SHA`, `pyproject.toml` gốc đều ngoài diff).

Hành vi **mới** duy nhất ngoài đường lỗi: `_open_page` nay cũng đổi `PdfiumError` ném từ
`page.close()` thành `FILE_CORRUPT`. Vô hại (`AutoCloseable.close` không ném `PdfiumError`), ghi lại
cho đủ.

## 4. Chấm lại các miền sau vòng sửa

Những gì lượt 1 đã kiểm và đạt (K13/U03/U06 trần điểm ảnh, homography có phép co, K14 `sniff`,
`PDF_LOCK` 8 luồng, cấm tuyệt đối khối [9], R-07 `sniff` trùng là cố ý, `test_perf` đo thật ở 40 MP)
**không bị diff vòng sửa chạm tới** — 13 trong 15 file chỉ thêm docstring. Phần tự kiểm lại trong
lượt này:

- **Gương ngưỡng FE.** Đối chiếu lại `packages/vision/quality/thresholds.py` với
  `F:/AppFront/src/domain/quality/thresholds.ts`: tám hằng khớp (2000, 1200, 0.5, 5, 0.75, 0.45,
  0.2, 0.4) và **bốn chiều toán tử khớp từng cái** — `>=`/`>=` (resolution), `<=`/`<` (skew, chiều
  ngược ba thang kia), `>=`/`>=` (contrast), `<=`/`<=` (noise). `worst_level([]) == "good"` như
  `worstLevel`.
- **R-08.** Quét AST lại toàn `packages/vision`: 0 hàm > 50 dòng, 0 hàm cyclomatic > 10.
- **Không nhập `packages.testing` từ mã không phải test**, không `getenv`/`environ`/`urllib`/
  `requests`/`socket`; hai chỗ `open(` duy nhất là `Image.open` của Pillow, không phải hệ tệp.
- **Cây sạch** (`git status --porcelain` rỗng). **Hai commit vòng sửa đúng mẫu**: dòng đầu
  `fix(vision): map broken pdf pages to file corrupt` (46 ký tự) và
  `docs(vision): add missing docstrings` (36 ký tự), thân có một dòng trống rồi khối trailer liền
  nhau `Prompt: B2-05a` + `Co-Authored-By:` (R-36b). `changes/B2-05a.md` có mặt và vẫn đúng các bước
  `không áp dụng` mà cổng đọc.

## 5. Finding mới của lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG-04 / OBS-02 | `_open_page` đổi **mọi** `PdfiumError` ở đường trang thành `FILE_CORRUPT` (422), kể cả lỗi không phải tệp hỏng: `bitmap.py:88` "Failed to get bitmap buffer (null pointer returned)" và `page.py:85` "Failed to get page rotation." đều ném sau khi `FPDF_LoadPage` đã thành công. Gói không có log, nên một lần cấp phát bitmap thất bại ở sát trần 40 MP bị đếm **lặng lẽ** thành lỗi dữ liệu người dùng trong quan trắc thay vì sự cố tài nguyên | `packages/vision/preprocess/pdf.py:79-80` | Không chặn merge: `err_code` của nhánh này là `None` nên **không có gì để phân loại**, và fail-closed 422 vẫn an toàn hơn 500. Đường nâng cấp: người gọi (W7/B2-04) log `exc.__cause__` ở mức `warning` khi bắt `FILE_CORRUPT` từ đường PDF, để sự cố tài nguyên không biến mất |
| 2 | Nit | TEST / R-23 | Đường **thân** `with` của `_open_page` (`get_size`/`render`/`to_numpy` ném `PdfiumError`) không có test nào chốt — ca U07 mới chỉ chạm đường *mở trang*. Độ phủ 100 % không phát hiện được: dòng `except` đã được ca mở trang phủ. Phải monkeypatch ngoài bộ test mới chứng minh được (mục 2 ở trên) | `packages/vision/preprocess/tests/test_pdf.py:163-186` | Một ca `monkeypatch.setattr(pdfium.PdfPage, "render", …)` ném `PdfiumError`, chốt `FILE_CORRUPT` — khoá lại phần "bao trọn" của bản sửa, để lần refactor sau không lặng lẽ thu `try` về mỗi dòng `pdf[i]` |
| 3 | Nit | MNT-04 | Dòng dài **132 ký tự**, vượt `line-length = 120` của chính repo. `ruff check` cho qua vì E501 miễn trừ phần đuôi pragma, nên cổng không bắt — nhưng đây là dòng duy nhất > 120 trong cả `packages/vision` | `packages/vision/preprocess/tests/test_geometry.py:121` | Đưa lý do lên một dòng `#` riêng phía trên, hoặc rút gọn còn "`factory` là `object` để bảng ca nhận mọi hàm dựng" |

Không finding P0/P1/P2 mới.

## 6. Điểm (chấm lại cả nhánh, `RULE.md` §5)

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,82 / 5** |

LOG = 4 (chỉ còn P3 finding 1; P1 lượt 1 đã đóng). MNT = 4 (MNT-05 P3 đã chấp nhận ở `NO-123`, cộng
Nit 3). TEST giữ 5: Nit 2 là ca còn thiếu của một hành vi đã được chứng minh là **đúng**, không phải
khiếm khuyết đúng đắn. OBS giữ 5: khiếm khuyết quan trắc ở finding 1 thuộc về người gọi, không
thuộc gói thuần này.

## 7. Sổ nợ — người điều phối ghi trên `main`

- `NO-121` (P1) → **đóng** ✅. Đã sửa ở gốc bằng `_open_page`, kiểm bằng phép tái hiện độc lập của
  phiên này, không chỉ bằng test của tác giả.
- `NO-122` (P2) → **đóng** ✅. Quét AST 27 file: 0 thiếu docstring; 7/7 `# type: ignore` có lý do.
- `NO-123` (P3) → giữ ➖ chấp nhận, không đổi.
- **Thêm một dòng P3 mới** cho finding 1 (phân loại `PdfiumError` đường trang gộp hết vào
  `FILE_CORRUPT`; chủ: người gọi W7/B2-04 log `__cause__`), và **một dòng P3** cho Nit 2 (thiếu ca
  monkeypatch khoá đường thân `with`). Nit 3 không cần dòng nợ.
- R-35/R-38: sau khi đóng `NO-121`/`NO-122`, nhánh **không còn nợ P0/P1 mở** nào.

## PHÁN QUYẾT: APPROVE

Vòng sửa làm đúng thứ được yêu cầu và không làm hơn. `NO-121` được sửa **ở gốc**: một context
manager dùng chung thay hai khối trùng nhau, bao trọn cả `pdf[i]` lẫn thân `with`, giữ `from exc` và
`finally` đóng trang — lỗi lượt 1 được tái hiện lại và nay trả `VisionError("FILE_CORRUPT")`, đồng
thời `PdfiumError` bắn thẳng từ `get_size`, `render` và `to_numpy` cũng bị đổi đúng, chốt rằng phần
"bao trọn" là thật chứ không phải chỉ vá đúng dòng tái hiện được. Trang lành trong cùng tài liệu vẫn
đọc và dựng bình thường, nên đây không phải kiểu sửa bằng cách nới lỗi ra. `NO-122` đóng sạch: 0/27
file thiếu docstring, và docstring viết theo R-02 — nói bất biến và lý do, có chỗ trỏ thẳng về
`thresholds.ts`, không đọc lại lệnh. Cổng tự chạy một lượt: **mã thoát 0**, 2789 qua / 10 bỏ qua
(cả 10 ở `apps/api/core/tests/test_common.py`, tập tham số rỗng, ngoài diff), 3 test perf,
`packages/vision` 100 % dòng **và** 100 % nhánh.

Không P0, không P1, không P2. Điểm 4,82/5 ≥ 4,0 → `APPROVE` theo ma trận `RULE.md` §5.

Ba finding còn lại đều không chặn: một P3 về **độ mịn của phép phân loại lỗi** (mọi `PdfiumError`
đường trang thành 422 — đúng chọn lựa fail-closed, nhưng một sự cố tài nguyên sẽ lặng lẽ bị đếm
thành lỗi dữ liệu vào; chữa ở người gọi, không ở gói này) và hai Nit (thiếu ca monkeypatch khoá
đường thân `with`; một dòng 132 ký tự mà E501 miễn trừ). Đề nghị người điều phối ghi hai dòng P3 ở
mục 7 vào `DEBT.md` **trước** khi merge (R-38), đóng `NO-121` và `NO-122`, rồi gộp squash vào `main`.
