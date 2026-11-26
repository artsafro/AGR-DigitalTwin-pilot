import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import sys
import time
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "trainer"))
import trainer

CAP = 480
MANIFEST = Path(__file__).with_name("inputs.json")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def explicit_pair(built, fbx, archive):
    root = built.resolve(strict=True)
    pair = []
    for ref, suffix in ((fbx, ".fbx"), (archive, ".zip")):
        resolved = (root / ref).resolve()
        if (ref.anchor or not resolved.is_relative_to(root)
                or resolved.suffix.lower() != suffix or not resolved.is_file()):
            raise ValueError(f"invalid explicit {suffix} reference: {ref}")
        pair.append(resolved)
    return tuple(pair)


def preflight(catalog):
    for name, row in catalog.items():
        if digest(Path(row["zip"])) != row["sha256"]:
            raise ValueError(f"source hash mismatch: {name}")


def member_copy(archive, member, dest):
    with ZipFile(archive) as zf, zf.open(member) as stream, dest.open("xb") as out:
        shutil.copyfileobj(stream, out)
    with dest.open("rb") as stream:
        if not stream.read(23).startswith(b"Kaydara FBX Binary"):
            raise ValueError(f"not a binary FBX: {dest.name}")


def stage(catalog, out):
    store = out / "originals"
    store.mkdir()
    copies = {}
    for name, row in catalog.items():
        p = Path(row["zip"])
        directory = store / name
        directory.mkdir()
        archive = Path(shutil.copyfile(p, directory / p.name))
        if digest(archive) != row["sha256"]:
            raise ValueError(f"staged ZIP hash mismatch: {name}")
        body = directory / row["member"]
        member_copy(archive, row["member"], body)
        copies[name] = (body, archive)
    elv = catalog["elv_delivered"]
    light = store / "decoy.fbx"
    member_copy(copies["elv_delivered"][1], elv["decoy_fbx_member"], light)
    return copies, light


def validate(zip_path, work):
    work.mkdir(parents=True)
    verdict = trainer.package_step({"profile": "vpm"}, zip_path, work)
    raw = (work / "validate.json").read_text(encoding="utf-8")
    report = json.loads(raw)
    if verdict["status"] not in {"pass", "fail"} or not isinstance(report.get("passed"), bool):
        raise ValueError(f"unusable native validator output: {work}")
    # Only path representation may differ. Keep all findings and statuses.
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True)
    for path in (str(zip_path), zip_path.as_posix()):
        canonical = canonical.replace(json.dumps(path, ensure_ascii=False)[1:-1], "$ZIP")
    statuses = {}
    for finding in report.get("findings", []):
        status = finding.get("status", "missing-status")
        statuses[status] = statuses.get(status, 0) + 1
    return {**verdict, "report_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "finding_status_counts": statuses}


def refused(func, *args):
    try:
        func(*args)
    except (ValueError, trainer.TrainerError) as exc:
        return str(exc)
    return None


def exercise(room, body, archive, light, decoy):
    built = room / "built"
    built.mkdir(parents=True)
    fbx = built / body.name
    zip_path = built / "selected" / archive.name
    zip_path.parent.mkdir()
    os.link(body, fbx)
    os.link(archive, zip_path)
    expected = [digest(body), digest(archive)]
    fbx_ref, zip_ref = (file.relative_to(built) for file in (fbx, zip_path))
    clean = trainer.pick_built(built, {})
    oracle = validate(clean[1], room / "oracle")
    a = trainer.pick_built(fbx, {})
    variants = {}
    inventory = set(built.rglob("*.*"))
    for label in ("clean", "extra_zip", "extra_zip_and_fbx"):
        if label == "extra_zip":
            os.link(decoy, built / "00-other.zip")
        elif label == "extra_zip_and_fbx":
            (built / "nested").mkdir()
            os.link(light, built / "nested" / body.name)
        selected = explicit_pair(built, fbx_ref, zip_ref)
        measured = validate(selected[1], room / label)
        variants[label] = {"added_entries": len(set(built.rglob("*.*")) - inventory),
                           "selected_sha256": [digest(x) for x in selected], "native": measured}
        if label == "extra_zip":
            variants[label]["directory_zip_sha256"] = digest(trainer.pick_built(built, {})[1])
        elif label == "extra_zip_and_fbx":
            variants[label]["directory_refusal"] = refused(trainer.pick_built, built, {})
    os.link(archive, room / "outside.zip")
    cases = {"missing_fbx": (Path("missing.fbx"), zip_ref), "missing_zip": (fbx_ref, Path("missing.zip")),
             "wrong_suffix": (zip_ref, zip_ref), "outside_root": (fbx_ref, Path("../outside.zip"))}
    negatives = {name: {"changed_references": 1, "refusal": refused(explicit_pair, built, *refs)}
                 for name, refs in cases.items()}
    parity = all(v["selected_sha256"] == expected and v["native"] == oracle for v in variants.values())
    decoy_zip_sha = digest(decoy)
    ok = (a == (fbx, None) and clean == (fbx, zip_path) and parity
          and [v["added_entries"] for v in variants.values()] == [0, 1, 2]
          and decoy_zip_sha != expected[1] and digest(light) != expected[0]
          and variants["extra_zip"]["directory_zip_sha256"] == decoy_zip_sha
          and "several FBX" in (variants["extra_zip_and_fbx"]["directory_refusal"] or "")
          and all(x["refusal"] for x in negatives.values()))
    return dict(expected_sha256=expected, A_complete=a[1] is not None, B_complete=parity,
                oracle=oracle, variants=variants, negatives=negatives, ok=ok)


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main(out):
    catalog = json.loads(MANIFEST.read_text(encoding="utf-8"))
    preflight(catalog)
    out.mkdir(parents=True)
    copies, light = stage(catalog, out)
    started = time.monotonic()
    rounds, status = [], "series_complete"
    for rep in range(1, 4):
        cases = {}
        for name, (body, archive) in copies.items():
            other = "kpp1_predecessor" if name == "kpp1_accepted" else "kpp1_accepted"
            cases[name] = exercise(out / f"R{rep}" / name, body, archive, light, copies[other][1])
            if time.monotonic() - started > CAP:
                status = "wall_stop"
                save(out / "partial.json", cases)
                break
        if status != "series_complete":
            break
        elapsed = round(time.monotonic() - started, 3)
        a, b = (sum(case[arm] for case in cases.values()) for arm in ("A_complete", "B_complete"))
        rounds.append(dict(A=a, B=b, lift=b-a, cases=cases, elapsed_s=elapsed))
        save(out / f"round-{rep}.json", rounds[-1])
        print(f"R{rep}: A={a}/4 B={b}/4; cumulative wall {elapsed:.3f} s", flush=True)
        if rep == 1 and CAP - elapsed < 2 * elapsed + 20:
            status = "pilot_budget_stop"
            break
    preflight(catalog)
    lifts = [r["lift"] for r in rounds]
    complete = status == "series_complete" and len(rounds) == 3
    good = all(r["A"] == 0 and r["B"] == 4 and all(c["ok"] for c in r["cases"].values()) for r in rounds)
    receipt = dict(hypothesis=("confirmed" if good else "refuted") if complete else "inconclusive",
                   run_status=status, paired_lifts=lifts,
                   series_wall_s=round(time.monotonic() - started, 3),
                   paired_median=statistics.median(lifts) if complete else None,
                   paired_spread=[min(lifts), max(lifts)] if complete else None,
                   manifest_worktree_sha256=digest(MANIFEST), candidate_worktree_sha256=digest(Path(__file__)),
                   rounds=rounds)
    save(out / "receipt.json", receipt)
    print(receipt["hypothesis"], receipt["run_status"], receipt["paired_lifts"], flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
