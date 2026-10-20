"""Validate task-to-model gate evidence without executing or approving a model.

new-case: fail-closed procedure checklist and reproducible evidence inventory (#351).
Receipts are producer/user attestations, not a replacement for the geometry/checker tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

GATES = ("inputs", "parts", "operations", "budgets", "export_readback", "report", "visual", "checker")
INVARIANTS = ("open_borders_hidden", "no_see_through_hole", "no_visible_back_faces", "no_close_overlap")
Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Evidence(Strict):
    path: Text
    sha256: Digest


class Gate(Strict):
    status: Literal["pass", "fail", "review", "missing"]
    note: Text
    evidence: list[Evidence]

    @model_validator(mode="after")
    def passed_evidence(self):
        if self.status == "pass" and not self.evidence:
            raise ValueError("pass requires evidence")
        return self


class Gates(Strict):
    inputs: Gate
    parts: Gate
    operations: Gate
    budgets: Gate
    export_readback: Gate
    report: Gate
    visual: Gate
    checker: Gate


class Deviation(Strict):
    gate: Literal["inputs", "parts", "operations", "budgets", "export_readback", "report", "visual", "checker"]
    what_failed: Text
    what_was_tried: Text
    new_tool_written: Text  # explicit 'none' when no new tool was needed
    result: Text


class JobChecklist(Strict):
    schema_version: Literal["1.0.0"]
    job_id: Text
    run_id: Text
    synthetic: bool
    path: Literal["standard", "deviation"]
    inputs: list[Evidence] = Field(min_length=1)
    artifacts: list[Evidence]
    deviations: list[Deviation]
    gates: Gates

    @model_validator(mode="after")
    def deviation_path(self):
        if (self.path == "deviation") != bool(self.deviations):
            raise ValueError("deviation path requires a log; standard path has none")
        return self


def _resolve(root, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("evidence paths must be repository-relative POSIX paths")
    path = (root / path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("evidence escapes repository")
    return path


def _verify(root, ref):
    path = _resolve(root, ref.path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref.sha256:
        raise ValueError(f"hash mismatch: {ref.path}")
    return path


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys instead of silently accepting the last gate/claim."""


def _mapping(loader, node):
    pairs = loader.construct_pairs(node)
    result = {}
    for key, value in pairs:
        if not isinstance(key, str) or key in result:
            raise ValueError("duplicate or non-string mapping key")
        result[key] = value
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _read(path):
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    # YAML admits NaN/inf; no evidence object may silently carry them.
    json.dumps(value, allow_nan=False)
    return value


def _checks(receipt, required=()):
    checks = receipt.get("checks")
    if not isinstance(checks, dict) or not checks or not set(required) <= checks.keys():
        raise ValueError("missing required checks")
    if any(value != "pass" for value in checks.values()):
        raise ValueError("failed, review or unmeasured check")


def _receipt(root, ref, gate, job):
    value = _read(_verify(root, ref))
    if not isinstance(value, dict) or value.get("gate") != gate or value.get("run_id") != job.run_id:
        raise ValueError("wrong gate/run receipt")
    subjects = value.get("artifact_sha256")
    expected = [a.sha256 for a in job.artifacts]
    if not expected or subjects != expected:
        raise ValueError("receipt must bind the current exported artifacts in order")
    return value


def _gate(root, gate, entry, job):
    for ref in entry.evidence:
        _verify(root, ref)
    if gate == "inputs":
        for ref in job.inputs:
            _verify(root, ref)
        if entry.evidence != job.inputs:
            raise ValueError("inputs gate must record the full input inventory")
    elif gate == "parts":
        from dt_ai.parts.model import PartsList
        parts = PartsList.model_validate(_read(_verify(root, entry.evidence[0])))
        if parts.synthetic != job.synthetic or parts.status != "confirmed":
            raise ValueError("parts require matching scope and Gate 1 confirmation")
        if any(q.answer is None for q in parts.questions):
            raise ValueError("unanswered parts question")
    elif gate == "report":
        if not _verify(root, entry.evidence[0]).read_text(encoding="utf-8").strip():
            raise ValueError("empty report")
    else:
        for artifact in job.artifacts:
            _verify(root, artifact)
        receipt = _receipt(root, entry.evidence[0], gate, job)
        if gate == "operations":
            required = [f"{phase}.{name}" for phase in ("before", "after") for name in INVARIANTS]
            _checks(receipt, required)
            operations = receipt.get("operations")
            if not isinstance(operations, list) or not operations or not all(
                    isinstance(x, str) and x.strip() for x in operations):
                raise ValueError("record operations from src/dt_ai/ops or deviation tool")
        elif gate == "budgets":
            measurements = receipt.get("measurements")
            if not isinstance(measurements, list) or not measurements:
                raise ValueError("missing budget measurements")
            for row in measurements:
                value, limit = row["value"], row["limit"]
                if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in (value, limit)):
                    raise ValueError("invalid budget number")
                op = row["comparison"]
                if op not in ("le", "lt") or not (value <= limit if op == "le" else value < limit):
                    raise ValueError("budget exceeded/unsupported comparison")
                if not isinstance(row.get("rule"), str) or not row["rule"].strip():
                    raise ValueError("budget needs its rule/decision source")
        elif gate == "export_readback":
            _checks(receipt, ("topology", "uv", "materials", "transforms"))
            if receipt.get("clean_process") is not True:
                raise ValueError("export readback requires a clean process")
        elif gate == "visual":
            _checks(receipt, ("face_orientation", "album_overlay", "source_overlay", "material_legend", "sections"))
            if receipt.get("decision") != "approved" or receipt.get("actor_role") != "user":
                raise ValueError("visual approval belongs to the user")
            for field in ("actor", "date", "review_tool", "decision_reference"):
                if not isinstance(receipt.get(field), str) or not receipt[field].strip():
                    raise ValueError(f"visual receipt missing {field}")
            scope = "synthetic_fixture" if job.synthetic else "project"
            if receipt.get("scope") != scope:
                raise ValueError("wrong visual approval scope")
            _verify(root, Evidence.model_validate(receipt["sheet"]))
        elif gate == "checker":
            _checks(receipt)
            if receipt.get("tool") != "SINTEZ AGR Checker" or receipt.get("complete") is not True:
                raise ValueError("require complete SINTEZ checker receipt, not a component check")


def inspect_job(data, root):
    """Inventory every gate; malformed contracts and incomplete evidence never pass."""
    root = Path(root)
    rows = [{"gate": name, "status": "missing", "evidence_exists": [], "errors": []} for name in GATES]
    result = {"passed": False, "gates": rows, "errors": []}
    try:
        job = JobChecklist.model_validate(data)
    except ValidationError as exc:
        result["errors"] = [str(exc)]
        return result
    result.update(job_id=job.job_id, run_id=job.run_id, synthetic=job.synthetic)
    ready = True
    for row in rows:
        name = row["gate"]
        entry = getattr(job.gates, name)
        row.update(status=entry.status, note=entry.note)
        for ref in entry.evidence:
            exists = False
            try:
                _verify(root, ref)
                exists = True
            except (OSError, ValueError) as exc:
                row["errors"].append(str(exc))
            row["evidence_exists"].append({"path": ref.path, "verified": exists})
        if entry.status == "pass":
            try:
                _gate(root, name, entry, job)
            except (OSError, ValueError, TypeError, KeyError, IndexError, yaml.YAMLError) as exc:
                row["errors"].append(str(exc))
        if row["errors"]:
            row["status"] = "fail"
        row["ready"] = ready and row["status"] == "pass"
        ready = row["ready"]
    result["passed"] = ready
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        data = _read(args.job)
        # Refuse all existing outputs, including hardlinks/symlinks, before any writes.
        # Also protect missing evidence paths and parent traversal aliases.
        if args.output:
            protected = [args.job.resolve()]
            if isinstance(data, dict):
                refs = list(data.get("inputs", [])) + list(data.get("artifacts", []))
                for gate in (data.get("gates") or {}).values():
                    refs.extend(gate.get("evidence", []))
                protected.extend(_resolve(args.root, r["path"]) for r in refs)
                # A visual receipt names another input: its review sheet. Protect
                # that path even when the sheet is absent (not only existing files).
                visual = (data.get("gates") or {}).get("visual", {})
                for ref in visual.get("evidence", [])[:1]:
                    receipt = _read(_resolve(args.root, ref["path"]))
                    if isinstance(receipt, dict) and isinstance(receipt.get("sheet"), dict):
                        protected.append(_resolve(args.root, receipt["sheet"]["path"]))
            output = args.output.resolve()
            if args.output.exists() or args.output.is_symlink() or output in protected:
                raise ValueError("output aliases an input/evidence or already exists")
        result = inspect_job(data, args.root)
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
        print(text, end="")
        return 0 if result["passed"] else 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as exc:
        print(json.dumps({"passed": False, "errors": [str(exc)]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
