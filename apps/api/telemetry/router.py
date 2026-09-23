"""`GET /api/feature-flags` (#9), `POST /api/telemetry` (#37) (B7-01 [2]).

Hai router riêng, không lồng (`public_router` không phải con của `protected_router`,
BE-00 §2): #9 cần `Principal` nên đi qua `protected_router`; #37 công khai đi qua
`public_router`, và **chính router đó** mang `metrics_lifespan` — `apps/api/core/app.py`
gộp `lifespan` của từng router được dò ra, nên `/metrics` chỉ bật đúng một lần.
"""

from typing import Final

from fastapi import Depends
from starlette.requests import Request
from starlette.responses import Response

from apps.api.core.deps import CurrentPrincipal
from apps.api.core.origin import reject_foreign_origin
from apps.api.core.ratelimit import key_ip, rate_limit
from apps.api.core.routing import protected_router, public_router, route_options
from apps.api.telemetry.flags import resolve_feature_flags
from apps.api.telemetry.ingest import ingest
from apps.api.telemetry.metrics import FEATURE_FLAGS_READS_TOTAL
from apps.api.telemetry.schemas import FeatureFlagsOut
from apps.api.telemetry.settings import get_telemetry_settings
from packages.observability.exporter import metrics_lifespan

_settings: Final = get_telemetry_settings()

protected = protected_router(tags=["telemetry"])
public = public_router(tags=["telemetry"], lifespan=metrics_lifespan)
ROUTERS: Final = (protected, public)


@protected.get("/feature-flags", response_model=FeatureFlagsOut, status_code=200)
async def telemetry_read_feature_flags(principal: CurrentPrincipal) -> FeatureFlagsOut:
    """#9 — tính lại mỗi request theo vai của phiên; không cache giữa người dùng."""
    resolved = resolve_feature_flags(get_telemetry_settings().feature_flags, principal.role)
    FEATURE_FLAGS_READS_TOTAL.inc()
    return FeatureFlagsOut.model_validate(resolved)


@public.post(
    "/telemetry",
    status_code=204,
    dependencies=[
        Depends(
            rate_limit(
                "telemetry_ingest",
                limit=_settings.telemetry_rate_limit,
                window_s=_settings.telemetry_rate_window_s,
                key=key_ip,
                store="cache",
                on_error="open",
            )
        ),
        Depends(reject_foreign_origin),
    ],
)
@route_options(body_limit=_settings.telemetry_body_max_bytes, idempotency="off")
async def telemetry_ingest_batch(request: Request) -> Response:
    """#37 — đọc thân thô rồi gọi lõi `ingest`; không khai model thân (BE-00 §11)."""
    body = await request.body()
    ingest(body, request.headers.get("content-type"))
    return Response(status_code=204)
