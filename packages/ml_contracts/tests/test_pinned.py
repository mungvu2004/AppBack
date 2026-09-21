"""Bản ghim và lệnh tải: chỉ thư viện chuẩn, luật `fetch` với bộ mở giả (không mạng trong test)."""

import hashlib
import http.client
import io
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from contextlib import AbstractContextManager
from pathlib import Path

import pytest

from packages.ml_contracts import pinned
from packages.ml_contracts.families import BASE_MODELS, MODEL_FAMILIES
from packages.ml_contracts.pinned import (
    BASELINE,
    PINNED,
    UNPINNED,
    FetchError,
    PinnedFile,
    PinnedWeights,
    Readable,
    fetch,
    open_https,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE = b"trong so nguon"
EXTRA = b'{"model_type": "segformer"}'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def weights(
    source: bytes = SOURCE, extra: bytes = EXTRA, source_url: str = "https://x.test/v1/model.bin"
) -> PinnedWeights:
    return PinnedWeights(
        name="demo",
        family="wallSegmentation",
        source_url=source_url,
        source_sha256=sha(source),
        onnx_sha256=None,
        license="MIT",
        extra_files=(PinnedFile("config.json", "https://x.test/v1/config.json", sha(extra)),),
    )


class Opener:
    """Bộ mở giả: trả nội dung theo URL và đếm lượt mở."""

    def __init__(self, bodies: dict[str, bytes], error: Exception | None = None) -> None:
        self.bodies = bodies
        self.error = error
        self.opened: list[str] = []

    def __call__(self, url: str) -> AbstractContextManager[Readable]:
        self.opened.append(url)
        if self.error is not None:
            raise self.error
        return io.BytesIO(self.bodies[url])


BODIES = {"https://x.test/v1/model.bin": SOURCE, "https://x.test/v1/config.json": EXTRA}


def test_pinned_table_rules() -> None:
    """URL https cố định (tag hay commit), SHA 64 hex đã đo, họ và bản gốc khớp bảng họ."""
    for name, pin in PINNED.items():
        assert pin.name == name
        assert pin.family in MODEL_FAMILIES
        for digest in (pin.source_sha256, pin.onnx_sha256 or pin.source_sha256, *(f.sha256 for f in pin.files)):
            assert len(digest) == 64
            assert digest != UNPINNED
            assert digest == digest.lower()
        for item in pin.files:
            assert item.url.startswith("https://")
            assert "/main/" not in item.url
            assert "/latest/" not in item.url
    assert {name for names in BASE_MODELS.values() for name in names} <= set(PINNED)
    assert PINNED["mitB0"].onnx_sha256 is None
    assert [f.filename for f in PINNED["mitB1"].files] == ["model.safetensors", "config.json"]
    assert PINNED["rapidocrRec"].files == ()
    assert all(PINNED[name].family == family for family, name in BASELINE.items())
    assert "wallSegmentation" not in BASELINE


def test_pinned_stdlib_only() -> None:
    """`pinned`, `families` chạy được ở bước build trước khi có numpy/pydantic."""
    script = textwrap.dedent(
        """
        import sys
        before = set(sys.modules)
        import packages.ml_contracts.pinned
        top = {name.split(".")[0] for name in set(sys.modules) - before}
        print(sorted(top - set(sys.stdlib_module_names) - {"packages"}))
        """
    )
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=60
    )
    assert result.stdout.strip() == "[]"


def test_fetch_rules(tmp_path: Path) -> None:
    """Tải vào `.part` rồi đổi tên; có sẵn đúng SHA thì không mở mạng; lệch thì tải lại."""
    table = {"demo": weights()}
    opener = Opener(BODIES)
    fetch(tmp_path, opener=opener, pinned=table)
    assert (tmp_path / "demo" / "model.bin").read_bytes() == SOURCE
    assert (tmp_path / "demo" / "config.json").read_bytes() == EXTRA
    assert not list(tmp_path.rglob("*.part"))
    fetch(tmp_path, opener=opener, pinned=table)
    assert len(opener.opened) == 2
    (tmp_path / "demo" / "model.bin").write_bytes(b"hong")
    fetch(tmp_path, opener=opener, pinned=table)
    assert opener.opened[-1] == "https://x.test/v1/model.bin"
    assert (tmp_path / "demo" / "model.bin").read_bytes() == SOURCE


def test_fetch_skips_bundled_sources(tmp_path: Path) -> None:
    opener = Opener(BODIES)
    fetch(tmp_path, opener=opener, pinned={"demo": weights(source_url="")})
    assert opener.opened == ["https://x.test/v1/config.json"]


def test_fetch_mismatch_deletes_and_exits_2(tmp_path: Path) -> None:
    opener = Opener({**BODIES, "https://x.test/v1/model.bin": b"bi thay"})
    with pytest.raises(FetchError, match="lệch") as caught:
        fetch(tmp_path, opener=opener, pinned={"demo": weights()})
    assert caught.value.exit_code == 2
    assert not list(tmp_path.rglob("model.bin*"))


def test_fetch_over_cap_is_a_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pinned, "FETCH_MAX_BYTES", len(SOURCE) - 1)
    with pytest.raises(FetchError) as caught:
        fetch(tmp_path, opener=Opener(BODIES), pinned={"demo": weights()})
    assert caught.value.exit_code == 2
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.parametrize(
    "error",
    [urllib.error.URLError("mất mạng"), TimeoutError("chậm"), http.client.IncompleteRead(b"x")],
)
def test_fetch_network_errors_exit_3(tmp_path: Path, error: Exception) -> None:
    with pytest.raises(FetchError, match="không tải được") as caught:
        fetch(tmp_path, opener=Opener(BODIES, error=error), pinned={"demo": weights()})
    assert caught.value.exit_code == 3
    assert not list(tmp_path.rglob("*.part"))


def test_fetch_refuses_unpinned_before_any_download(tmp_path: Path) -> None:
    opener = Opener(BODIES)
    unpinned = PinnedWeights("x", "wallSegmentation", "https://x.test/v1/w.bin", UNPINNED, None, "MIT")
    with pytest.raises(FetchError, match="chưa ghim: x") as caught:
        fetch(tmp_path, opener=opener, pinned={"demo": weights(), "x": unpinned})
    assert caught.value.exit_code == 2
    assert opener.opened == []


def test_open_https_sets_timeout_and_refuses_http(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, float]] = []

    def fake_urlopen(url: str, timeout: float) -> io.BytesIO:
        seen.append((url, timeout))
        return io.BytesIO(b"")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with open_https("https://x.test/a") as response:
        assert response.read(1) == b""
    assert seen == [("https://x.test/a", pinned.FETCH_TIMEOUT_S)]
    with pytest.raises(ValueError, match="https"):
        open_https("http://x.test/a")


@pytest.mark.parametrize(("raised", "code"), [(None, 0), (FetchError(3, "mạng"), 3)])
def test_main_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raised: FetchError | None, code: int) -> None:
    calls: list[Path] = []

    def fake_fetch(dest: Path) -> None:
        calls.append(dest)
        if raised is not None:
            raise raised

    monkeypatch.setattr(pinned, "fetch", fake_fetch)
    assert pinned.main(["fetch", "--dest", str(tmp_path)]) == code
    assert calls == [tmp_path]


def test_cli_runs_as_module() -> None:
    """`python -m packages.ml_contracts.pinned` là điểm vào của bước build (không mở mạng: chỉ `--help`)."""
    result = subprocess.run(
        [sys.executable, "-m", "packages.ml_contracts.pinned", "fetch", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0
    assert "--dest" in result.stdout
