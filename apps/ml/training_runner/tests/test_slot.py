"""Test `training_slot` và `claim_lease` trên Redis thật (`messaging_env`, B6-03b [3]).

Tên test mô tả thuần, **không** hậu tố `__J0x`: regex `case_gate`
(`^test_(?P<fn>.+)__(?P<case>J\\d{2})$`) coi mọi test mang hậu tố đó là ca của một
task đã khai trong `cases.toml` — `slot.py` không khai task nào.
"""

import time

import pytest
import redis

from apps.ml.training_runner import slot as slot_module
from apps.ml.training_runner.errors import TRAINING_SLOT_LOST
from apps.ml.training_runner.keys import SLOT_KEY, claim_key, new_token
from apps.ml.training_runner.redis_sync import delete_if_owner, renew_if_owner, training_redis
from apps.ml.training_runner.slot import claim_lease, training_slot
from packages.messaging.tasks import PermanentError, TransientError

pytestmark = pytest.mark.usefixtures("messaging_env")

TTL_MS = 400
RENEW_MS = 100


def test_training_slot_present_while_held_then_gone() -> None:
    """Khoá có mặt trong lúc giữ `training_slot`, biến mất ngay khi thoát khối."""
    client = training_redis()
    try:
        with training_slot(wait_s=1, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as held:
            assert client.get(SLOT_KEY) == held.token
            held.check()
        assert client.get(SLOT_KEY) is None
    finally:
        client.close()


def test_training_slot_second_waiter_times_out() -> None:
    """Người thứ hai chờ `training_slot` tới `wait_s` rồi nhận `TransientError`."""
    client = training_redis()
    # Người giữ đặt tay với TTL dài, không lồng hai `training_slot`: `TTL_MS` 400 ms sống được
    # nhờ luồng gia hạn, mà luồng ấy bị đói CPU dưới `pytest -n 6` của cả `apps/ml` (có test
    # torch) đủ lâu để khoá hết hạn trong 0,3 s chờ — người thứ hai lấy được khoá, test đổ giả.
    try:
        client.set(SLOT_KEY, "someone-else", px=60_000)
        with pytest.raises(TransientError), training_slot(wait_s=0.3, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS):
            pass
    finally:
        client.delete(SLOT_KEY)
        client.close()


def test_training_slot_rejects_bad_renew_every_ms() -> None:
    """`renew_every_ms x 2 >= ttl_ms` → `ValueError` trước khi chạm Redis."""
    with (
        pytest.raises(ValueError, match="renew_every_ms"),
        training_slot(wait_s=1, ttl_ms=TTL_MS, renew_every_ms=TTL_MS),
    ):
        pass


def test_training_slot_lost_when_key_stolen() -> None:
    """Khoá bị xoá rồi người khác chiếm giữa chừng → `lost` bật, `check()` ném `PermanentError`."""
    client = training_redis()
    try:
        with training_slot(wait_s=1, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as held:
            delete_if_owner(client, SLOT_KEY, held.token)
            client.set(SLOT_KEY, "someone-else", px=60_000)
            assert held.lost.wait(2), "luồng gia hạn phải bật lost trong vài nhịp"
            with pytest.raises(PermanentError) as excinfo:
                held.check()
            assert excinfo.value.code == TRAINING_SLOT_LOST
    finally:
        client.delete(SLOT_KEY)
        client.close()


def test_training_slot_exit_does_not_delete_other_token() -> None:
    """Thoát khối không xoá khoá đang do token khác giữ (bị cướp mất trong lúc chạy)."""
    client = training_redis()
    try:
        with training_slot(wait_s=1, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as held:
            delete_if_owner(client, SLOT_KEY, held.token)
            client.set(SLOT_KEY, "someone-else", px=60_000)
        assert client.get(SLOT_KEY) == "someone-else"
    finally:
        client.delete(SLOT_KEY)
        client.close()


def test_training_slot_lost_on_sustained_redis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis lỗi liên tục quá `ttl_ms - renew_every_ms` → `lost` bật (fail-closed)."""

    def _broken(*_args: object, **_kwargs: object) -> bool:
        """Vá `renew_if_owner`: luôn ném lỗi Redis để test fail-closed."""
        raise redis.ConnectionError("redis giả lỗi cho test")

    monkeypatch.setattr(slot_module, "renew_if_owner", _broken)
    with training_slot(wait_s=1, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS) as held:
        assert held.lost.wait(2), "lỗi Redis liên tục phải bật lost sau vài nhịp"


def test_training_slot_exit_survives_redis_error_on_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis hỏng lúc thoát khối (xoá khoá) không che lỗi của thân khối, TTL dọn hộ."""

    def _broken_delete(*_args: object, **_kwargs: object) -> bool:
        """Vá `delete_if_owner`: luôn ném lỗi Redis để kiểm thoát khối không bị che lỗi."""
        raise redis.ConnectionError("redis giả lỗi cho test")

    monkeypatch.setattr(slot_module, "delete_if_owner", _broken_delete)
    with (
        pytest.raises(ValueError, match="trong thân khối"),
        training_slot(wait_s=1, ttl_ms=TTL_MS, renew_every_ms=RENEW_MS),
    ):
        raise ValueError("lỗi trong thân khối")


def test_claim_lease_renew_extends_ttl() -> None:
    """`claim_lease` gia hạn `claim_key` định kỳ: TTL ở cuối lớn hơn một chu kỳ ban đầu."""
    client = training_redis()
    job_id = "job_01J0000000000000000000000B"
    token = new_token()
    try:
        with claim_lease(client, job_id, token, ttl_ms=TTL_MS):
            assert client.get(claim_key(job_id)) == token
            time.sleep(RENEW_MS * 3 / 1000)
            assert client.pttl(claim_key(job_id)) > TTL_MS / 2
        assert client.get(claim_key(job_id)) is None
    finally:
        client.close()


def test_claim_lease_reacquires_after_key_deleted() -> None:
    """Khoá claim bị xoá giữa chừng → `claim_lease` giành lại bằng `SET NX` cùng token, `lost` không bật."""
    client = training_redis()
    job_id = "job_01J0000000000000000000000C"
    token = new_token()
    try:
        with claim_lease(client, job_id, token, ttl_ms=TTL_MS) as lease:
            client.delete(claim_key(job_id))
            time.sleep(RENEW_MS * 2 / 1000)
            assert client.get(claim_key(job_id)) == token
            assert not lease.lost.is_set()
    finally:
        client.close()


def test_claim_lease_lost_when_other_token_takes_over() -> None:
    """Token khác chiếm `claim_key` → `lost` bật, thoát khối không xoá claim của người khác."""
    client = training_redis()
    job_id = "job_01J0000000000000000000000D"
    token = new_token()
    try:
        with claim_lease(client, job_id, token, ttl_ms=TTL_MS) as lease:
            delete_if_owner(client, claim_key(job_id), token)
            client.set(claim_key(job_id), "other-token", px=60_000)
            assert lease.lost.wait(2), "token khác chiếm claim phải bật lost trong vài nhịp"
        assert client.get(claim_key(job_id)) == "other-token"
    finally:
        client.delete(claim_key(job_id))
        client.close()


def test_claim_lease_lost_immediately_when_already_taken() -> None:
    """Claim đã bị token khác giữ từ trước khi vào khối → `lost` bật ngay, không khởi luồng gia hạn."""
    client = training_redis()
    job_id = "job_01J0000000000000000000000G"
    token = new_token()
    client.set(claim_key(job_id), "other-token", px=60_000)
    try:
        with claim_lease(client, job_id, token, ttl_ms=TTL_MS) as lease:
            assert lease.lost.is_set()
        assert client.get(claim_key(job_id)) == "other-token"
    finally:
        client.delete(claim_key(job_id))
        client.close()


def test_claim_lease_redis_error_keeps_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis lỗi khi gia hạn claim → log và thử lại, không bật `lost` (khác `training_slot`)."""
    client = training_redis()
    job_id = "job_01J0000000000000000000000E"
    token = new_token()
    calls = {"n": 0}
    real_renew = renew_if_owner

    def _flaky(*args: object, **kwargs: object) -> bool:
        """Vá `renew_if_owner`: ném lỗi Redis hai lượt đầu rồi gọi hàm thật."""
        calls["n"] += 1
        if calls["n"] <= 2:
            raise redis.ConnectionError("redis giả lỗi cho test")
        return real_renew(client, claim_key(job_id), token, TTL_MS)

    monkeypatch.setattr(slot_module, "renew_if_owner", _flaky)
    try:
        with claim_lease(client, job_id, token, ttl_ms=TTL_MS) as lease:
            time.sleep(RENEW_MS * 4 / 1000)
            assert not lease.lost.is_set()
    finally:
        client.close()


def test_claim_lease_exit_survives_redis_error_on_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis hỏng lúc thoát khối (xoá claim) không che lỗi của thân khối, TTL dọn hộ."""
    client = training_redis()
    job_id = "job_01J0000000000000000000000F"
    token = new_token()

    def _broken_delete(*_args: object, **_kwargs: object) -> bool:
        """Vá `delete_if_owner`: luôn ném lỗi Redis để kiểm thoát khối không bị che lỗi."""
        raise redis.ConnectionError("redis giả lỗi cho test")

    monkeypatch.setattr(slot_module, "delete_if_owner", _broken_delete)
    try:
        with (
            pytest.raises(ValueError, match="trong thân khối"),
            claim_lease(client, job_id, token, ttl_ms=TTL_MS),
        ):
            raise ValueError("lỗi trong thân khối")
    finally:
        client.close()
