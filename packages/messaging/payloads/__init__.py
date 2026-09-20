"""Payload task của từng module: `packages/messaging/payloads/<module>.py`.

Đặt ở đây chứ không ở module chủ vì cả bên gửi (`apps/api`) và bên chạy
(`apps/worker`, `apps/ml`) đều phải thấy cùng một schema, trong khi hai bên không
được nhập mã của nhau (BE-00 §2.1). Mọi lớp kế thừa
`packages.messaging.tasks.TaskPayload` và khai `schema_version`.
"""
