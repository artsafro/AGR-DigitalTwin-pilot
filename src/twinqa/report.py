# Ported from AGR src/dt_ai/core/models.py (sha256 7d257e4ecc00) on 2026-10-06;
# changes: only Finding/ValidationReport kept, as dataclasses (no pydantic, no BuildJob);
# findings grouped into V001-V017 stages from DELIVERY_VALIDATOR.yaml; `passed` is computed.
"""Validation findings and report (statuses per DELIVERY_VALIDATOR.yaml output.statuses).

A report is stamped with the standards digest and the code commit; recheck() reads a stored
report back as current / stale_standards / evidence_missing (issue #511).
"""
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from twinqa.io import digest

STATUSES = ("pass", "fail", "review", "not_run")
# Stage status = worst finding: fail > review > not_run > pass. A stage without findings is not_run.
RANK = {"pass": 0, "not_run": 1, "review": 2, "fail": 3}


@dataclass
class Finding:
    name: str
    status: str
    observed: str
    expected: str
    source_pdf_pages: list[int]
    evidence: str = ""
    conflicts: list[int] = field(default_factory=list)

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"Unknown status {self.status}")


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


@dataclass
class ValidationReport:
    profile: str
    target: str
    target_sha256: str
    source_sha256: str
    source_pdf_verified: bool
    stages: list[Stage]
    notes: list[str] = field(default_factory=list)
    standards_sha256: str = ""
    code_commit: str = ""

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
            stages.append(d)
        counts = {k: sum(s.status == k for s in self.machine_stages) for k in STATUSES}
        return {"profile": self.profile, "target": self.target, "target_sha256": self.target_sha256,
                "source_sha256": self.source_sha256, "source_pdf_verified": self.source_pdf_verified,
                "passed": self.passed, "exit_code": self.exit_code, "machine_stage_counts": counts,
                "manual_reviews_pending": [s.id for s in self.stages if s.gate == "manual_review"],
                "stages": stages, "notes": self.notes,
                "standards_sha256": self.standards_sha256, "code_commit": self.code_commit}

    def summary(self) -> str:
        lines = [f"Target:  {self.target}", f"SHA256:  {self.target_sha256}", f"Profile: {self.profile.upper()}",
                 f"Regulation sha256 {self.source_sha256[:12]}... "
                 + ("verified" if self.source_pdf_verified else "(PDF not found; hash from lock only)"),
                 f"Standards sha256 {self.standards_sha256[:12]}...; code {self.code_commit[:12] or 'unknown'}", ""]
        for s in self.stages:
            lines.append(f"{s.id} [{s.status.upper():7}] {s.gate:13} {s.check}")
            for f in s.findings:
                if f.status != "pass" or len(s.findings) <= 3:
                    tag = f" conflict #{','.join(map(str, f.conflicts))}" if f.conflicts else ""
                    lines.append(f"     - {f.status:7} {f.name}: {f.observed} (expected: {f.expected}; reg p.{','.join(map(str, f.source_pdf_pages))}{tag})")
        lines += [""] + [f"Note: {n}" for n in self.notes]
        verdict = "PASSED" if self.passed else "NOT PASSED"
        lines.append(f"Verdict: {verdict} (exit {self.exit_code}); manual checks "
                     f"{', '.join(s.id for s in self.stages if s.gate == 'manual_review')} still need signed review.")
        return "\n".join(lines)


SHA = re.compile(r"^[0-9a-f]{64}$")
# Exit codes of a recheck; "current" keeps the stored report's own exit code (0 / 1 / 2).
RECHECK_EXIT = {"stale_standards": 3, "evidence_missing": 4}


def code_commit(repo: Path = Path(__file__).resolve().parents[2]) -> str:
    """HEAD commit of the validator checkout, or "unknown" when git cannot tell."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    head = out.stdout.strip()
    return head if out.returncode == 0 and re.fullmatch(r"[0-9a-f]{40,64}", head) else "unknown"


def read_stored_report(data: bytes) -> dict:
    """Parse a stored validation report; anything that is not one raises ValueError naming the field."""
    try:
        old = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"old report is not JSON: {exc}") from None
    if not isinstance(old, dict) or "recheck_of" in old:
        raise ValueError("old report is not a validation report object")
    target, sha = old.get("target"), old.get("target_sha256")
    if not isinstance(target, str) or not target:
        raise ValueError("old report: target must be a non-empty string")
    if not isinstance(sha, str) or not SHA.match(sha):
        raise ValueError("old report: target_sha256 must be 64 lowercase hex")
    if type(old.get("passed")) is not bool:
        raise ValueError("old report: passed must be true or false")
    code = old.get("exit_code")
    if type(code) is not int or code not in (0, 1, 2):
        raise ValueError("old report: exit_code must be 0, 1 or 2")
    if old["passed"] != (code == 0):
        raise ValueError("old report: passed and exit_code disagree")
    if "standards_sha256" in old and not (isinstance(old["standards_sha256"], str)
                                          and SHA.match(old["standards_sha256"])):
        raise ValueError("old report: standards_sha256 must be 64 lowercase hex")
    return old


def recheck(old_bytes: bytes, old_path: str, standards_sha256: str, commit: str = "") -> dict:
    """Is the stored verdict still true now? current / stale_standards / evidence_missing.

    A relative target resolves against the current directory, as validate_package reads it.
    """
    old = read_stored_report(old_bytes)
    target = Path(old["target"])
    then_std = old.get("standards_sha256")
    reasons, now_sha = [], None
    if target.is_file():
        now_sha = digest(target.read_bytes())
        if now_sha != old["target_sha256"]:
            reasons.append(("evidence_missing", f"target changed: sha256 {now_sha[:12]} != {old['target_sha256'][:12]}"))
    else:
        reasons.append(("evidence_missing", f"target not found: {target}"))
    if then_std is None:
        reasons.append(("stale_standards", "old report has no standards digest"))
    elif then_std != standards_sha256:
        reasons.append(("stale_standards", f"standards changed: {standards_sha256[:12]} != {then_std[:12]}"))
    kinds = {k for k, _ in reasons}
    status = "evidence_missing" if "evidence_missing" in kinds else "stale_standards" if kinds else "current"
    current = status == "current"
    return {"recheck_of": old_path, "recheck_of_sha256": digest(old_bytes), "status": status,
            "reasons": [r for _, r in reasons], "profile": old.get("profile"), "target": old["target"],
            "target_sha256_then": old["target_sha256"], "target_sha256_now": now_sha,
            "standards_sha256_then": then_std, "standards_sha256_now": standards_sha256,
            "code_commit_then": old.get("code_commit"), "code_commit_now": commit,
            "exit_code_then": old["exit_code"],
            "passed": current and old["passed"],
            "exit_code": old["exit_code"] if current else RECHECK_EXIT[status]}


def recheck_summary(result: dict) -> str:
    """Text verdict; a stale or missing recheck names no stored verdict (it is not re-confirmed)."""
    lines = [f"Recheck of: {result['recheck_of']}", f"Target:     {result['target']}", f"Status:     {result['status']}"]
    lines += [f"Reason: {r}" for r in result["reasons"]]
    if result["status"] == "current":
        verdict = "PASSED" if result["passed"] else "NOT PASSED"
        lines.append(f"Verdict: stored verdict still holds: {verdict} (exit {result['exit_code']})")
    else:
        lines.append(f"Verdict: NOT CURRENT ({result['status']}); validate again (exit {result['exit_code']})")
    return "\n".join(lines)
