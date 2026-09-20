"""Model trên dây: `WireModel`, `KeepNull`, `WireDatetime`, `NfcStr` (BE-00 §3.1).

Hai luật của FE mà khung phải giữ thay cho từng module:

- **vắng trường, không `null`** (W2, K02): `WireModel` bỏ mọi trường `None`, trừ
  trường khai `KeepNull`. Không dùng `exclude_unset` — nó làm rơi cả trường bắt
  buộc (K02);
- **ngày giờ đúng `.sssZ`** (W3, K20): Pydantic v2 mặc định in 6 chữ số, nên mọi
  `datetime` trên dây phải là `WireDatetime`. Khai lớp có `datetime` trần ở bất kỳ
  độ sâu kiểu nào là lỗi **ngay lúc nhập module**, không đợi tới golden.

Module này **không** nhập `fastapi`/`starlette`: hàm worker được phép nhập nó
(BE-00 §7 "Hàm worker nhập").
"""

from datetime import datetime
from typing import Annotated, Any, ClassVar, TypeVar, cast, get_args, get_origin, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, SerializerFunctionWrapHandler, create_model
from pydantic import model_serializer as _model_serializer
from pydantic.alias_generators import to_camel
from pydantic.functional_validators import AfterValidator

from packages.core.instants import to_wire
from packages.core.text import nfc

WireDatetime = Annotated[datetime, PlainSerializer(to_wire, return_type=str)]
"""Kiểu duy nhất được phép cho ngày giờ trên dây (`YYYY-MM-DDTHH:MM:SS.sssZ`)."""

NfcStr = Annotated[str, AfterValidator(nfc)]
"""Chuỗi người nhập: chuẩn hoá NFC ngay ở biên HTTP (C16, K20)."""


class _KeepNullMarker:
    """Cờ nằm trong metadata của `Annotated`; không mang dữ liệu."""

    __slots__ = ()


KEEP_NULL = _KeepNullMarker()

_T = TypeVar("_T")
KeepNull = Annotated[_T, KEEP_NULL]
"""`lastActiveAt: KeepNull[WireDatetime | None]` — khoá **luôn có**, giá trị được `null` (W2)."""

_WIRE_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


def _serializes_datetime(metadata: tuple[Any, ...]) -> bool:
    """Metadata của `Annotated` có serializer riêng chưa (tức `WireDatetime`)."""
    return any(isinstance(item, PlainSerializer) for item in metadata)


def _has_bare_datetime(annotation: Any) -> bool:
    """`datetime` không kèm serializer ở bất kỳ độ sâu nào của kiểu.

    Không đi vào `BaseModel` lồng: model lồng tự kiểm khi chính nó được khai
    (`__pydantic_init_subclass__`), nên đi tiếp chỉ làm lặp việc và dễ vòng lặp
    với kiểu tự tham chiếu.
    """
    if annotation is datetime:
        return True
    origin = get_origin(annotation)
    if origin is Annotated:
        base, *metadata = get_args(annotation)
        return not _serializes_datetime(tuple(metadata)) and _has_bare_datetime(base)
    if origin is None:
        return False
    return any(_has_bare_datetime(arg) for arg in get_args(annotation) if arg is not Ellipsis)


def _keep_null_keys(model: type["WireModel"]) -> frozenset[str]:
    """Tên trường **và** alias của mọi trường khai `KeepNull` (khoá dump theo cả hai)."""
    keys: set[str] = set()
    for name, field in model.model_fields.items():
        if any(isinstance(item, _KeepNullMarker) for item in field.metadata):
            keys.add(name)
            keys.add(field.alias or to_camel(name))
    return frozenset(keys)


class WireModel(BaseModel):
    """Gốc của mọi model **response** (BE-00 §3.1, W1-W3).

    `extra="forbid"` để một trường thừa hỏng ngay ở test của chính module, chứ không
    đợi zod `.strict()` của FE bắt (K01).
    """

    model_config = _WIRE_CONFIG

    KEEP_NULL_KEYS: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Chạy **sau** khi Pydantic dựng xong `model_fields` (khác `__init_subclass__`).

        Ném `TypeError` khi lớp con có `datetime` trần: sai này chỉ lộ ra ở chuỗi
        6 chữ số mili giây, thứ mà chỉ golden của B0-07 mới bắt được.
        """
        super().__pydantic_init_subclass__(**kwargs)
        hints = get_type_hints(cls, include_extras=True)
        bare = sorted(name for name, hint in hints.items() if name in cls.model_fields and _has_bare_datetime(hint))
        if bare:
            raise TypeError(f"{cls.__name__}: dùng WireDatetime thay cho datetime trần ở {bare} (W3)")
        cls.KEEP_NULL_KEYS = _keep_null_keys(cls)

    @_model_serializer(mode="wrap")
    def _drop_none(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Bỏ trường `None` (W2). `KeepNull` giữ lại; `exclude_unset` bị cấm (K02)."""
        data: dict[str, Any] = handler(self)
        keep = type(self).KEEP_NULL_KEYS
        return {key: value for key, value in data.items() if value is not None or key in keep}


class WireRequest(BaseModel):
    """Gốc của mọi model **request**: camelCase, khoá lạ → 422 `VALIDATION` (C03)."""

    model_config = _WIRE_CONFIG


def versioned[BodyT: BaseModel](body_model: type[BodyT]) -> type[WireRequest]:
    """Thân của ghi có version: `{baseVersion, body}` (W20, HOP-DONG-MOI §1.2).

    Thiếu `baseVersion` **không** rơi vào 422 của Pydantic: `AppRoute` kiểm trước và
    trả 428 `PRECONDITION_REQUIRED`.
    """
    model = create_model(
        f"Versioned{body_model.__name__}",
        __base__=WireRequest,
        base_version=(int, Field(ge=0)),
        body=(body_model, ...),
    )
    return cast("type[WireRequest]", model)


__all__ = [
    "KEEP_NULL",
    "KeepNull",
    "NfcStr",
    "WireDatetime",
    "WireModel",
    "WireRequest",
    "versioned",
]
