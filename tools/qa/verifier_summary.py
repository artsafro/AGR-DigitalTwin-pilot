"""Verifier summary (#1577): per job, how often the verifier's ONE main discrepancy matched what Artem corrected.

new-case: reads every `verifier*.json` (tools/qa/verifier.py reports) under a jobs root and the job's
`verifier_review.json`, written after Artem's review:

    {"reviews": [{"verifier": "verifier.json", "artem_corrected": ["material:base_color", "checklist:rib_count"]}]}

`artem_corrected` lists the keys Artem corrected (`material:<axis>` or `checklist:<category>[:<facade>]`; `[]` =
accepted as is). A run matches when its main discrepancy key equals a corrected key or lies under it
(`checklist:rib_count:2-1` under `checklist:rib_count`), or when the verifier found nothing and Artem corrected
nothing. Fails closed: a review naming a missing or duplicated report, an unknown key, an invalid report or an
empty root is an error (exit 2). For Artem's review after a week of observe mode.

Observe week (#1739): `--sheet-line --verifier V.json --mesh-quality MQ.json` prints the ONE line every sheet sent to
Artem carries (verifier main finding + mesh-quality score and worst facade cell); `--digest` prints one weekly line
for the status push (runs, matches, mesh-quality score band). Both fail closed (exit 2) on a missing/invalid report.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from verifier import MATERIAL_AXES, VerifierError, validate_report  # noqa: E402
from vlm_checklist import CATEGORIES  # noqa: E402

REVIEW = "verifier_review.json"


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise VerifierError(f"{path}: unreadable ({type(e).__name__}: {e})") from None


def _check_key(key, where) -> str:
    if not isinstance(key, str):
        raise VerifierError(f"{where}: artem_corrected entry {key!r} is not a string")
    parts = key.split(":")
    ok = (len(parts) == 2 and parts[0] == "material" and parts[1] in MATERIAL_AXES) or (
        parts[0] == "checklist" and len(parts) in (2, 3) and parts[1] in CATEGORIES and all(parts))
    if not ok:
        raise VerifierError(f"{where}: unknown correction key {key!r} (material:<axis> | checklist:<category>"
                            f"[:<facade>])")
    return key


def matched(main, corrected: list[str]) -> bool:
    if main is None:
        return not corrected
    k = main["key"]
    return any(k == c or k.startswith(c + ":") for c in corrected)


def summarize(jobs_root: Path) -> dict:
    jobs_root = Path(jobs_root)
    reports = sorted(p for p in jobs_root.rglob("verifier*.json") if p.name != REVIEW) if jobs_root.is_dir() else []
    if not reports:
        raise VerifierError(f"no verifier*.json under {jobs_root}")
    by_job: dict[Path, dict] = {}
    for p in reports:
        try:
            validate_report(_read(p))
        except VerifierError as e:
            raise VerifierError(f"{p}: {e}") from None
        by_job.setdefault(p.parent, {})[p.name] = _read(p)
    out, tot = {}, {"runs": 0, "reviewed": 0, "matched": 0}
    for job, docs in sorted(by_job.items()):
        rev_path = job / REVIEW
        reviewed = {}
        if rev_path.exists():
            rev = _read(rev_path)
            if not isinstance(rev, dict) or not isinstance(rev.get("reviews"), list):
                raise VerifierError(f"{rev_path}: needs a 'reviews' list")
            if not rev["reviews"]:
                raise VerifierError(f"{rev_path}: reviews is empty; delete the file or record a review")
            for i, r in enumerate(rev["reviews"]):
                where = f"{rev_path}: reviews[{i}]"
                name = r.get("verifier") if isinstance(r, dict) else None
                if name not in docs:
                    raise VerifierError(f"{where}: verifier {name!r} is not a report in {job}")
                if name in reviewed:
                    raise VerifierError(f"{where}: duplicate review of {name}")
                corr = r.get("artem_corrected")
                if not isinstance(corr, list):
                    raise VerifierError(f"{where}: artem_corrected must be a list (empty = accepted as is)")
                reviewed[name] = [_check_key(k, where) for k in corr]
        n_match = sum(matched(docs[n]["main_discrepancy"], c) for n, c in reviewed.items())
        rel = job.relative_to(jobs_root).as_posix()
        out[rel] = {"runs": len(docs), "reviewed": len(reviewed), "matched": n_match,
                    "match_rate": (n_match / len(reviewed)) if reviewed else None,
                    "unreviewed": sorted(n for n in docs if n not in reviewed)}
        tot["runs"] += len(docs)
        tot["reviewed"] += len(reviewed)
        tot["matched"] += n_match
    tot["match_rate"] = (tot["matched"] / tot["reviewed"]) if tot["reviewed"] else None
    return {"jobs": out, "total": tot}


def _mqo():
    import mesh_quality_observe as mqo   # noqa: PLC0415  (tools/qa on sys.path above)
    return mqo


def _check_mq(doc, where):
    try:
        return _mqo().validate_stage_report(doc)
    except ValueError as e:
        raise VerifierError(f"{where}: {e}") from None


def sheet_line(verifier_doc, mq_doc) -> str:
    """The ONE line every sheet sent to Artem carries during the observe week (#1739): verifier + mesh-quality."""
    try:
        v = validate_report(verifier_doc)
    except VerifierError as e:
        raise VerifierError(f"verifier report: {e}") from None
    m = _check_mq(mq_doc, "mesh_quality report")
    main = v["main_discrepancy"]
    sc = v["scores"]
    left = (f"Verifier ({v['mode']}): main={main['key'] if main else 'none'}; "
            f"checklist flagged {sc.get('checklist_flagged')}/{sc.get('checklist_items')}; "
            f"material min {sc.get('material_min')}")
    line = f"{left} | Mesh quality (observe): {m['signal']}"
    if "\n" in line or "\r" in line:
        raise VerifierError("sheet line must be one line")
    return line


def digest_line(jobs_root: Path) -> str:
    """Weekly digest line for the status push: verifier runs / matches + mesh-quality score bands."""
    s = summarize(jobs_root)
    t = s["total"]
    jobs_root = Path(jobs_root)
    scores = []
    for p in sorted(jobs_root.rglob("mesh_quality*.json")):
        scores.append(_check_mq(_read(p), str(p))["score"])
    rate = f" ({t['match_rate']:.0%})" if t["match_rate"] is not None else ""
    mq = (f"mesh-quality {len(scores)} reports, score min {min(scores):.1f} / median "
          f"{statistics.median(scores):.1f} / max {max(scores):.1f}") if scores else "mesh-quality 0 reports"
    return (f"Verifier observe week: {t['runs']} runs in {len(s['jobs'])} jobs, reviewed {t['reviewed']}, "
            f"main finding matched {t['matched']}/{t['reviewed']}{rate}; {mq}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", type=Path, default=Path("jobs"))
    ap.add_argument("--digest", action="store_true", help="one weekly digest line for the status push (#1739)")
    ap.add_argument("--sheet-line", action="store_true", help="one line for a sheet: needs --verifier and "
                                                               "--mesh-quality (#1739)")
    ap.add_argument("--verifier", type=Path)
    ap.add_argument("--mesh-quality", type=Path)
    a = ap.parse_args(argv)
    try:
        if a.sheet_line:
            if not a.verifier or not a.mesh_quality:
                raise VerifierError("--sheet-line needs --verifier and --mesh-quality")
            print(sheet_line(_read(a.verifier), _read(a.mesh_quality)))
            return 0
        if a.digest:
            print(digest_line(a.jobs))
            return 0
        s = summarize(a.jobs)
    except VerifierError as e:
        print(f"error: {e}")
        return 2
    print(json.dumps(s, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
