"""FIX-114 — `_shared_container`: mọi tiến trình xdist dùng chung một container dịch vụ.

Bản thân việc "dịch vụ lên thật" đã có `tools/tests/test_services.py` (K23). Ở đây kiểm đúng
phần **chia sẻ và đếm**, thứ chỉ hiện ra khi có nhiều tiến trình: ai dựng, ai đọc lại, và ai xoá.
Container là bản giả có chủ ý — cái đang kiểm là bộ đếm và file trạng thái, không phải Docker
(K23 cấm mock chính dịch vụ **đang kiểm**, không cấm mock thứ nằm ngoài phạm vi test).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from docker.errors import NotFound  # type: ignore[import-untyped]

from packages.testing.fixtures import services
from packages.testing.fixtures.services import SHARED_STATE_PREFIX, _shared_container
from packages.testing.fixtures.worker_id import XDIST_WORKER_ENV

KEY = "svc"


@dataclass
class _FakeWrapped:
    id: str


@dataclass
class _FakeContainer:
    """Chỗ `_shared_container` chỉ dùng `get_wrapped_container().id` và `stop()`."""

    id: str
    stopped: list[str] = field(default_factory=list)

    def get_wrapped_container(self) -> _FakeWrapped:
        return _FakeWrapped(self.id)

    def stop(self) -> None:
        self.stopped.append(self.id)


@dataclass
class _FakeTempPathFactory:
    """`getbasetemp()` như xdist: một thư mục con mỗi tiến trình dưới đúng một gốc mỗi lượt chạy."""

    root: Path
    worker: str

    def getbasetemp(self) -> Path:
        base = self.root / f"popen-{self.worker}"
        base.mkdir(parents=True, exist_ok=True)
        return base


def _factory(root: Path, worker: str) -> pytest.TempPathFactory:
    return cast(pytest.TempPathFactory, _FakeTempPathFactory(root, worker))


@dataclass
class _Starter:
    """Đếm số lần thật sự dựng container — điều duy nhất phân biệt "chia chung" với "mỗi người một bản"."""

    calls: list[str] = field(default_factory=list)
    containers: list[_FakeContainer] = field(default_factory=list)

    def __call__(self) -> tuple[_FakeContainer, str]:
        container = _FakeContainer(id=f"cid-{len(self.calls)}")
        self.calls.append(container.id)
        self.containers.append(container)
        return container, f"endpoint-{container.id}"


def _state(root: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads((root / f"{SHARED_STATE_PREFIX}{KEY}.json").read_text(encoding="utf-8")))


def test_ngoài_xdist_dựng_thẳng_rồi_dừng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Chạy tay (`-p no:xdist`): không file trạng thái, không khoá — hành vi cũ, y nguyên."""
    monkeypatch.delenv(XDIST_WORKER_ENV, raising=False)
    starter = _Starter()
    with _shared_container(KEY, _factory(tmp_path, "gw0"), starter) as value:
        assert value == "endpoint-cid-0"
    assert starter.containers[0].stopped == ["cid-0"]
    assert not list(tmp_path.glob(f"{SHARED_STATE_PREFIX}*"))


def test_tiến_trình_thứ_hai_dùng_lại_container_của_tiến_trình_đầu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hai tiến trình xdist chồng nhau: dựng **một** lần, cả hai thấy cùng địa chỉ, đếm lên 2."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw0")
    starter = _Starter()
    with patch.object(services, "_remove_container"):  # container giả: không có gì cho Docker xoá
        with _shared_container(KEY, _factory(tmp_path, "gw0"), starter) as first:
            monkeypatch.setenv(XDIST_WORKER_ENV, "gw1")
            with _shared_container(KEY, _factory(tmp_path, "gw1"), starter) as second:
                assert first == second == "endpoint-cid-0"
                assert _state(tmp_path)["users"] == 2
        assert starter.calls == ["cid-0"]


def test_chỉ_người_rời_cuối_cùng_xoá_container(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tiến trình dựng xong trước **không** được xoá: hai tiến trình kia còn đang dùng."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw0")
    starter = _Starter()
    with patch.object(services, "_remove_container") as remove:
        with _shared_container(KEY, _factory(tmp_path, "gw0"), starter):
            monkeypatch.setenv(XDIST_WORKER_ENV, "gw1")
            with _shared_container(KEY, _factory(tmp_path, "gw1"), starter):
                pass
            # gw1 (người dựng là gw0) đã rời: còn một người dùng, container phải còn sống
            remove.assert_not_called()
            assert _state(tmp_path)["users"] == 1
        remove.assert_called_once_with("cid-0")
    assert starter.containers[0].stopped == []  # không đi đường `stop()` của nhánh ngoài xdist


def test_người_vào_sau_khi_đếm_về_0_dựng_container_mới(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review F-1: file trạng thái phải mất cùng container, không để lại `users: 0` trỏ vào xác cũ.

    xdist tắt tiến trình đã hết việc trước khi cả phiên xong (`--dist loadfile`), nên một tiến
    trình còn lại có thể nhận fixture **lần đầu** sau khi bộ đếm đã về 0. Nó phải dựng container
    mới, không được đọc lại endpoint của container vừa bị xoá.
    """
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw0")
    starter = _Starter()
    with patch.object(services, "_remove_container"):
        with _shared_container(KEY, _factory(tmp_path, "gw0"), starter) as first:
            assert first == "endpoint-cid-0"
        assert not list(tmp_path.glob(f"{SHARED_STATE_PREFIX}*.json"))

        monkeypatch.setenv(XDIST_WORKER_ENV, "gw1")
        with _shared_container(KEY, _factory(tmp_path, "gw1"), starter) as second:
            assert second == "endpoint-cid-1"  # container mới, không phải endpoint đã chết
    assert starter.calls == ["cid-0", "cid-1"]


def test_container_đã_biến_mất_không_làm_hỏng_lượt_dọn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review F-2: `NotFound` là đích đã đạt — teardown fixture phiên phải kết thúc sạch."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw0")
    with patch.object(services, "DockerClient") as docker_client:
        docker_client.return_value.client.containers.get.side_effect = NotFound("đã bị xoá")
        with _shared_container(KEY, _factory(tmp_path, "gw0"), _Starter()):
            pass
    assert not list(tmp_path.glob(f"{SHARED_STATE_PREFIX}*.json"))


def test_container_bị_xoá_dù_thân_test_ném_lỗi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lượt chạy hỏng giữa chừng vẫn phải trả container lại, không để lại rác (R-16)."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw0")
    with patch.object(services, "_remove_container") as remove:  # noqa: SIM117 — `pytest.raises` phải ở trong
        with pytest.raises(ValueError, match="hỏng"), _shared_container(KEY, _factory(tmp_path, "gw0"), _Starter()):
            raise ValueError("hỏng")
    remove.assert_called_once_with("cid-0")
    assert not list(tmp_path.glob(f"{SHARED_STATE_PREFIX}*.json"))  # người cuối đi thì file đi theo
