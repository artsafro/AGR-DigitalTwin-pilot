"""Verifier summary (#1577): per job, how often the verifier's ONE main discrepancy matched what Artem corrected.

new-case: reads every `verifier*.json` (tools/qa/verifier.py reports) under a jobs root and the job's
`verifier_review.json`, written after Artem's review:

    {"reviews": [{"verifier": "verifier.json", "artem_corrected": ["material:base_color", "checklist:rib_count"]}]}

`artem_corrected` lists the keys Artem corrected (`material:<axis>` or `checklist:<category>[:<facade>]`; `[]` =
accepted as is). A run matches when its main discrepancy key equals a corrected key or lies under it
(`checklist:rib_count:2-1` under `checklist:rib_count`), or when the verifier found nothing and Artem corrected
nothing. Fails closed: a review naming a missing or duplicated report, an unknown key, an invalid report or an
empty root is an error (exit 2). For Artem's review after a week of observe mode.
"""
from __future__ import annotations

import argparse
import json
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", type=Path, default=Path("jobs"))
    a = ap.parse_args(argv)
    try:
        s = summarize(a.jobs)
    except VerifierError as e:
        print(f"error: {e}")
        return 2
    print(json.dumps(s, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
