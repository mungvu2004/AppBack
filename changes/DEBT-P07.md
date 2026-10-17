# DEBT-P07 — N9/N10 đếm độ dài mật khẩu mới sau NFC (BUG-P07-015, NO-423)

- `apps/api/auth/passwords.py`: kiểu dùng chung `NewPassword = Annotated[str, BeforeValidator(nfc), Field(min_length=MIN_PASSWORD_LENGTH)]`
  cạnh `MIN_PASSWORD_LENGTH`.
- `apps/api/auth_recovery/router.py`: `PasswordResetConfirmBody.new_password` (N9) và `AcceptInvitationBody.password` (N10) dùng
  `NewPassword`. `"ê"*4` dạng NFD (8 điểm mã, 4 ký tự) → 422 `VALIDATION` `field:"newPassword"` / `field:"password"`, như N13 (BUG-P07-014).
- Test mới `test_auth_confirm_password_reset__C02_nfd_length`, `test_auth_accept_invitation__C02_nfd_length`: đỏ trên main (2 failed),
  xanh sau sửa; `apps/api/auth`, `apps/api/auth_recovery`, `apps/api/me` 343 xanh; ruff, mypy sạch.
- Không endpoint, không bảng, không migration, không đổi dây (vẫn 422 `VALIDATION`): bước 6, 7, 8 không có gì mới.
