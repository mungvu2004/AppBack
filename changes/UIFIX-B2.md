# UIFIX-B2 — review UI/UX, gói backend B2 (G2-9, G2-10, G1-10)

- Thêm route công khai `POST /api/auth/invitations/preview` (`auth_preview_invitation`) trong `apps/api/auth_recovery/router.py`: xem trước lời mời trước khi điền form, chỉ đọc, không tiêu token.
- 200 trả `{status:"valid", email, role, inviterName?, expiresAt}`; `inviterName` lấy từ nhật ký `user.invite`/`user.invite_resend` mới nhất.
- Ba mã 422 riêng: `INVITATION_TOKEN_INVALID` (link sai/sai mục đích), `INVITATION_TOKEN_USED` (đã dùng hoặc người đã `active`), `INVITATION_TOKEN_EXPIRED` (quá hạn hoặc bị thay sau "Gửi lại"). Hai mã mới khai trong router.
- Cùng `require_origin` và hạn mức `recovery_ip` với N8/N9/N10. Token đi trong thân, không lên URL (K11).
- Test: `apps/api/auth_recovery/tests/test_router_preview_invitation.py` (13 test).
- Cần điều phối: thêm dòng BE-BIND (case C) cho `auth_preview_invitation`, HOP-DONG-MOI và `openapi.json`; nếu không `core/tests/test_routes.py::test_public_routes_are_allowed` đỏ.
