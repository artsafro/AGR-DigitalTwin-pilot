# Ported from AGR src/dt_ai/core/models.py (sha256 7d257e4ecc00) on 2026-10-06;
# changes: only Finding/ValidationReport kept, as dataclasses (no pydantic, no BuildJob);
# findings grouped into V001-V017 stages from DELIVERY_VALIDATOR.yaml; `passed` is computed.
"""Validation findings and report (statuses per DELIVERY_VALIDATOR.yaml output.statuses)."""
import math
from dataclasses import asdict, dataclass, field

STATUSES = ("pass", "fail", "review", "not_run")
# Stage status = worst finding: fail > review > not_run > pass. A stage without findings is not_run.
RANK = {"pass": 0, "not_run": 1, "review": 2, "fail": 3}
# A pass this close to its threshold is called out in summary(); it is still a pass.
NEAR_THRESHOLD_MARGIN = 0.05
_FINDING_KEYS = {
    "name", "status", "observed", "expected", "source_pdf_pages",
    "evidence", "conflicts", "measured", "threshold", "margin", "data",
}
_FINDING_REQUIRED = ("name", "status", "observed", "expected", "source_pdf_pages")
_STAGE_KEYS = {"id", "check", "gate", "source_pdf_pages", "findings", "status"}
_STAGE_REQUIRED = ("id", "check", "gate", "source_pdf_pages", "findings")
_REPORT_KEYS = {
    "profile", "target", "target_sha256", "source_sha256", "source_pdf_verified",
    "passed", "exit_code", "machine_stage_counts", "manual_reviews_pending", "stages", "notes",
}
_REPORT_REQUIRED = ("profile", "target", "target_sha256", "source_sha256", "source_pdf_verified", "stages")


def _real(value):
    """Finite int or float, or None when the value is not a number.

    NaN and infinities are errors: they must not become a margin that looks safe.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        raise ValueError(f"non-finite value {value!r}")
    return value


def signed_margin(measured, threshold, bound):
    """Signed margin of a numeric check. Positive means on the safe side.

    ``min`` (measured must be >= threshold): (measured - threshold) / threshold.
    ``max`` (measured must be <= threshold): (threshold - measured) / threshold.
    None when measured or threshold is not numeric, or when threshold is 0.
    Any other bound is an error that names it.
    A finite pair whose division overflows to a non-finite result is an arithmetic error.
    """
    if not isinstance(bound, str) or bound not in ("min", "max"):
        raise ValueError(f"unmapped bound {bound!r}; expected 'min' or 'max'")
    measured_n = _real(measured)
    threshold_n = _real(threshold)
    if measured_n is None or threshold_n is None or threshold_n == 0:
        return None
    if bound == "min":
        result = (measured_n - threshold_n) / threshold_n
    else:
        result = (threshold_n - measured_n) / threshold_n
    if not math.isfinite(result):
        raise ValueError(f"non-finite margin {result!r}")
    return result


def _mapping(data, allowed, label):
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be an object")
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"unmapped {label} key {unknown[0]!r}")


def _require(data, required, label):
    for key in required:
        if key not in data:
            raise ValueError(f"partial {label} missing {key!r}")


def _optional_mapping(data, key):
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping, got {type(value).__name__}")
    return dict(value)


def _optional_number(data, key):
    if key not in data or data[key] is None:
        return None
    value = _real(data[key])
    if value is None:
        raise ValueError(f"non-finite {key} {data[key]!r}")
    return value


def _format_measure(value) -> str:
    number = _real(value)
    if number is None:
        return "None"
    return f"{number:.6g}"


def _near_threshold_line(finding) -> str | None:
    margin = finding.margin
    if finding.status != "pass":
        return None
    number = _real(margin)
    if number is None or number < 0 or number >= NEAR_THRESHOLD_MARGIN:
        return None
    return (f"near threshold: {finding.name} margin {_format_measure(number)} "
            f"(measured {_format_measure(finding.measured)}, threshold {_format_measure(finding.threshold)})")


@dataclass
class Finding:
    name: str
    status: str
    observed: str
    expected: str
    source_pdf_pages: list[int]
    evidence: str = ""
    conflicts: list[int] = field(default_factory=list)
    measured: float | None = None
    threshold: float | None = None
    margin: float | None = None
    data: dict = field(default_factory=dict)  # operands behind a computed limit (e.g. V003 Ground area band)

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"Unknown status {self.status}")

    @classmethod
    def from_dict(cls, data: dict) -> "Finding":
        """Load one finding. Missing measured/threshold/margin mean an old report."""
        _mapping(data, _FINDING_KEYS, "finding")
        _require(data, _FINDING_REQUIRED, "finding")
        return cls(
            name=data["name"],
            status=data["status"],
            observed=data["observed"],
            expected=data["expected"],
            source_pdf_pages=list(data["source_pdf_pages"]),
            evidence=data.get("evidence", ""),
            conflicts=list(data.get("conflicts", [])),
            measured=_optional_number(data, "measured"),
            threshold=_optional_number(data, "threshold"),
            margin=_optional_number(data, "margin"),
            data=_optional_mapping(data, "data"),
        )


@dataclass
class Stage:
    id: str
    check: str
    gate: str  # blocking | manual_review
    source_pdf_pages: list[int]
    findings: list[Finding] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.findings:
            return "not_run"
        return max((f.status for f in self.findings), key=RANK.__getitem__)

    @classmethod
    def from_dict(cls, data: dict) -> "Stage":
        _mapping(data, _STAGE_KEYS, "stage")
        _require(data, _STAGE_REQUIRED, "stage")
        return cls(
            id=data["id"],
            check=data["check"],
            gate=data["gate"],
            source_pdf_pages=list(data["source_pdf_pages"]),
            findings=[Finding.from_dict(item) for item in data["findings"]],
        )


@dataclass
class ValidationReport:
    profile: str
    target: str
    target_sha256: str
    source_sha256: str
    source_pdf_verified: bool
    stages: list[Stage]
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationReport":
        """Load a report. Derived keys (passed, exit_code, stage status) are recomputed.

        Findings written before measured/threshold/margin existed load with those fields None.
        """
        _mapping(data, _REPORT_KEYS, "report")
        _require(data, _REPORT_REQUIRED, "report")
        return cls(
            profile=data["profile"],
            target=data["target"],
            target_sha256=data["target_sha256"],
            source_sha256=data["source_sha256"],
            source_pdf_verified=data["source_pdf_verified"],
            stages=[Stage.from_dict(item) for item in data["stages"]],
            notes=list(data.get("notes", [])),
        )

    @property
    def machine_stages(self):
        return [s for s in self.stages if s.gate == "blocking"]

    @property
    def passed(self) -> bool:
        """True only if every mandatory machine check ran and passed (no fail/review/not_run)."""
        return bool(self.machine_stages) and all(s.status == "pass" for s in self.machine_stages)

    @property
    def exit_code(self) -> int:
        if self.passed:
            return 0
        if any(f.status == "fail" for s in self.stages for f in s.findings):
            return 1
        return 2

    def to_dict(self) -> dict:
        stages = []
        for s in self.stages:
            d = asdict(s)
            d["status"] = s.status
            for finding in d["findings"]:
                if not finding.get("data"):  # keep the #462 report shape; data appears only when it holds operands
                    finding.pop("data", None)
            stages.append(d)
        counts = {k: sum(s.status == k for s in self.machine_stages) for k in STATUSES}
        return {"profile": self.profile, "target": self.target, "target_sha256": self.target_sha256,
                "source_sha256": self.source_sha256, "source_pdf_verified": self.source_pdf_verified,
                "passed": self.passed, "exit_code": self.exit_code, "machine_stage_counts": counts,
                "manual_reviews_pending": [s.id for s in self.stages if s.gate == "manual_review"],
                "stages": stages, "notes": self.notes}

    def summary(self) -> str:
        lines = [f"Target:  {self.target}", f"SHA256:  {self.target_sha256}", f"Profile: {self.profile.upper()}",
                 f"Regulation sha256 {self.source_sha256[:12]}... "
                 + ("verified" if self.source_pdf_verified else "(PDF not found; hash from lock only)"), ""]
        for s in self.stages:
            lines.append(f"{s.id} [{s.status.upper():7}] {s.gate:13} {s.check}")
            for f in s.findings:
                if f.status != "pass" or len(s.findings) <= 3:
                    tag = f" conflict #{','.join(map(str, f.conflicts))}" if f.conflicts else ""
                    lines.append(f"     - {f.status:7} {f.name}: {f.observed} (expected: {f.expected}; reg p.{','.join(map(str, f.source_pdf_pages))}{tag})")
        lines += [""] + [f"Note: {n}" for n in self.notes]
        for stage in self.stages:
            for finding in stage.findings:
                near = _near_threshold_line(finding)
                if near:
                    lines.append(near)
        verdict = "PASSED" if self.passed else "NOT PASSED"
        lines.append(f"Verdict: {verdict} (exit {self.exit_code}); manual checks "
                     f"{', '.join(s.id for s in self.stages if s.gate == 'manual_review')} still need signed review.")
        return "\n".join(lines)
