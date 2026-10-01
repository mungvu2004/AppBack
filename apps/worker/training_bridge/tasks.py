"""Năm task cầu nối `default.training_bridge.*` của job huấn luyện (B6-03a [2], [6]).

Khung prep: chỉ có `arm_cancel_key`, thứ cả task lẫn lịch (`jobs.py`) gọi trước mọi commit
chuyển job sang `failed|cancelled`. Việc C viết các task vào file này.
"""

from apps.worker.training_bridge.settings import get_training_settings
from packages.messaging.payloads.training import cancel_key
from packages.messaging.redis import safe_redis


async def arm_cancel_key(job_id: str) -> None:
    """Đặt `training:cancel:{job}` = "1" với TTL `TRAINING_CANCEL_TTL_S` (BE-00 §7).

    Gọi **trước** commit; Redis lỗi thì ngoại lệ lan lên để người gọi rollback (task: lỗi
    tạm J02, lịch: bỏ lượt). Gọi lại trên job đã kết thúc là bình thường (đặt lại khoá).
    """
    await safe_redis().set(cancel_key(job_id), "1", ex=get_training_settings().training_cancel_ttl_s)
