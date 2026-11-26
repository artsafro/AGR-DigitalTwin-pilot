"""Read-only source binding replay for #126; never opens model keys."""

import hashlib
import json
import os
import re
import statistics
import subprocess
import time
from pathlib import Path

PIN = "d77c3249d972904f5c397aeb48d81c1c43a651e3"
BANK = "016aab0c7ae3496643fdfdc69582be8e6cb877e2f62d2ff19ebef23a7be36635"
LEDGER = "230eace1a0a434cb25091f449760d3895d5b7d169086a2f2ba049db88a8496a7"
INBOX = "C:/Users/artsafro/Desktop/!3D viz/!Weltbau/10_Сокольники/inbox"
SOURCES = {
    "revit_fbx": ("СОКОЛЬНИКИ_УВК1000_АР_R23_вар1.fbx", "feaae5271831802b"),
    "facade_pdf": ("СОКОЛЬНИКИ_УВК1000_АР_R23_вар1.pdf", "fd650339"),
}


def pinned(path, expected):
    raw = subprocess.check_output(["git", "show", f"{PIN}:{path}"])
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Unexpected Git digest: {path}")
    return json.loads(raw)


def declarations(entry):
    return {source["sha256"] for source in entry["sources"]}


def classify(sources, tuning):
    hashes = set(sources.values())
    return int(
        sources.keys() == SOURCES.keys()
        and len(hashes) == len(SOURCES)
        and not hashes & tuning
        and all(re.fullmatch(r"[0-9a-f]{64}", sources[role]) and sources[role].startswith(prefix)
                for role, (_, prefix) in SOURCES.items())
    )


def main():
    start = time.monotonic()
    bank = pinned("docs/trainer/etalons.json", BANK)["etalons"]
    ledger = pinned("docs/trainer/ledger.json", LEDGER)["rows"]
    if sorted(row["first_failing_step"] for row in ledger) != ["artifact"] * 3 + ["sources-dwg"]:
        raise ValueError("Frozen modal-stop witness diverged")
    entries = {entry["id"]: entry for entry in bank}
    tuning = set().union(*(declarations(entry) for entry in bank if entry["split"] == "tuning"))
    if not tuning or not all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in tuning):
        raise ValueError("Incomplete tuning declarations")
    old = entries["sokolniki-body-v005"]
    shared = declarations(entries["63a-stage1"]) & declarations(entries["63b-stage1"])
    separate = declarations(entries["63a-stage1"]) & declarations(entries["g22-k2-stage1"])
    if old["sources"] or old["practice_ready"] or len(shared) != 1 or separate:
        raise ValueError("Frozen controls diverged")
    inbox = Path(os.environ.get("SOKOLNIKI_R126_INBOX", INBOX))
    receipt = Path(__file__).with_suffix(".jsonl")
    expected = None
    if receipt.is_file():
        with receipt.open(encoding="utf-8") as file:
            expected = json.loads(file.readline())["hashes"]
    deltas = []
    first = expected
    for pair in range(1, 4):
        pair_start = time.monotonic()
        candidate = {}
        for role, (basename, _) in SOURCES.items():
            path = inbox / basename
            before = path.stat()
            with path.open("rb") as file:
                digest = hashlib.file_digest(file, "sha256").hexdigest()
            after = path.stat()
            if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                raise ValueError(f"Source changed during read: {role}")
            candidate[role] = digest
        if first is not None and first != candidate:
            raise ValueError("Candidate digest drift between pairs")
        first = candidate
        old_score = classify({}, tuning)
        new_score = classify(candidate, tuning)
        fbx = candidate["revit_fbx"]
        flipped = ("1" if fbx[0] == "0" else "0") + fbx[1:]
        renamed = dict(candidate, revit_fbx=next(iter(shared)))
        injected = {
            "pdf_omitted": classify({"revit_fbx": fbx}, tuning),
            "renamed_tuning_source": classify(renamed, tuning),
            "corrupt_fbx_prefix": classify(dict(candidate, revit_fbx=flipped), tuning),
        }
        overlap_count = len(set(candidate.values()) & tuning)
        injected_overlap = len(set(renamed.values()) & tuning)
        if any(injected.values()) or injected_overlap < 1:
            raise ValueError("Injected controls diverged")
        delta = new_score - old_score
        deltas.append(delta)
        wall = time.monotonic() - pair_start
        print(json.dumps({"pair": pair, "old": old_score, "candidate": new_score, "delta": delta,
                          "hashes": candidate, "tuning_overlap": overlap_count, "injected": injected,
                          "changed_inputs": {"pdf_omitted": 1, "renamed_tuning_source": 1,
                                             "corrupt_fbx_prefix": 1}, "native_reads": 2,
                          "wall_s": round(wall, 3)}), flush=True)
        if (pair == 1 and 3 * wall > 60) or time.monotonic() - start > 60:
            raise TimeoutError("60 s series budget does not fit")
    result = "confirmed" if deltas == [1, 1, 1] else "refuted" if deltas == [0, 0, 0] else "inconclusive"
    print(json.dumps({"status": "complete", "result": result, "median": statistics.median(deltas),
                      "spread": max(deltas) - min(deltas), "wall_s": round(time.monotonic() - start, 3),
                      "tuning_digest_count": len(tuning), "declared_63a_63b_overlap": len(shared),
                      "declared_63a_g22_overlap": len(separate)}))


if __name__ == "__main__":
    main()
