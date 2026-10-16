"""`packages/testing/fixtures/permissions.py`: fixture tắt `qc.approve` của engineer, helper khẳng định 403 W7."""

import httpx
import pytest

from packages.domain.permissions import can
from packages.testing.fixtures.permissions import assert_forbidden

_HEADERS = {"X-Request-Id": "req_1"}


@pytest.mark.usefixtures("engineer_without_qc_approve")
def test_engineer_without_qc_approve__only_qc_approve_changes() -> None:
    """Engineer mất `qc.approve` nhưng giữ `layer.edit`; admin giữ cả hai."""
    assert (can("engineer", "qc.approve"), can("engineer", "layer.edit"), can("admin", "qc.approve")) == (
        False,
        True,
        True,
    )


def test_assert_forbidden__accepts_w7_body() -> None:
    """Đúng 403 với `{code, requestId}` khớp header → không ném."""
    assert_forbidden(httpx.Response(403, json={"code": "FORBIDDEN", "requestId": "req_1"}, headers=_HEADERS))


@pytest.mark.parametrize(
    ("status", "body", "headers"),
    [
        (200, {"code": "FORBIDDEN", "requestId": "req_1"}, _HEADERS),
        (403, {"code": "FORBIDDEN", "requestId": "khác"}, _HEADERS),
        (403, {"code": "FORBIDDEN", "requestId": None}, {}),
    ],
)
def test_assert_forbidden__rejects_other_responses(
    status: int, body: dict[str, str | None], headers: dict[str, str]
) -> None:
    """Sai status, `requestId` lệch header, hay thiếu hẳn header (thân `requestId: null`) → `AssertionError`."""
    with pytest.raises(AssertionError):
        assert_forbidden(httpx.Response(status, json=body, headers=headers))
