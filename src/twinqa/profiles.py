# Ported from AGR src/dt_ai/core/profiles.py (sha256 ed1290e45a51) on 2026-10-06;
# changes: standards dir is an argument (default: <repo>/standards), PDF hash checked
# only when the PDF is found, lock hashes are line-ending neutral, `conflicts:` blocks
# are excluded from traceability coverage and their paths are verified, Profiles wrapper.
"""Load the locked NPM/VPM profiles and the V001-V017 validator spec (standards/)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from twinqa.io import UniqueLoader, digest, json_bytes, read_json

FILES = ("NPM_STANDARD.yaml", "VPM_STANDARD.yaml", "DELIVERY_VALIDATOR.yaml")
NOT_RULES = {"standard", "version", "status", "source", "conflicts"}
DEFAULT_STANDARDS = Path(__file__).resolve().parents[2] / "standards"
# Files whose content decides a verdict; the lock keeps only pdf_sha256 (pdf_default_location is per machine).
DIGEST_FILES = (*FILES, "traceability.json")
LOCK = "source/source-lock.json"


def read_snapshot(folder: Path = DEFAULT_STANDARDS) -> dict[str, bytes]:
    """Bytes of the lock and every rule file, each read exactly once.

    Parsing, lock checks and the standards digest all use this one snapshot, so an edit made
    while a report is being produced cannot stamp rules other than the ones applied.
    A missing file raises OSError.
    """
    folder = Path(folder)
    return {name: (folder / name).read_bytes() for name in (LOCK, *DIGEST_FILES)}


def _text_sha(data: bytes) -> str:
    return digest(data.replace(b"\r\n", b"\n"))  # as io.digest_text: line-ending neutral


def snapshot_digest(snap: dict[str, bytes]) -> str:
    """SHA-256 over the rule files and the regulation hash of one snapshot; a lock without pdf_sha256 raises KeyError."""
    lock = read_json(snap[LOCK])
    stamp = {"pdf_sha256": lock["pdf_sha256"], "files": {n: _text_sha(snap[n]) for n in DIGEST_FILES}}
    return digest(json_bytes(stamp))


def standards_digest(folder: Path = DEFAULT_STANDARDS) -> str:
    """SHA-256 over the rule files and the regulation hash; line-ending neutral.

    Read straight from the files (no lock check), so an unlocked edit still moves the digest.
    """
    return snapshot_digest(read_snapshot(folder))


def snapshot_validator(snap: dict[str, bytes]) -> dict:
    """DELIVERY_VALIDATOR.yaml of a snapshot (no lock check: a recheck must read edited standards)."""
    return yaml.load(snap["DELIVERY_VALIDATOR.yaml"].decode("utf-8"), Loader=UniqueLoader)


def expected_stages(validator: dict, kind: str) -> list[tuple[str, str, str]]:
    """(id, gate, check) of every stage a report of profile `kind` carries, in report order."""
    return [(s["id"], s["gate"], s["check"]) for s in validator["stages"]
            if s["scope"] in ("both", kind.upper())]


@dataclass
class Profiles:
    npm: dict
    vpm: dict
    validator: dict
    pdf_sha256: str
    pdf_verified: bool  # False when the PDF file was not available to hash
    folder: Path = field(default=DEFAULT_STANDARDS)
    standards_sha256: str = ""  # snapshot_digest of the very bytes these rules were parsed from

    def profile(self, kind: str) -> dict:
        return {"npm": self.npm, "vpm": self.vpm}[kind.lower()]

    def stage(self, stage_id: str) -> dict:
        return next(s for s in self.validator["stages"] if s["id"] == stage_id)

    def conflict(self, kind: str, path: str) -> dict | None:
        """Annotation {ids, status, note} for a dotted field path, or None."""
        data = self.validator if kind == "validator" else self.profile(kind)
        return data.get("conflicts", {}).get(path)


def rule_paths(value, path):
    if isinstance(value, dict):
        for key, child in value.items():
            if key not in {"source_page", "source_pages", "schema_source_pages"}:
                yield from rule_paths(child, path + "." + str(key))
    else:
        yield path


def _has_path(data, dotted: str) -> bool:
    node = data
    for part in dotted.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and any(isinstance(x, dict) and x.get("id") == part for x in node):
            node = next(x for x in node if isinstance(x, dict) and x.get("id") == part)
        else:
            return False
    return True


def find_pdf(folder: Path, lock: dict) -> Path | None:
    candidates = [os.environ.get("TWINQA_REGULATION_PDF"), folder / "source" / lock["pdf_file"],
                  lock.get("pdf_default_location")]
    return next((Path(c) for c in candidates if c and Path(c).is_file()), None)


def load_profiles(folder: Path = DEFAULT_STANDARDS) -> Profiles:
    """Profiles are locked to the reviewed copies; changes require updating the lock."""
    folder = Path(folder)
    snap = read_snapshot(folder)
    lock = read_json(snap[LOCK])
    pdf = find_pdf(folder, lock)
    if pdf is not None and digest(pdf.read_bytes()) != lock["pdf_sha256"]:
        raise ValueError(f"Source PDF hash mismatch: {pdf}")
    data = {}
    for name in FILES:
        value = yaml.load(snap[name].decode("utf-8"), Loader=UniqueLoader)
        if not isinstance(value, dict) or value.get("source", {}).get("sha256") != lock["pdf_sha256"]:
            raise ValueError(f"Invalid source reference in {name}")
        if _text_sha(snap[name]) != lock["profiles"][name]:
            raise ValueError(f"Unreviewed profile change: {name}; update traceability, docs and the lock first")
        for conflict_path, note in value.get("conflicts", {}).items():
            if not _has_path(value, conflict_path):
                raise ValueError(f"{name}: conflicts entry for unknown field {conflict_path}")
            if note.get("status") not in {"review", "noted"} or not note.get("ids"):
                raise ValueError(f"{name}: conflicts entry {conflict_path} needs ids and status review|noted")
        data[name] = value
    if _text_sha(snap["traceability.json"]) != lock["traceability_sha256"]:
        raise ValueError("Unreviewed traceability change")
    trace = read_json(snap["traceability.json"])
    expected = {s["id"] for s in data["DELIVERY_VALIDATOR.yaml"]["stages"]}
    for kind in ("NPM", "VPM"):
        for group, value in data[f"{kind}_STANDARD.yaml"].items():
            if group not in NOT_RULES:
                expected.update(rule_paths(value, kind + "." + group))
    ids = [row["rule"] for row in trace]
    if set(ids) != expected or len(ids) != len(expected):
        raise ValueError("Traceability does not cover each profile rule exactly once")
    for row in trace:
        if not row["pages"] or any(type(p) is not int or not 1 <= p <= lock["pdf_pages"] for p in row["pages"]):
            raise ValueError(f"Missing or invalid page evidence: {row['rule']}")
        if row["source_sha256"] != lock["pdf_sha256"]:
            raise ValueError(f"Stale traceability source: {row['rule']}")
    return Profiles(npm=data["NPM_STANDARD.yaml"], vpm=data["VPM_STANDARD.yaml"],
                    validator=data["DELIVERY_VALIDATOR.yaml"], pdf_sha256=lock["pdf_sha256"],
                    pdf_verified=pdf is not None, folder=folder, standards_sha256=snapshot_digest(snap))
