"""`VertexGemini`: gọi Gemini trên Vertex AI bằng service account (AID-01).

Port hành vi `call()`/`endpoint()` của bản thử `F:/runs/design-director/director.py`:
đầu ra JSON theo `responseJsonSchema`, thử lại 429/500/503/504 lùi dần (2, 4, 8 s),
tối đa 4 lượt, timeout 120 s. Lớp HTTP (`Post`) và `sleep` tiêm được để test không cần mạng.
"""

import base64
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final, Protocol

from packages.genai.port import (
    GENAI_AUTH,
    GENAI_BAD_RESPONSE,
    GENAI_UNAVAILABLE,
    GenAI,
    GenAIError,
    GenAIResult,
    Part,
    TextPart,
    Thinking,
)
from packages.genai.settings import GenAISettings

SCOPE: Final = "https://www.googleapis.com/auth/cloud-platform"
ENDPOINT: Final = (
    "https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/publishers/google/models/{model}"
    ":generateContent"
)
TIMEOUT_S: Final = 120.0
MAX_ATTEMPTS: Final = 4
MAX_OUTPUT_TOKENS: Final = 8192
RETRY_STATUSES: Final = frozenset({429, 500, 503, 504})
_ERROR_BODY_CHARS: Final = 300

type Post = Callable[[str, Mapping[str, str], bytes, float], tuple[int, bytes]]


class Credentials(Protocol):
    """Phần của `google.oauth2.service_account.Credentials` mà lớp này dùng."""

    @property
    def valid(self) -> bool:
        """Token còn hạn."""
        ...

    @property
    def token(self) -> str | None:
        """Bearer token hiện tại."""
        ...

    def refresh(self, request: Any) -> None:
        """Lấy token mới qua transport `request` của google-auth."""
        ...


def urllib_post(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    """POST bằng `urllib.request`; mã HTTP lỗi trả về như kết quả, lỗi mạng ném `OSError`."""
    req = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")  # noqa: S310 — URL https cố định
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — URL https cố định
            return int(resp.status), bytes(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _google_request() -> Any:
    """Transport làm mới token của google-auth trên urllib3 (đã có trong lock)."""
    import urllib3
    from google.auth.transport.urllib3 import Request

    return Request(urllib3.PoolManager(timeout=urllib3.Timeout(total=30.0)))  # type: ignore[no-untyped-call]


def _part_json(part: Part) -> dict[str, Any]:
    """Một phần nội dung theo dạng dây của Gemini (`text` hoặc `inlineData` base64)."""
    if isinstance(part, TextPart):
        return {"text": part.text}
    return {"inlineData": {"mimeType": part.mime, "data": base64.b64encode(part.data).decode("ascii")}}


def request_body(parts: Sequence[Part], schema: Mapping[str, Any], thinking: Thinking) -> dict[str, Any]:
    """Thân `generateContent`: một lượt `user`, đầu ra JSON ép theo `schema`."""
    return {
        "contents": [{"role": "user", "parts": [_part_json(p) for p in parts]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": dict(schema),
            "thinkingConfig": {"thinkingLevel": thinking},
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
        },
    }


def parse_response(raw: bytes) -> tuple[dict[str, Any], int, int]:
    """Lấy JSON từ `candidates[0]` (bỏ phần `thought`) + token vào/ra; sai dạng → `GENAI_BAD_RESPONSE`."""
    try:
        res = json.loads(raw)
        parts = res["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise GenAIError(GENAI_BAD_RESPONSE, "không có candidate hoặc bị chặn") from None
    try:
        data = json.loads(text)
    except ValueError:
        raise GenAIError(GENAI_BAD_RESPONSE, "đầu ra không phải JSON") from None
    if not isinstance(data, dict):
        raise GenAIError(GENAI_BAD_RESPONSE, "đầu ra không phải đối tượng JSON")
    usage = res.get("usageMetadata") or {}
    return data, int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0))


class VertexGemini:
    """Bản `GenAI` thật; dùng chung được giữa các luồng (làm mới token có khoá)."""

    def __init__(
        self,
        credentials: Credentials,
        *,
        project: str,
        model: str,
        post: Post = urllib_post,
        sleep: Callable[[float], None] = time.sleep,
        google_request: Callable[[], Any] = _google_request,
    ) -> None:
        """Nhận credentials (đã gắn scope), dự án, mô hình; `post`/`sleep`/`google_request` tiêm cho test."""
        self._credentials = credentials
        self._url = ENDPOINT.format(project=project, model=model)
        self._post = post
        self._sleep = sleep
        self._google_request = google_request
        self._lock = threading.Lock()

    def _token(self) -> str:
        """Bearer token còn hạn; làm mới dưới khoá khi hết hạn. Lỗi làm mới → `GENAI_AUTH`/`GENAI_UNAVAILABLE`."""
        from google.auth import exceptions

        with self._lock:
            if not self._credentials.valid:
                try:
                    self._credentials.refresh(self._google_request())
                except exceptions.RefreshError:
                    raise GenAIError(GENAI_AUTH, "làm mới token thất bại") from None
                except exceptions.TransportError:
                    raise GenAIError(GENAI_UNAVAILABLE, "không tới được máy chủ token") from None
            token = self._credentials.token
        if not token:
            raise GenAIError(GENAI_AUTH, "không có token")
        return token

    def generate_json(
        self, parts: Sequence[Part], schema: Mapping[str, Any], *, thinking: Thinking = "low"
    ) -> GenAIResult:
        """Gọi `generateContent`, thử lại lỗi tạm thời; 401/403 → `GENAI_AUTH`, hết lượt → `GENAI_UNAVAILABLE`."""
        started = time.monotonic()
        body = json.dumps(request_body(parts, schema, thinking)).encode()
        last = ""
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                self._sleep(2.0 * 2 ** (attempt - 1))
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._token()}"}
            try:
                status, raw = self._post(self._url, headers, body, TIMEOUT_S)
            except OSError as exc:  # URLError, TimeoutError, ConnectionError
                last = f"lỗi mạng: {type(exc).__name__}"
                continue
            if status == 200:
                data, tokens_in, tokens_out = parse_response(raw)
                return GenAIResult(data, tokens_in, tokens_out, round(time.monotonic() - started, 3))
            detail = f"HTTP {status}: {raw[:_ERROR_BODY_CHARS].decode(errors='replace')}"
            if status in (401, 403):
                raise GenAIError(GENAI_AUTH, detail)
            if status not in RETRY_STATUSES:
                raise GenAIError(GENAI_BAD_RESPONSE, detail)
            last = detail
        raise GenAIError(GENAI_UNAVAILABLE, f"hết {MAX_ATTEMPTS} lượt; {last}")


def create_genai(settings: GenAISettings) -> GenAI | None:
    """`VertexGemini` từ cấu hình; `None` khi chưa có khoá (tính năng tắt)."""
    info = settings.service_account_info()
    project = settings.project()
    if info is None or project is None:
        return None
    from google.oauth2 import service_account

    try:
        creds = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            info, scopes=[SCOPE]
        )
    except (ValueError, KeyError):
        raise GenAIError(GENAI_AUTH, "khoá service account không hợp lệ") from None
    return VertexGemini(creds, project=project, model=settings.design_director_model)
