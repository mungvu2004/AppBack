"""Model dây của N21/N22 (B3-05 [2], [6] tầng 1): thân ghi strict, response `ProjectRuleConfig`.

Tầng 1 (Pydantic, gương zod) chỉ kiểm **mẫu** và kiểu; tập mã/khoá và khoảng giá trị là tầng 2 ở `service.py`
(danh mục). Khoá dict (`WALL-THICKNESS`, `wall.minThicknessMm`) giữ nguyên văn, không đổi camelCase.
"""

from typing import Annotated, Any, Final, Literal, Self

from pydantic import AllowInfNan, Field, StrictBool, StringConstraints, model_validator
from pydantic.types import Strict

from apps.api.core.wire import WireModel, WireRequest

RULE_CODE_PATTERN: Final = r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*$"
THRESHOLD_KEY_PATTERN: Final = r"^[a-zA-Z]+(\.[a-zA-Z0-9]+)+$"

type RuleCodeKey = Annotated[str, StringConstraints(pattern=RULE_CODE_PATTERN)]
type ThresholdKey = Annotated[str, StringConstraints(pattern=THRESHOLD_KEY_PATTERN)]
type ThresholdValue = Annotated[float, Strict(), AllowInfNan(False)]
type RuleSeverityName = Literal["critical", "warning", "suggestion"]


class RuleConfigOverrideIn(WireRequest):
    """Một `RuleOverride`: ≥ 1 khoá, không `null`; `thresholds` không rỗng (gương `RuleOverrideSchema`)."""

    enabled: StrictBool | None = None
    severity: RuleSeverityName | None = None
    thresholds: Annotated[dict[ThresholdKey, ThresholdValue], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def _non_empty_and_no_null(self) -> Self:
        """Override rỗng `{}` hay khoá mang `null` → `ValueError` (422 `VALIDATION`)."""
        if not self.model_fields_set:
            raise ValueError("override phải có ít nhất một khoá")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("khoá của override không được null")
        return self


class RuleConfigBodyIn(WireRequest):
    """Thân của N22: toàn bộ `overrides` (PUT thay thế)."""

    overrides: dict[RuleCodeKey, RuleConfigOverrideIn]


class RuleConfigWriteIn(WireRequest):
    """`{baseVersion, body}` của N22 (W20); thiếu `baseVersion` bị khung chặn 428 trước Pydantic."""

    base_version: Annotated[int, Field(strict=True, ge=0)]
    body: RuleConfigBodyIn


class RuleConfigOverrideOut(WireModel):
    """Override trả về: khoá vắng thì vắng (W2), còn `false` và `0` luôn có mặt."""

    enabled: bool | None = None
    severity: RuleSeverityName | None = None
    thresholds: dict[str, float] | None = None


class ProjectRuleConfigOut(WireModel):
    """`ProjectRuleConfig` = `{revision, overrides}`; chưa lưu → `{revision: 0, overrides: {}}`."""

    revision: int
    overrides: dict[str, RuleConfigOverrideOut]

    @classmethod
    def of(cls, revision: int, overrides: dict[str, dict[str, Any]]) -> Self:
        """Dựng từ `overrides` đã lọc theo danh mục (jsonb → model)."""
        return cls(revision=revision, overrides={c: RuleConfigOverrideOut(**o) for c, o in overrides.items()})
