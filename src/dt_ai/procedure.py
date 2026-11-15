"""Validate task-to-model gate evidence without executing or approving a model.

new-case: fail-closed procedure checklist and reproducible evidence inventory (#351).
Receipts are producer/user attestations, not a replacement for the geometry/checker tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

GATES = ("inputs", "parts", "operations", "budgets", "export_readback", "report", "visual", "checker")
INVARIANTS = ("open_borders_hidden", "no_see_through_hole", "no_visible_back_faces", "no_close_overlap",
              "quad_dominance", "texel_ready")
# Source files are the only evidence eligible for a pinned ``commit`` (immutable revision).
SOURCE_SUFFIXES = (".py", ".cs", ".ps1", ".ms", ".js", ".ts")
# Gate roles that may legitimately carry source code; a ``commit`` is rejected anywhere else.
SOURCE_ROLES = ("inputs", "parts", "operations")
# Why a not-yet-passed gate is parked (#1204): the user, a live 3ds Max, or the visual gate.
WAITS = ("user", "max", "visual")
Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
# Full object id only (SHA-1 or SHA-256 repositories): refs and abbreviations are mutable/ambiguous.
ObjectId = Annotated[str, Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")]
# A repo-relative JSON listing customer sources that live outside the repository (#1202).
EXTERNAL_MANIFEST = "external-inputs/1"
_SHA256 = re.compile(r"[a-f0-9]{64}")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Evidence(Strict):
    """A hashed reference. ``commit`` pins source evidence to an immutable revision (#387):
    the ``inputs`` inventory (any path), or a supplementary source-suffixed reference in the
    ``parts``/``operations`` roles; its sha256 is checked against the blob at that commit, so
    later edits of the live file do not invalidate it. The primary parsed contract of a
    ``pass`` ``parts`` gate (the PartsList) and the primary receipt of a ``pass`` ``operations``
    gate are generated semantic roles and always reject ``commit``, regardless of suffix.
    Generated artifacts, receipts, reports and visual sheets are always hashed from the working
    tree and reject ``commit``. ``manifest: external-inputs/1`` (inputs role only, #1202) marks
    the file as an external-input manifest: the walker re-hashes every absolute path it lists and
    reports each row as ``equal``, ``mismatch`` (an error) or ``unreachable`` (never a pass)."""
    path: Text
    sha256: Digest
    commit: ObjectId | None = None
    manifest: Literal["external-inputs/1"] | None = None


class Gate(Strict):
    """``waits`` (optional, #1204) names what a non-passed gate is parked on: ``user`` (a user
    decision or review), ``max`` (a live 3ds Max step) or ``visual`` (the visual gate first).
    It is counted by the walker and never makes a gate ready; a ``pass`` gate waits for nothing.
    A ``missing`` (not started) gate may omit ``note`` and ``evidence`` (#1310, F17); any other
    status needs a ``note``."""
    status: Literal["pass", "fail", "review", "missing"]
    note: Text | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    waits: Literal["user", "max", "visual"] | None = None

    @model_validator(mode="after")
    def passed_evidence(self):
        if self.note is None and self.status != "missing":
            raise ValueError(f"a {self.status} gate requires a note")
        if self.status == "pass" and not self.evidence:
            raise ValueError("pass requires evidence")
        if self.status == "pass" and self.waits is not None:
            raise ValueError("a pass gate cannot declare waits")
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
        if any(ref.manifest for ref in self.artifacts):
            raise ValueError("an external-inputs manifest is allowed only in the inputs role")
        return self


def _resolve(root, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("evidence paths must be repository-relative POSIX paths")
    path = (root / path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("evidence escapes repository")
    return path


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=60)


def _pinned_blob(root, ref):
    """Bytes of ``ref.path`` at ``ref.commit``; the commit must be in the history of HEAD."""
    if _git(root, "cat-file", "-e", f"{ref.commit}^{{commit}}").returncode != 0:
        raise ValueError(f"pinned commit not found: {ref.path}@{ref.commit}")
    if _git(root, "merge-base", "--is-ancestor", ref.commit, "HEAD").returncode != 0:
        raise ValueError(f"pinned commit is not in the history of HEAD: {ref.path}@{ref.commit}")
    blob = _git(root, "cat-file", "blob", f"{ref.commit}:./{ref.path}")
    if blob.returncode != 0:
        raise ValueError(f"path absent at pinned commit: {ref.path}@{ref.commit}")
    return blob.stdout


def _verify(root, ref, role, *, generated=False):
    """Return the verified bytes; callers parse these, never a second read of the path.

    ``commit`` (pinned historical lookup) is honored only for source evidence: the
    ``inputs`` role is source inventory (any path), while ``parts`` and ``operations``
    honor it only for a supplementary source-suffixed reference. ``generated=True`` marks
    the primary parsed contract of a ``pass`` ``parts`` gate or the primary receipt of a
    ``pass`` ``operations`` gate; those reject ``commit`` regardless of suffix, so current
    bytes stay mandatory. Generated artifacts, receipts, reports and visual sheets are
    always hashed from the working tree and reject ``commit``."""
    path = _resolve(root, ref.path)
    if ref.commit:
        if generated:
            raise ValueError(f"pinned commit not allowed for generated {role} evidence: {ref.path}")
        if role not in SOURCE_ROLES:
            raise ValueError(f"pinned commit not allowed for {role} evidence: {ref.path}")
        if role != "inputs" and Path(ref.path).suffix.lower() not in SOURCE_SUFFIXES:
            raise ValueError(f"pinned commit not allowed for non-source evidence: {ref.path}")
        data = _pinned_blob(root, ref)
    else:
        data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != ref.sha256:
        raise ValueError(f"hash mismatch: {ref.path}")
    return data


def _reject_constant(name):
    raise ValueError(f"nonfinite value {name}")


def parse_external_manifest(data):
    """Validated ``[{path, sha256}]`` rows of an ``external-inputs/1`` manifest.

    Fail-closed: not JSON, NaN/inf, a wrong tag, an empty or non-list ``files``, a row
    without an absolute path or a lowercase SHA-256, or two rows naming the same file
    raise ``ValueError`` naming the defect. Extra keys (sheet, role, location...) are allowed."""
    def bad(why):
        return ValueError(f"malformed external-inputs manifest: {why}")
    try:
        value = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError are ValueErrors
        raise bad(f"not JSON ({exc})") from None
    if not isinstance(value, dict) or value.get("manifest") != EXTERNAL_MANIFEST:
        raise bad(f"manifest must be {EXTERNAL_MANIFEST!r}")
    files = value.get("files")
    if not isinstance(files, list) or not files:
        raise bad("files must be a nonempty list")
    rows, seen = [], {}
    for i, row in enumerate(files):
        if not isinstance(row, dict):
            raise bad(f"files[{i}] is not an object")
        path, digest = row.get("path"), row.get("sha256")
        if not isinstance(path, str) or not path.strip():
            raise bad(f"files[{i}].path is empty")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise bad(f"files[{i}].sha256 is not a lowercase SHA-256: {path}")
        if not (PureWindowsPath(path).is_absolute() or PurePosixPath(path).is_absolute()):
            raise bad(f"files[{i}].path is not absolute (repo files are direct inputs): {path}")
        native = Path(path)
        key = os.path.normcase(str(native.resolve()) if native.is_absolute() else os.path.normpath(path))
        if key in seen:
            raise bad(f"files[{i}] repeats files[{seen[key]}]: {path}")
        seen[key] = i
        rows.append({"path": path, "sha256": digest})
    return rows


def _is_manifest(data):
    try:
        value = json.loads(data.decode("utf-8"))
    except ValueError:
        return False
    return isinstance(value, dict) and str(value.get("manifest", "")).startswith("external-inputs")


def _hash_external(row):
    """Re-hash one manifest row: ``equal``, ``mismatch``, ``unreachable`` or ``error``."""
    path = Path(row["path"])
    if not path.is_absolute():
        return {**row, "status": "unreachable", "reason": "absolute path of another OS"}
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        return {**row, "status": "unreachable", "reason": type(exc).__name__}
    if not stat.S_ISREG(mode):
        return {**row, "status": "error", "reason": "not a regular file"}
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        return {**row, "status": "unreachable", "reason": type(exc).__name__}
    actual = digest.hexdigest()
    if actual == row["sha256"]:
        return {**row, "status": "equal"}
    return {**row, "status": "mismatch", "actual_sha256": actual}


def _external_inputs(root, job, errors):
    """Expand every declared manifest of the inputs role; append defects to ``errors``."""
    refs, rows = [], []
    for ref in [*job.inputs, *job.gates.inputs.evidence]:
        if ref not in refs:
            refs.append(ref)
    for ref in refs:
        try:
            data = _verify(root, ref, "inputs")
        except (OSError, ValueError) as exc:
            if str(exc) not in errors:
                errors.append(str(exc))
            continue
        if not ref.manifest:
            if _is_manifest(data):
                errors.append(f"undeclared external-inputs manifest: {ref.path} (add manifest: {EXTERNAL_MANIFEST})")
            continue
        try:
            listed = parse_external_manifest(data)
        except ValueError as exc:
            errors.append(f"{ref.path}: {exc}")
            continue
        for row in listed:
            result = {"manifest": ref.path, **_hash_external(row)}
            rows.append(result)
            if result["status"] == "mismatch":
                errors.append(f"external input hash mismatch: {row['path']} (manifest {ref.path})")
            elif result["status"] == "error":
                errors.append(f"external input is {result['reason']}: {row['path']} (manifest {ref.path})")
    return rows


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


def _read(source):
    text = source.decode("utf-8") if isinstance(source, bytes) else source.read_text(encoding="utf-8")
    value = yaml.load(text, Loader=UniqueLoader)
    # YAML admits NaN/inf; no evidence object may silently carry them.
    json.dumps(value, allow_nan=False)
    return value


def _checks(receipt, required=()):
    checks = receipt.get("checks")
    if not isinstance(checks, dict) or not checks or not set(required) <= checks.keys():
        raise ValueError("missing required checks")
    if any(not isinstance(key, str) or not key.strip() for key in checks):
        raise ValueError("check IDs must be nonempty strings")
    if any(value != "pass" for value in checks.values()):
        raise ValueError("failed, review or unmeasured check")


def _receipt(root, ref, gate, job):
    value = _read(_verify(root, ref, gate, generated=(gate == "operations")))
    if not isinstance(value, dict) or value.get("gate") != gate or value.get("run_id") != job.run_id:
        raise ValueError("wrong gate/run receipt")
    subjects = value.get("artifact_sha256")
    expected = [a.sha256 for a in job.artifacts]
    if not expected or subjects != expected:
        raise ValueError("receipt must bind the current exported artifacts in order")
    if value.get("input_evidence") != [ref.model_dump(exclude_none=True) for ref in job.inputs]:
        raise ValueError("receipt must bind the exact current input inventory in order")
    parts = job.gates.parts.evidence
    if not parts or value.get("parts_sha256") != parts[0].sha256:
        raise ValueError("receipt must bind the current confirmed parts identity")
    return value


def _gate(root, gate, entry, job):
    for ref in entry.evidence:
        _verify(root, ref, gate)
    if gate == "inputs":
        for ref in job.inputs:
            _verify(root, ref, "inputs")
        if entry.evidence != job.inputs:
            raise ValueError("inputs gate must record the full input inventory")
    elif gate == "parts":
        # Use the public contract facade; importing parts first hits its legacy
        # cycle through core.models in a fresh CLI process (owned separately by #354).
        from dt_ai.core.models import PartsList
        parts = PartsList.model_validate(_read(_verify(root, entry.evidence[0], "parts", generated=True)))
        if parts.synthetic != job.synthetic or parts.status != "confirmed":
            raise ValueError("parts require matching scope and Gate 1 confirmation")
        if (parts.gate1 is None or parts.gate1.ref is None
                or parts.gate1.scope != ("synthetic_fixture" if job.synthetic else "project")
                or parts.gate1.parts_sha256 != parts.approval_sha256()):
            raise ValueError("Gate 1 requires matching scope, an answer ref and matching PartsList approval_sha256")
        if any(q.answer is None for q in parts.questions):
            raise ValueError("unanswered parts question")
    elif gate == "report":
        if not _verify(root, entry.evidence[0], "report").decode("utf-8").strip():
            raise ValueError("empty report")
    else:
        for artifact in job.artifacts:
            _verify(root, artifact, "artifact")
        receipt = _receipt(root, entry.evidence[0], gate, job)
        if gate == "operations":
            required = [f"{phase}.{name}" for phase in ("before", "after") for name in INVARIANTS]
            _checks(receipt, required)
            operations = receipt.get("operations")
            if not isinstance(operations, list) or not operations or not all(
                    isinstance(x, str) and x.strip() for x in operations):
                raise ValueError("record operations from src/dt_ai/ops or deviation tool")
        elif gate == "budgets":
            # Measurements are mandatory; additional declared checks cannot be ignored.
            if "checks" in receipt:
                _checks(receipt)
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
            sheet = Evidence.model_validate(receipt["sheet"])
            if sheet.manifest:
                raise ValueError("an external-inputs manifest is allowed only in the inputs role")
            _verify(root, sheet, "sheet")
        elif gate == "checker":
            _checks(receipt)
            if receipt.get("tool") != "SINTEZ AGR Checker" or receipt.get("complete") is not True:
                raise ValueError("require complete SINTEZ checker receipt, not a component check")


def _invalid(data, exc, rows, result):
    """Report a schema failure per field (#1310, F17): every error names its location, an
    error under ``gates.<gate>`` marks that gate ``fail``, and a gate whose own entry is valid
    keeps its declared status. Nothing is ready: the checklist as a whole is invalid."""
    gates = data.get("gates") if isinstance(data, dict) else None
    for error in exc.errors():
        loc = ".".join(str(part) for part in error["loc"]) or "<root>"
        message = f"{loc}: {error['msg']}"
        result["errors"].append(message)
        if len(error["loc"]) > 1 and error["loc"][0] == "gates" and error["loc"][1] in GATES:
            row = rows[GATES.index(error["loc"][1])]
            row["errors"].append(message)
    for row in rows:
        raw = gates.get(row["gate"]) if isinstance(gates, dict) else None
        if row["errors"]:
            row["status"] = "fail"
        elif raw is not None:
            try:
                entry = Gate.model_validate(raw)
            except ValidationError:
                continue
            row.update(status=entry.status, note=entry.note, waits=entry.waits)
            if entry.waits:
                result["waits"][entry.waits] += 1
        row["ready"] = False
    return result


def _duplicated_inputs(root, refs):
    """Paths listed more than once (after resolving ``./`` and case aliases; #1310, F20)."""
    seen, repeated = {}, []
    for ref in refs:
        try:
            key = os.path.normcase(str(_resolve(root, ref.path)))
        except ValueError:
            key = ref.path  # the per-reference check reports the bad path itself
        if key not in seen:
            seen[key] = ref.path
        elif key not in repeated:
            repeated.append(key)
            yield ref.path if ref.path == seen[key] else f"{seen[key]} = {ref.path}"


def inspect_job(data, root):
    """Inventory every gate; malformed contracts and incomplete evidence never pass."""
    root = Path(root)
    rows = [{"gate": name, "status": "missing", "waits": None, "evidence_exists": [], "errors": []}
            for name in GATES]
    result = {"passed": False, "gates": rows, "waits": dict.fromkeys(WAITS, 0), "errors": []}
    try:
        job = JobChecklist.model_validate(data)
    except ValidationError as exc:
        return _invalid(data, exc, rows, result)
    result.update(job_id=job.job_id, run_id=job.run_id, synthetic=job.synthetic)
    ready = True
    for row in rows:
        name = row["gate"]
        entry = getattr(job.gates, name)
        row.update(status=entry.status, note=entry.note, waits=entry.waits)
        if entry.waits:
            result["waits"][entry.waits] += 1
        primary_generated = name in ("parts", "operations") and entry.status == "pass"
        for i, ref in enumerate(entry.evidence):
            exists = False
            try:
                _verify(root, ref, name, generated=(primary_generated and i == 0))
                exists = True
            except (OSError, ValueError) as exc:
                row["errors"].append(str(exc))
            row["evidence_exists"].append({"path": ref.path, "verified": exists})
            if ref.manifest and name != "inputs":
                row["errors"].append(f"an external-inputs manifest is allowed only in the inputs role: {ref.path}")
        if entry.status == "pass":
            try:
                _gate(root, name, entry, job)
            except (OSError, ValueError, TypeError, KeyError, IndexError, yaml.YAMLError) as exc:
                row["errors"].append(str(exc))
        if name == "inputs":
            for role, refs in (("inputs", job.inputs), ("gates.inputs.evidence", entry.evidence)):
                for path in _duplicated_inputs(root, refs):
                    row["errors"].append(f"duplicated {role} path: {path}")
            external = _external_inputs(root, job, row["errors"])
            unreachable = sum(r["status"] == "unreachable" for r in external)
            row.update(external_inputs=external, unreachable=unreachable)
            # Unverifiable on this machine is neither a hash failure nor a pass.
            if unreachable and row["status"] == "pass":
                row["status"] = "review"
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
                # Paths listed by a declared external-inputs manifest are inputs too.
                for ref in refs:
                    if isinstance(ref, dict) and ref.get("manifest"):
                        try:
                            listed = parse_external_manifest(_resolve(args.root, ref["path"]).read_bytes())
                        except (OSError, ValueError):
                            continue  # the walk itself reports the defect
                        protected.extend(Path(r["path"]).resolve() for r in listed
                                         if Path(r["path"]).is_absolute())
            output = args.output.resolve()
            if args.output.exists() or args.output.is_symlink() or output in protected:
                raise ValueError("output aliases an input/evidence or already exists")
        result = inspect_job(data, args.root)
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # Binary mode: LF on every OS, so the hash survives .gitattributes eol=lf (G15).
            with args.output.open("xb") as stream:
                stream.write(text.encode("utf-8"))
        _emit(text)
        return 0 if result["passed"] else 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as exc:
        _emit(json.dumps({"passed": False, "errors": [str(exc)]}) + "\n")
        return 1


def _emit(text):
    """Print LF-only even on Windows, so a redirected walk is byte-equal to ``--output``."""
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        print(text, end="")
        return
    sys.stdout.flush()
    buffer.write(text.encode("utf-8"))
    buffer.flush()


if __name__ == "__main__":
    raise SystemExit(main())
