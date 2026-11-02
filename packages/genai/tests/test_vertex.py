"""`VertexGemini`, `GenAISettings`, `create_genai`, `FakeGenAI` — không mạng (HTTP tiêm, máy chủ cục bộ)."""

import base64
import json
import threading
from collections.abc import Iterator, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import exceptions
from pydantic import SecretStr, ValidationError

from packages.genai import (
    GENAI_AUTH,
    GENAI_BAD_RESPONSE,
    GENAI_UNAVAILABLE,
    GenAIError,
    GenAIResult,
    GenAISettings,
    ImagePart,
    Part,
    TextPart,
    VertexGemini,
    create_genai,
    get_genai_settings,
    reset_genai_settings_cache,
)
from packages.genai.vertex import MAX_ATTEMPTS, TIMEOUT_S, _google_request, urllib_post
from packages.testing.fixtures.genai import FakeGenAI

SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}}}


class FakeCreds:
    """Credentials giả: hết hạn cho tới khi `refresh`; `fail` ném lỗi google-auth chỉ định."""

    def __init__(self, *, valid: bool = True, fail: Exception | None = None, bearer: str | None = "tok") -> None:
        self.valid = valid
        self.token = bearer if valid else None
        self.fail = fail
        self._new_token = bearer
        self.refreshes: list[Any] = []

    def refresh(self, request: Any) -> None:
        self.refreshes.append(request)
        if self.fail:
            raise self.fail
        self.valid, self.token = True, self._new_token


class FakePost:
    """`post` giả: trả lần lượt các (status, body) hoặc ném ngoại lệ, ghi lại lời gọi."""

    def __init__(self, *replies: tuple[int, bytes] | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, dict[str, str], bytes, float]] = []

    def __call__(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
        self.calls.append((url, dict(headers), body, timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def ok(parts: list[dict[str, Any]], usage: dict[str, int] | None = None) -> tuple[int, bytes]:
    """Phản hồi 200 với `parts` của candidate đầu."""
    res: dict[str, Any] = {"candidates": [{"content": {"parts": parts}}]}
    if usage is not None:
        res["usageMetadata"] = usage
    return 200, json.dumps(res).encode()


def make(post: FakePost, creds: FakeCreds | None = None, sleeps: list[float] | None = None) -> VertexGemini:
    """`VertexGemini` với HTTP, sleep, transport token giả."""
    sink = sleeps if sleeps is not None else []
    return VertexGemini(
        creds or FakeCreds(), project="p1", model="m1", post=post, sleep=sink.append, google_request=lambda: "REQ"
    )


def test_request_body_and_headers() -> None:
    post = FakePost(ok([{"text": '{"a": 1}'}], {"promptTokenCount": 11, "candidatesTokenCount": 7}))
    parts: list[Part] = [TextPart("xin chào"), ImagePart(b"\x89PNG", "image/png")]
    res = make(post).generate_json(parts, SCHEMA, thinking="medium")
    assert res.data == {"a": 1}
    assert (res.input_tokens, res.output_tokens) == (11, 7)
    assert res.seconds >= 0
    url, headers, body, timeout = post.calls[0]
    assert url == (
        "https://aiplatform.googleapis.com/v1/projects/p1/locations/global/publishers/google/models/m1:generateContent"
    )
    assert headers == {"Content-Type": "application/json", "Authorization": "Bearer tok"}
    assert timeout == TIMEOUT_S
    sent = json.loads(body)
    assert sent["contents"] == [
        {
            "role": "user",
            "parts": [
                {"text": "xin chào"},
                {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b"\x89PNG").decode()}},
            ],
        }
    ]
    cfg = sent["generationConfig"]
    assert cfg["responseMimeType"] == "application/json"
    assert cfg["responseJsonSchema"] == SCHEMA
    assert cfg["thinkingConfig"] == {"thinkingLevel": "medium"}


def test_thought_parts_skipped_and_text_joined() -> None:
    post = FakePost(ok([{"text": "nghĩ...", "thought": True}, {"text": '{"a":'}, {"text": " 2}"}]))
    res = make(post).generate_json([TextPart("x")], SCHEMA)
    assert res.data == {"a": 2}
    assert (res.input_tokens, res.output_tokens) == (0, 0)
    assert json.loads(post.calls[0][2])["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


def test_retry_then_success_with_backoff() -> None:
    sleeps: list[float] = []
    post = FakePost((429, b"quota"), OSError("reset"), ok([{"text": "{}"}]))
    res = make(post, sleeps=sleeps).generate_json([TextPart("x")], SCHEMA)
    assert res.data == {}
    assert sleeps == [2.0, 4.0]
    assert len(post.calls) == 3


def test_retry_exhaustion_unavailable() -> None:
    post = FakePost(*[(500, b"boom")] * MAX_ATTEMPTS)
    with pytest.raises(GenAIError) as err:
        make(post).generate_json([TextPart("x")], SCHEMA)
    assert err.value.code == GENAI_UNAVAILABLE
    assert len(post.calls) == MAX_ATTEMPTS


@pytest.mark.parametrize("status", [401, 403])
def test_auth_status_no_retry(status: int) -> None:
    post = FakePost((status, b"denied"))
    with pytest.raises(GenAIError) as err:
        make(post).generate_json([TextPart("x")], SCHEMA)
    assert err.value.code == GENAI_AUTH
    assert len(post.calls) == 1


@pytest.mark.parametrize(
    "reply",
    [
        (400, b"bad schema"),
        (200, b"not json"),
        (200, b'{"candidates": []}'),
        (200, b'{"promptFeedback": {"blockReason": "SAFETY"}}'),
        ok([{"text": "không phải json"}]),
        ok([{"text": "[1, 2]"}]),
    ],
)
def test_bad_response(reply: tuple[int, bytes]) -> None:
    with pytest.raises(GenAIError) as err:
        make(FakePost(reply)).generate_json([TextPart("x")], SCHEMA)
    assert err.value.code == GENAI_BAD_RESPONSE


def test_token_refresh_when_expired_once() -> None:
    creds = FakeCreds(valid=False, bearer="new")
    post = FakePost(ok([{"text": "{}"}]), ok([{"text": "{}"}]))
    gem = make(post, creds)
    gem.generate_json([TextPart("x")], SCHEMA)
    gem.generate_json([TextPart("x")], SCHEMA)
    assert creds.refreshes == ["REQ"]
    assert post.calls[0][1]["Authorization"] == "Bearer new"


@pytest.mark.parametrize(
    ("fail", "code"),
    [
        (exceptions.RefreshError("no"), GENAI_AUTH),  # type: ignore[no-untyped-call]
        (exceptions.TransportError("down"), GENAI_UNAVAILABLE),  # type: ignore[no-untyped-call]
    ],
)
def test_token_refresh_failure(fail: Exception, code: str) -> None:
    with pytest.raises(GenAIError) as err:
        make(FakePost(), FakeCreds(valid=False, fail=fail)).generate_json([TextPart("x")], SCHEMA)
    assert err.value.code == code


def test_missing_token_is_auth() -> None:
    with pytest.raises(GenAIError) as err:
        make(FakePost(), FakeCreds(bearer=None)).generate_json([TextPart("x")], SCHEMA)
    assert err.value.code == GENAI_AUTH
    assert str(err.value) == "GENAI_AUTH: không có token"
    assert str(GenAIError(GENAI_AUTH)) == GENAI_AUTH


# --- lớp HTTP mặc định, trên máy chủ 127.0.0.1 -----------------------------------------------------


@pytest.fixture
def local_server() -> Iterator[str]:
    """Máy chủ HTTP cục bộ: `/ok` trả 200 + vọng lại thân, đường khác trả 503."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            code = 200 if self.path == "/ok" else 503
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_urllib_post_ok_and_http_error(local_server: str) -> None:
    assert urllib_post(f"{local_server}/ok", {"X": "1"}, b"abc", 5) == (200, b"abc")
    assert urllib_post(f"{local_server}/down", {}, b"zz", 5) == (503, b"zz")


def test_google_request_transport() -> None:
    from google.auth.transport.urllib3 import Request

    assert isinstance(_google_request(), Request)


# --- settings + create_genai -------------------------------------------------------------------------


def sa_json(project_id: str | None = "proj-sa") -> str:
    """Khoá service account giả (RSA sinh tại chỗ) — không bao giờ gọi mạng."""
    pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        .decode()
    )
    info: dict[str, str] = {
        "type": "service_account",
        "private_key_id": "k1",
        "private_key": pem,
        "client_email": "sa@proj.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    if project_id:
        info["project_id"] = project_id
    return json.dumps(info)


def settings(sa: str | None, project: str | None = None) -> GenAISettings:
    """`GenAISettings` dựng thẳng, không qua môi trường."""
    return GenAISettings(
        design_director_vertex_sa_json=SecretStr(sa) if sa is not None else None,
        design_director_vertex_project=project,
    )


@pytest.mark.parametrize("sa", [None, "", "   "])
def test_create_genai_none_without_key(sa: str | None) -> None:
    assert create_genai(settings(sa)) is None


def test_create_genai_builds_vertex() -> None:
    gem = create_genai(settings(sa_json()))
    assert isinstance(gem, VertexGemini)
    assert "/projects/proj-sa/" in gem._url
    assert "/models/gemini-3.8-flash:" in gem._url
    gem2 = create_genai(settings(sa_json(None), project="proj-env"))
    assert isinstance(gem2, VertexGemini)
    assert "/projects/proj-env/" in gem2._url


def test_create_genai_bad_key_is_auth() -> None:
    with pytest.raises(GenAIError) as err:
        create_genai(settings('{"project_id": "p"}'))
    assert err.value.code == GENAI_AUTH


@pytest.mark.parametrize("sa", ["{not json", "[1]", '{"type": "service_account"}'])
def test_settings_reject_bad_key(sa: str) -> None:
    with pytest.raises(ValidationError):
        settings(sa)


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESIGN_DIRECTOR_VERTEX_SA_JSON", '{"project_id": "p9"}')
    monkeypatch.setenv("DESIGN_DIRECTOR_MODEL", "m9")
    monkeypatch.delenv("DESIGN_DIRECTOR_VERTEX_PROJECT", raising=False)
    reset_genai_settings_cache()
    try:
        got = get_genai_settings()
        assert (got.project(), got.design_director_model) == ("p9", "m9")
        assert get_genai_settings() is got
    finally:
        reset_genai_settings_cache()


# --- FakeGenAI ---------------------------------------------------------------------------------------


def test_fake_genai_queue_and_calls(fake_genai: FakeGenAI) -> None:
    result = GenAIResult({"b": 1}, 3, 4, 0.5)
    fake_genai.queue({"a": 1}, result, GenAIError(GENAI_UNAVAILABLE))
    parts = [TextPart("x")]
    assert fake_genai.generate_json(parts, SCHEMA).data == {"a": 1}
    assert fake_genai.generate_json(parts, SCHEMA, thinking="medium") is result
    with pytest.raises(GenAIError):
        fake_genai.generate_json(parts, SCHEMA)
    with pytest.raises(AssertionError):
        fake_genai.generate_json(parts, SCHEMA)
    assert [c.thinking for c in fake_genai.calls] == ["low", "medium", "low", "low"]
    assert fake_genai.calls[0].parts == (TextPart("x"),)
