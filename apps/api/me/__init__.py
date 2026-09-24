"""`apps/api/me` — hồ sơ, mật khẩu, ảnh đại diện của chính người dùng (B1-04).

Chỉ docstring: `jobs.py` của module này bị `apps/worker` nhập, và không được kéo theo
`fastapi`/`jwt`/`argon2` qua việc nhập gói cha (BE-00 §7 "Hàm worker nhập").
"""
