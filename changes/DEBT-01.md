# DEBT-01 — Trả nợ kỹ thuật đợt 1 (NO-050 … NO-164)

- Không op mới, không revision mới, không seed mới: cổng case/golden (bước 5b, 8) và migration (bước 6) chỉ chạy lại cho mã có sẵn.
- Mỗi nhánh mang một hay nhiều FIX (FIX-083 … FIX-099, `docs/fixes.md`), mỗi chủ file một commit `fix(<scope>): …` + trailer `Prompt:`/`Fix:`.
- `fix/debt-01-tooling`: `tools/verify`, `tools/ci`, `.github`, `pyproject.toml` (NO-130 đổi `concurrency` của coverage), `deploy/compose/verify.yml`, `uv.lock` (ghim `redis`).
- `fix/debt-01-deploy`, `fix/b0-08-web-openssl-cve`: chỉ `deploy/**`; test tĩnh quét YAML/template nginx/compose thay cho test hành vi.
- `fix/debt-01-core`, `fix/debt-01-modules`: mã Python của nhiều chủ; mọi FIX có test đỏ trên `main` trước khi sửa (FIX.md luật 1).
- `fix/debt-01-fe` ở AppFront: cổng `pnpm verify`, không qua `run.sh`.
