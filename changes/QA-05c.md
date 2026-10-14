# QA-05c — nginx: 404 cho tệp thiếu dưới `/basis/` và `/pascal/`

- `deploy/nginx/snippets/app_locations.conf`: thêm `location /basis/` (bộ giải KTX2 của Pascal) và `location /pascal/`
  (vật liệu `.ktx2`, `NEXT_PUBLIC_ASSETS_CDN_URL="/pascal"`) theo luật `/draco/`: `security_headers.conf` +
  `try_files $uri =404`; `/pascal/` thêm `Cache-Control: public, max-age=86400` (tên không băm). Trước đó tệp thiếu rơi
  xuống `location /` và trả `index.html` 200 (hàng catalog B05-G-145, B05-G-146).
- `deploy/tests/test_nginx.py`: test mới `test_nginx_pascal_static_prefixes_return_404_when_missing`, tách hàm kiểm chung
  với test `/draco/`, `/assets/` (giờ kiểm cả `security_headers.conf`).
- Không đổi mã Python của app, route, schema, migration, openapi — bước 6, 7, 8 không có gì mới để kiểm.
