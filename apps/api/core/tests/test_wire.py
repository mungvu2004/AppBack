"""`WireModel`: bỏ `None`, giữ `KeepNull`, `.sssZ`, NFC, và schema OpenAPI đúng alias."""

import unicodedata
from datetime import UTC, datetime
from typing import Final

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from apps.api.core.auth import Principal
from apps.api.core.tests.sample import ItemBody, OptionalOut, sample_app, sample_client
from apps.api.core.wire import KeepNull, NfcStr, WireDatetime, WireModel, WireRequest, versioned
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock

__all__ = ["sample_app", "sample_client"]

NFD_NAME: Final = unicodedata.normalize("NFD", "Tầng trệt")
MOMENT: Final = datetime(2026, 3, 4, 5, 6, 7, 123456, tzinfo=UTC)


def test_none_is_dropped_and_keep_null_stays() -> None:
    """W2: trường `None` vắng khoá, trừ trường khai `KeepNull`."""
    dumped = OptionalOut(name="a", note=None, seen_at=None).model_dump(by_alias=True)
    assert "note" not in dumped
    assert dumped == {"name": "a", "seenAt": None}


def test_datetime_is_three_millis() -> None:
    """W3: đúng ba chữ số mili giây, cắt chứ không làm tròn."""
    dumped = OptionalOut(name="a", seen_at=MOMENT).model_dump(by_alias=True, mode="json")
    assert dumped["seenAt"] == "2026-03-04T05:06:07.123Z"


def test_bare_datetime_is_rejected_at_class_declaration() -> None:
    """`datetime` trần ở bất kỳ độ sâu nào → hỏng ngay lúc khai lớp, không đợi golden."""
    with pytest.raises(TypeError, match="WireDatetime"):

        class Bad(WireModel):
            """Model sai: `datetime` trần trong list."""

            moments: list[datetime | None]


def test_bare_datetime_in_dict_is_rejected() -> None:
    """`datetime` trần nằm trong giá trị dict cũng bị bắt."""
    with pytest.raises(TypeError, match="WireDatetime"):

        class BadDict(WireModel):
            """Model sai: `datetime` trần trong dict."""

            by_name: dict[str, datetime]


def test_wire_datetime_is_accepted_at_any_depth() -> None:
    """Có serializer thì mọi độ sâu đều hợp lệ."""

    class Good(WireModel):
        """Model hợp lệ: mọi `datetime` đều là `WireDatetime`."""

        moments: list[WireDatetime | None]

    assert Good(moments=[MOMENT, None]).model_dump(by_alias=True, mode="json")["moments"][0].endswith("Z")


def test_nested_wire_model_checks_itself() -> None:
    """Model lồng tự kiểm khi chính nó được khai, nên model ngoài không phải đi sâu."""

    class Inner(WireModel):
        """Model lồng tự kiểm `datetime` của nó."""

        at: WireDatetime

    class Outer(WireModel):
        """Model ngoài chứa model lồng."""

        inner: Inner

    assert Outer(inner=Inner(at=MOMENT)).model_dump(by_alias=True, mode="json")["inner"]["at"].endswith(".123Z")


def test_extra_key_is_forbidden() -> None:
    """K01: response không bao giờ mang trường FE không khai."""
    with pytest.raises(ValueError, match="Extra inputs"):
        OptionalOut(name="a", la=1)


def test_nfc_str_normalises_input() -> None:
    """C16, K20: chuỗi người nhập lưu dạng NFC."""
    body = ItemBody(name=NFD_NAME)
    assert body.name == unicodedata.normalize("NFC", NFD_NAME)
    assert body.name != NFD_NAME


def test_keep_null_alias_is_recorded() -> None:
    """Sổ khoá `KeepNull` mang cả tên trường lẫn alias (dump theo kiểu nào cũng đúng)."""
    assert {"seen_at", "seenAt"} <= OptionalOut.KEEP_NULL_KEYS


def test_versioned_builds_base_version_body() -> None:
    """`versioned()` dựng thân `{baseVersion, body}` (W20, HOP-DONG-MOI §1.2)."""
    model = versioned(ItemBody)
    assert issubclass(model, WireRequest)
    parsed = model.model_validate({"baseVersion": 2, "body": {"name": "a"}})
    assert parsed.model_dump(by_alias=True)["baseVersion"] == 2


def test_versioned_rejects_negative_base_version() -> None:
    """`baseVersion` âm hỏng ở Pydantic (422)."""
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        versioned(ItemBody).model_validate({"baseVersion": -1, "body": {"name": "a"}})


def test_keep_null_annotation_is_usable_on_plain_model() -> None:
    """`KeepNull` chỉ là `Annotated`; nó không ràng buộc model phải là `WireModel`."""

    class Plain(BaseModel):
        """Model thường dùng `KeepNull`."""

        value: KeepNull[int | None] = None

    assert Plain().model_dump() == {"value": None}


def test_nfc_str_is_plain_str_annotation() -> None:
    """`NfcStr` dùng được như `str` trong model request."""

    class Request(WireRequest):
        """Model request có `NfcStr`."""

        name: NfcStr

    assert Request(name="a").name == "a"


async def test_optional_field_is_absent_on_the_wire(
    sample_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """C17 trên dây thật: `note` vắng, `seenAt` có khoá và bằng `null`."""
    response = await sample_client.get("/api/sample/optional", headers=auth_headers(fake_principal))
    assert response.status_code == 200
    assert response.json() == {"name": "tuỳ chọn", "seenAt": None}


async def test_datetime_on_the_wire_ends_with_three_millis(
    sample_client: httpx.AsyncClient, fake_principal: Principal, fake_clock: FakeClock
) -> None:
    """Ngày giờ qua HTTP thật cũng đúng `.sssZ`."""
    fake_clock.set(MOMENT)
    response = await sample_client.get("/api/sample/now", headers=auth_headers(fake_principal))
    assert response.json()["seenAt"] == "2026-03-04T05:06:07.123Z"


def test_openapi_keeps_response_properties_with_aliases(sample_app: FastAPI) -> None:
    """`model_serializer` không được làm rơi `properties` của schema response (K01)."""
    schema = sample_app.openapi()["components"]["schemas"]["OptionalOut"]
    assert set(schema["properties"]) == {"name", "note", "seenAt"}
    assert schema["required"] == ["name"]
