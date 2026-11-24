"""new-case: hash-bound disposition of the existing KPP1 v004 reports [D382].

Read-only replay for readiness; does not rerun or change the machine validator.
"""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys
from zipfile import ZipFile

ARCHIVES = {"npm": "npm/0000_Kpp_1.zip", "vpm": "vpm/SM_Kpp_1.zip"}
NPM_ROLE = "npm/validate-npm.json"
NPM_WORK = "npm/validate-npm-work.json"
VPM_ROLE = "vpm/validate-vpm.json"
VPM_WORK = "vpm/validate-vpm-work.json"
PINS = {
    ARCHIVES["npm"]: "0ee309e7a6c5e51b297a38a1b9be255e4e73e986ca353b2b39a1bb6d7e228bfe",
    ARCHIVES["vpm"]: "d84d1df0adc2b80e35bc5c5eaecc47ea9fb5ec95553ac3756635848b12ce1bf9",
    NPM_ROLE: "671ec674a109de8a256f0443aaff29cfcc629bd732736cb986943cba4d8a5a31",
    NPM_WORK: "7d0469b0a0e0f68a209914ac84743ee3b57b11bc90dd4df494e60fffc51fc6c7",
    VPM_ROLE: "c4f1b8c70b8c14ca6fb9896b28eb07371a530efb38d6530753c7f3b3b029976b",
    VPM_WORK: "745ee8f574f3a6979fd939777c88d9778c325ee990f7046fec978a3e25f5996d",
}
GROUND_MEMBER = "0000_Kpp_1_Ground.fbx"
# #1416 package-v002, not a digest inferred from the candidate archive.
GROUND_SHA256 = "8006f0a3904d91f4793c7eb0dcbac6e934c16c470b29c994b7ff7c7a66c9c6d4"

# Positions refer to the exact immutable reports above. Disposition is on a
# finding, not on a V-stage (notably V004 on NPM contains both OKS and Ground).
NPM_ROWS = {
    ("V003", 6): "accepted_exception",  # Ground skirt
    ("V004", 2): "accepted_exception",  # OKS clearance review
    ("V004", 4): "accepted_exception",  # OKS duplicate vertices review
    ("V004", 6): "accepted_exception",  # Ground topology
    ("V004", 9): "accepted_exception",  # Ground clearance
}
VPM_ROWS = {
    ("V004", 2): "accepted_exception",  # OKS clearance review
    ("V007", 0): "accepted_exception",  # flat procedural normal
    ("V012", 0): "name_accepted_manual_review",  # no waiver of the manual check
}
APPROVED_ROWS = {
    NPM_ROLE: NPM_ROWS,
    NPM_WORK: {**NPM_ROWS, ("V003", 9): "accepted_exception"},  # decor
    VPM_ROLE: VPM_ROWS,
    VPM_WORK: {**VPM_ROWS, ("V003", 3): "accepted_exception"},  # decor
}


def _snapshot(root, path, expected_sha):
    # Bound memory even for a foreign file supplied at a known path. Parse the
    # very bytes that were hashed, not a second read of a mutable filename.
    limit = 16 * 1024 * 1024 if path.endswith(".zip") else 128 * 1024
    try:
        with (root / path).open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as exc:
        raise ValueError(f"{path}: unavailable evidence: {exc}") from exc
    if len(data) > limit or sha256(data).hexdigest() != expected_sha:
        raise ValueError(f"{path}: SHA-256 mismatch for the approved evidence")
    return data


def _project(report, approved):
    findings, manual, open_stages = [], [], []
    for stage in report["stages"]:
        stage_id = stage["id"]
        if stage["gate"] == "manual_review":
            manual.append(stage_id)
        elif stage["status"] != "pass" and not stage["findings"]:
            open_stages.append(stage_id)
        for index, finding in enumerate(stage["findings"]):
            if finding["status"] != "pass":
                findings.append({"stage": stage_id, "index": index, "name": finding["name"],
                                 "raw_status": finding["status"],
                                 "disposition": approved.get((stage_id, index), "open")})
    return {"raw": report, "findings": findings, "manual_accepted": manual,
            "open_stages_without_findings": open_stages}


def replay(root, *, pins=PINS, approved_rows=APPROVED_ROWS, ground_sha256=GROUND_SHA256):
    snapshots = {path: _snapshot(root, path, digest) for path, digest in pins.items()}
    with ZipFile(BytesIO(snapshots[ARCHIVES["npm"]])) as archive:
        members = [entry for entry in archive.infolist() if entry.filename == GROUND_MEMBER]
        if len(members) != 1:
            raise ValueError(f"{GROUND_MEMBER}: expected exactly one member")
        digest = sha256()
        with archive.open(members[0]) as member:
            while chunk := member.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != ground_sha256:
            raise ValueError(f"{GROUND_MEMBER}: bytes differ from #1416 package-v002")
    reports = {}
    for path, approved in approved_rows.items():
        profile = path.split("/", 1)[0]
        raw = json.loads(snapshots[path])
        if raw["profile"] != profile or raw["target_sha256"] != pins[ARCHIVES[profile]]:
            raise ValueError(f"{path}: report does not refer to the pinned {profile} archive")
        reports[path] = _project(raw, approved)
    return {
        "package": "KPP1 v004 / draft-b25-r1", "decision": "D382",
        "ground_sha256": ground_sha256,
        "readiness": {"s_podz": {"projects": ["KPP1", "ELV"], "profile": "vpm", "stage": "V011",
                                  "disposition": "accepted_exception", "decision": "D377",
                                  "request_customer_data": False}},
        "reports": reports,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="the sealed draft-b25-r1 directory")
    args = parser.parse_args()
    try:
        result = replay(args.evidence)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    # Exit 0 means the post-validation overlay was read successfully, never a
    # machine or delivery pass. The raw report and its exit code stay intact.
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
