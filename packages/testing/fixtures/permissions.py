"""`engineer_without_qc_approve`: ma trận quyền mà engineer giữ `layer.edit` nhưng mất `qc.approve`.

Ma trận thật cho hai khoá ấy cùng giá trị ở mọi vai, nên chỉ một vai "sửa được nhưng không duyệt
được" mới phân biệt được route có kiểm `qc.approve` thật hay chỉ dựa vào `layer.edit` (NFR-02).
`can` đọc `PERMISSION_MATRIX` của module lúc gọi, nên thay biến module là đủ cho mọi nơi gọi.
"""

from types import MappingProxyType

import httpx
import pytest

from packages.domain.permissions import matrix


def assert_forbidden(response: httpx.Response) -> None:
    """403 đúng thân W7: chỉ `code` và `requestId` khớp header `X-Request-Id` (bắt buộc có); lệch → `AssertionError`."""
    request_id = response.headers.get("X-Request-Id")
    expected = {"code": "FORBIDDEN", "requestId": request_id}
    if request_id is None or response.status_code != 403 or response.json() != expected:
        raise AssertionError(f"kỳ vọng 403 {expected}, nhận {response.status_code} {response.text}")


@pytest.fixture
def engineer_without_qc_approve(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thay `PERMISSION_MATRIX` trong phạm vi một test: `qc.approve` chỉ còn cho admin."""
    patched = MappingProxyType(
        {
            **matrix.PERMISSION_MATRIX,
            "qc.approve": MappingProxyType({"admin": True, "engineer": False, "viewer": False}),
        }
    )
    monkeypatch.setattr(matrix, "PERMISSION_MATRIX", patched)
