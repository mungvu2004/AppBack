"""Tiện ích dùng chung của test `apps/api/auth_recovery` (không phải file test, pytest không thu thập).

Mẫu `apps/api/auth/tests/support.py` (NO-146/R-07) — gom `_seed_token`/`_seed_reset_token`/
`_seed_invite_token` từng bị chép gần nguyên văn giữa `test_tokens.py`, `test_jobs.py`,
`test_router_confirm_reset.py`, `test_router_accept_invitation.py`.
"""

import secrets
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth_recovery.tokens import derive_token, hash_token
from packages.core.clock import Clock
from packages.core.ids import new_id
from packages.core.keys import current_key
from packages.db.models.auth_recovery import NONCE_LEN, OneTimeToken, TokenPurpose


async def seed_token(
    db: AsyncSession,
    *,
    user_id: str,
    purpose: TokenPurpose,
    clock: Clock,
    ttl: timedelta = timedelta(hours=1),
    used_at: datetime | None = None,
    superseded_at: datetime | None = None,
    sent_at: datetime | None = None,
    created_at: datetime | None = None,
    commit: bool = True,
) -> tuple[OneTimeToken, str]:
    """Chèn thẳng một dòng token (không qua `issue_token`), trả dòng và token bản rõ.

    `created_at` để trống → cột tự lấy giá trị mặc định của DB (`func.now()`), không đi theo
    `clock`; chỉ set tường minh khi test cần một mốc xác định (cắt hạn `resend_unsent`). `commit=False`
    chỉ `flush()` — dùng khi lượt đọc lại xảy ra trên **cùng** session (test của `tokens.py`); mọi nơi
    khác cần một session/kết nối khác thấy được dữ liệu nên commit là mặc định.
    """
    token_id = new_id("tok", clock)
    nonce = secrets.token_bytes(NONCE_LEN)
    plain = derive_token(current_key("token"), token_id=token_id, purpose=purpose, nonce=nonce)
    row = OneTimeToken(
        id=token_id,
        user_id=user_id,
        purpose=purpose,
        token_hash=hash_token(plain),
        nonce=nonce,
        expires_at=clock.now() + ttl,
        used_at=used_at,
        superseded_at=superseded_at,
        sent_at=sent_at,
        **({"created_at": created_at} if created_at is not None else {}),
    )
    db.add(row)
    if commit:
        await db.commit()
    else:
        await db.flush()
    return row, plain
