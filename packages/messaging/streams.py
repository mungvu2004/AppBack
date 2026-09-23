"""Bus sự kiện trên Redis Streams (BE-00 §7).

Mỗi mục stream có đúng một trường `d` chứa JSON UTF-8, cắt bằng `MAXLEN ~` nên
Redis được phép giữ dôi vài mục — người đọc không bao giờ dựa vào số mục.

Không có consumer group: mỗi kết nối SSE `XREAD` từ id riêng của nó (S02), nên
hai người đọc cùng stream thấy cùng chuỗi sự kiện. `publish_once` là lối vào duy
nhất cho thông báo: FE không khử trùng, XADD hai lần là người dùng thấy hai lần
(K32).
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from packages.core.ids import is_id
from packages.messaging.redis import MAX_BLOCK_MS, AsyncRedis, SyncRedis, redis_errors
from packages.messaging.settings import get_messaging_settings

FIELD: Final = "d"
_EVENT_ID_RE: Final = re.compile(r"[0-9]{1,20}-[0-9]{1,20}")
FIRST_ID: Final = "0-0"

# Lua chạy nguyên khối trong Redis: lượt lặp thấy khoá khử trùng thì trả id cũ và
# **không** XADD, nên thông báo vào stream đúng một lần dù task được giao lại (J10).
_PUBLISH_ONCE: Final = """
local seen = redis.call('GET', KEYS[1])
if seen then return seen end
local id = redis.call('XADD', KEYS[2], 'MAXLEN', '~', ARGV[1], '*', ARGV[2], ARGV[3])
redis.call('SET', KEYS[1], id, 'EX', ARGV[4])
return id
"""


@dataclass(frozen=True, slots=True)
class Event:
    """Một mục stream đã giải mã; `id` là id Redis `<mili giây>-<thứ tự>`."""

    id: str
    data: dict[str, object]


def is_event_id(value: str) -> bool:
    """Đúng mẫu id Redis Stream. `lastEventId` do client gửi phải qua hàm này trước."""
    return _EVENT_ID_RE.fullmatch(value) is not None


def user_stream(user_id: str) -> str:
    """Stream thông báo của một người dùng."""
    if not is_id("usr", user_id):
        raise ValueError(f"user_id sai mẫu usr_<ULID>: {user_id!r}")
    return f"events:user:{user_id}"


def upload_stream(upload_id: str) -> str:
    """Stream tiến độ của một lượt upload; được `EXPIRE` sau trạng thái cuối."""
    if not is_id("upl", upload_id):
        raise ValueError(f"upload_id sai mẫu upl_<ULID>: {upload_id!r}")
    return f"events:upload:{upload_id}"


def _encode(data: Mapping[str, object]) -> str:
    """JSON hoá thân sự kiện; kiểu thô (`bytes`, `datetime`) ném `TypeError` tại chỗ.

    Người gọi phải đổi sang dạng dây bằng `packages.core.instants.to_wire` trước,
    để lỗi lộ ra ở nơi sinh dữ liệu chứ không ở người đọc stream.
    """
    return json.dumps(data, ensure_ascii=False, allow_nan=False)


def _decode(entries: Sequence[tuple[str, Mapping[str, str]]]) -> list[Event]:
    return [Event(id=entry_id, data=json.loads(fields[FIELD])) for entry_id, fields in entries]


def _stream_entries(streams: object) -> Sequence[tuple[str, Mapping[str, str]]]:
    """Entries của stream đầu (và duy nhất) trong kết quả `XREAD`.

    Stub redis-py 8 khai kiểu trả của `xread` gộp cả dạng RESP2 (list các tuple) và
    RESP3 (dict) vì dùng chung cho hai giao thức; client Streams (`packages.messaging.redis`)
    không đặt `protocol=3` nên luôn nhận RESP2. Dạng khác là lỗi lập trình, ném rõ thay vì
    nuốt (R-16).
    """
    if not isinstance(streams, list):
        raise TypeError(f"XREAD kỳ vọng list (RESP2), nhận {type(streams).__name__}")
    entries = streams[0][1]
    if not isinstance(entries, list):
        raise TypeError(f"XREAD kỳ vọng entries dạng list (RESP2), nhận {type(entries).__name__}")
    return cast(list[tuple[str, Mapping[str, str]]], entries)


def _id_key(event_id: str) -> tuple[int, int]:
    milliseconds, _, sequence = event_id.partition("-")
    return int(milliseconds), int(sequence)


def _check_event_id(event_id: str) -> str:
    if not is_event_id(event_id):
        raise ValueError(f"id sự kiện sai mẫu <mili giây>-<thứ tự>: {event_id!r}")
    return event_id


def _check_block_ms(block_ms: int) -> int:
    """Trần chặn phải nằm dưới trần đọc socket của client Streams, không thì `XREAD` timeout."""
    if not 0 <= block_ms <= MAX_BLOCK_MS:
        raise ValueError(f"block_ms phải trong [0, {MAX_BLOCK_MS}], nhận {block_ms}")
    return block_ms


def _dedupe_key(dedupe_key: str) -> str:
    if not dedupe_key:
        raise ValueError("dedupe_key không được rỗng")
    return f"dedupe:{dedupe_key}"


class _Bus:
    """Phần chung của hai bản bus: trần `MAXLEN` và tham số của script `publish_once`."""

    def __init__(self, maxlen: int | None) -> None:
        self._maxlen = get_messaging_settings().stream_maxlen if maxlen is None else maxlen

    def _once_call(
        self, stream: str, dedupe_key: str, data: Mapping[str, object], ttl_s: int
    ) -> tuple[list[str], list[str | int]]:
        """(KEYS, ARGV) của `_PUBLISH_ONCE` — một nguồn duy nhất cho bản async và sync."""
        if ttl_s <= 0:
            raise ValueError(f"ttl_s phải > 0, nhận {ttl_s}")
        return [_dedupe_key(dedupe_key), stream], [self._maxlen, FIELD, _encode(data), ttl_s]


class EventBus(_Bus):
    """Bản async, dùng trong request và trong SSE."""

    def __init__(self, client: AsyncRedis, *, maxlen: int | None = None) -> None:
        super().__init__(maxlen)
        self._client = client
        # `register_script` chỉ băm nội dung; script được nạp vào Redis ở lần gọi đầu.
        self._once = client.register_script(_PUBLISH_ONCE)

    async def publish(self, stream: str, data: Mapping[str, object]) -> str:
        """XADD một sự kiện, trả id của nó."""
        with redis_errors():
            return str(await self._client.xadd(stream, {FIELD: _encode(data)}, maxlen=self._maxlen, approximate=True))

    async def publish_once(self, stream: str, dedupe_key: str, data: Mapping[str, object], ttl_s: int) -> str:
        """XADD đúng một lần cho mỗi `dedupe_key` còn hạn; lượt lặp trả id đã phát (K32)."""
        keys, args = self._once_call(stream, dedupe_key, data, ttl_s)
        with redis_errors():
            return str(await self._once(keys=keys, args=args))

    async def read_after(self, stream: str, last_id: str, *, block_ms: int = 0, count: int = 100) -> list[Event]:
        """Sự kiện có id **lớn hơn** `last_id`, đúng thứ tự, không trùng (S02)."""
        _check_event_id(last_id)
        _check_block_ms(block_ms)
        with redis_errors():
            # `block=0` với Redis nghĩa là chặn vô hạn; `None` mới là "không chặn".
            streams = await self._client.xread({stream: last_id}, count=count, block=block_ms or None)
        return [] if not streams else _decode(_stream_entries(streams))

    async def tail_id(self, stream: str) -> str | None:
        """Id mục cuối, hoặc `None` khi stream rỗng — điểm bắt đầu của một luồng mở mới (S08)."""
        with redis_errors():
            entries = await self._client.xrevrange(stream, count=1)
        return None if not entries else str(entries[0][0])

    async def is_trimmed(self, stream: str, last_id: str) -> bool:
        """`last_id` đã rơi khỏi stream vì `MAXLEN` — người đọc phải xin lại ảnh chụp."""
        _check_event_id(last_id)
        with redis_errors():
            entries = await self._client.xrange(stream, count=1)
        return True if not entries else _id_key(last_id) < _id_key(str(entries[0][0]))

    async def expire(self, stream: str, seconds: int) -> None:
        """Hẹn giờ xoá cả stream (stream upload hết hạn 24 giờ sau trạng thái cuối)."""
        with redis_errors():
            await self._client.expire(stream, seconds)


class SyncEventBus(_Bus):
    """Bản đồng bộ cho `on_after_commit`, chạy ngoài vòng sự kiện (BE-00 §7).

    Chỉ có ba thao tác ghi: đường sau commit không đọc lại stream.
    """

    def __init__(self, client: SyncRedis, *, maxlen: int | None = None) -> None:
        super().__init__(maxlen)
        self._client = client
        self._once = client.register_script(_PUBLISH_ONCE)

    def publish(self, stream: str, data: Mapping[str, object]) -> str:
        """XADD một sự kiện, trả id của nó."""
        with redis_errors():
            return str(self._client.xadd(stream, {FIELD: _encode(data)}, maxlen=self._maxlen, approximate=True))

    def publish_once(self, stream: str, dedupe_key: str, data: Mapping[str, object], ttl_s: int) -> str:
        """XADD đúng một lần cho mỗi `dedupe_key` còn hạn; lượt lặp trả id đã phát (K32)."""
        keys, args = self._once_call(stream, dedupe_key, data, ttl_s)
        with redis_errors():
            return str(self._once(keys=keys, args=args))

    def expire(self, stream: str, seconds: int) -> None:
        """Hẹn giờ xoá cả stream."""
        with redis_errors():
            self._client.expire(stream, seconds)
