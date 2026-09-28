"""Ghi lớp không gian một tầng có kiểm version (B3-03): #35, `write_layer` cho B5-06b và B3-04.

Đọc và giải mã tài liệu là việc của `apps.api.spatial_read`; ở đây chỉ có đường **ghi**:
kiểm lớp ứng viên, giải quyết đua bằng `revision` (W20, C09b), đổi tỉ lệ cho mục chưa
duyệt, nhận id thực thể, ghi nhật ký theo trường và bảng đếm.
"""
