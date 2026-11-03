# BENCH3D-20 — bỏ vùng phụ xiên trục, không nối tường giữa hai căn

- `apps/worker/pipeline_build/geometry.py` `_drop_far_clusters`: vùng phụ có `axis_share` (±4° quanh hướng trội của chính vùng) < 0,6 bị bỏ cả vùng (phối cảnh/sơ đồ vị trí in cùng tờ); vùng chứa cụm dài nhất luôn giữ.
- `_join_gaps` chỉ nối cặp tường cùng vùng (vùng tính trước bước nối, cùng chuỗi với `_multiple_plans`); `close_envelope_gaps` không dựng đoạn khép có hai đầu thuộc hai vùng → tờ 2 căn ra `MULTIPLE_PLANS`.
- `clusters.py`: `region_labels` (STRtree), `axis_share` cửa sổ trượt O(n log n).
- Replay bench-3d: bench 35→36 (nt-02), F 5→6 (f-26); W1 không đổi ca nào. Không đổi hợp đồng/openapi.
