"""Verifier step before showing Artem (#1577): 6-view VLM checklist + material rubric, OBSERVE mode.

new-case: skeleton stage `verifier` (docs/agents/skeletons.json) right after `readback` in oks-vpm, ground-npm and
ground-vpm. It answers the fixed variant-A checklist of tools/qa/vlm_checklist.py (#768) twice, views forward and
reversed, keeps only order-consistent answers, adds a material block (6 axes scored 1-5 with a one-line reason;
fix order missing -> base_color -> borders -> scale; arXiv 2609.06535) and writes ONE `verifier.json` with the
findings, the ONE main discrepancy it would fix next (VIGA verifier loop, arXiv 2601.11109) and the scores.

Rules:
- The VLM confirms, it never locates: positions and counts come from geometry and drawing vectors (CrossProjection,
  arXiv 2608.00473: 82 % view matching vs 22 % line localisation). Findings carry `locate_with` for that.
- OBSERVE (default) never edits the model and writes only the report. `--mode fix` is refused unless
  `jobs/<ID>/skeleton.json` sets `config.verifier_mode = "fix"` (Artem's word); at most 3 rounds. Even then this
  tool only reports; the fix is a separate step.
- Advisory, not a delivery gate. Everything fails closed: a missing/duplicate/unknown/non-integer score, a broken
  answer, a VLM error, an output path that overlaps an input or already exists -> exit 2/1 and nothing written.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import vlm_checklist as _vc  # noqa: E402
from vlm_checklist import VIEWS, ChecklistError, parse_answers  # noqa: E402,F401

SCHEMA = "agr.verifier/1"
MODES = ("observe", "fix")
MAX_ROUNDS = 3
MATERIAL_AXES = ("missing", "base_color", "borders", "scale", "finish", "consistency")
MATERIAL_TEXT = {
    "missing": "every surface has its material; no default/grey/untextured or missing face",
    "base_color": "base colour of each finish matches the slide/legend (RAL)",
    "borders": "borders between finishes sit where the slide puts them; no bleeding or stray band",
    "scale": "texture scale/tiling is plausible (bricks, ribs, panels not stretched or tiny)",
    "finish": "surface character (matte/gloss, texture type) matches the legend",
    "consistency": "the same finish looks the same on every view and in NPM vs VPM",
}
FIX_ORDER = ("missing", "base_color", "borders", "scale")
DISCREPANCY_MAX = 3      # a material score <= 3 is a discrepancy; 4-5 is acceptable
ROLE = ("confirm-only: the VLM confirms; positions and counts come from geometry and drawing vectors "
        "(CrossProjection)")
LOCATE_GEOMETRY = "geometry and drawing vectors (CrossProjection): count/position from the model and the DXF"
REPORT_KEYS = ("schema", "job", "mode", "round", "edits_model", "role", "inputs", "vlm", "checklist", "materials",
               "findings", "main_discrepancy", "scores")
FINDING_KEYS = ("id", "source", "key", "text", "locate_with")


class VerifierError(ValueError):
    """Input, answer or report that cannot be used; never treated as pass."""


def checklist_items(facades: dict) -> list[dict]:
    try:
        return _vc.checklist_a(facades)
    except ChecklistError as e:
        raise VerifierError(str(e)) from None


# ---------------------------------------------------------------- material rubric (pure, fail closed)

def _is_int_score(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def parse_material_scores(answers) -> dict:
    """{axis: {score, reason}} in MATERIAL_AXES order. Every axis exactly once, integer 1-5, one-line reason."""
    if not isinstance(answers, list):
        raise VerifierError(f"material scores must be a list, got {type(answers).__name__}")
    out: dict = {}
    for a in answers:
        if not isinstance(a, dict):
            raise VerifierError(f"material score is not an object: {a!r}")
        axis = a.get("axis")
        if axis not in MATERIAL_AXES:
            raise VerifierError(f"unknown material axis {axis!r} (known: {list(MATERIAL_AXES)})")
        if axis in out:
            raise VerifierError(f"duplicate material axis {axis!r}")
        s = a.get("score")
        if not _is_int_score(s):
            if isinstance(s, float) and not math.isfinite(s):
                raise VerifierError(f"score of {axis} is not an integer: {s!r} (NaN/inf)")
            raise VerifierError(f"score of {axis} is not an integer: {s!r}")
        if not 1 <= s <= 5:
            raise VerifierError(f"score of {axis} is outside 1-5: {s}")
        r = a.get("reason")
        if not isinstance(r, str) or not r.strip() or "\n" in r or "\r" in r:
            raise VerifierError(f"reason of {axis} must be one non-empty line, got {r!r}")
        out[axis] = {"score": s, "reason": r.strip()}
    missing = [x for x in MATERIAL_AXES if x not in out]
    if missing:
        raise VerifierError(f"missing material axes: {missing}")
    return {x: out[x] for x in MATERIAL_AXES}


def combine_material(forward: dict, reverse: dict) -> dict:
    """Both view orders scored; the lower (more critical) score is kept with its reason."""
    if list(forward) != list(MATERIAL_AXES) or list(reverse) != list(MATERIAL_AXES):
        raise VerifierError("material forward/reverse do not cover the 6 axes")
    out = {}
    for x in MATERIAL_AXES:
        f, r = forward[x], reverse[x]
        low = r if r["score"] < f["score"] else f
        out[x] = {"score": low["score"], "reason": low["reason"], "forward": f["score"], "reverse": r["score"]}
    return out


# ---------------------------------------------------------------- findings and the ONE main discrepancy

def _checklist_key(item: dict) -> str:
    key = f"checklist:{item['category']}"
    return key if item.get("facade", "all") == "all" else f"{key}:{item['facade']}"


def findings(items: list[dict], kept: dict, materials: dict) -> list[dict]:
    """Ordered by what to fix first: material discrepancies (fix order, then the other axes by score), then
    order-consistent checklist defects in checklist order."""
    out = []
    rank = {x: i for i, x in enumerate(FIX_ORDER)}
    bad = [x for x in MATERIAL_AXES if materials[x]["score"] <= DISCREPANCY_MAX]
    bad.sort(key=lambda x: (rank.get(x, len(FIX_ORDER)), materials[x]["score"], MATERIAL_AXES.index(x)))
    for x in bad:
        out.append({"id": f"M:{x}", "source": "material", "key": f"material:{x}",
                    "text": f"{x} scored {materials[x]['score']}/5: {materials[x]['reason']}",
                    "locate_with": "material slots and UV of the model (the VLM only confirms)"})
    for it in items:
        if kept.get(it["id"]) is True:
            geo = it["category"] in ("rib_count", "field_outline", "door", "windows", "no_extra")
            out.append({"id": it["id"], "source": "checklist", "key": _checklist_key(it), "text": it["question"],
                        "locate_with": LOCATE_GEOMETRY if geo else "material slots of the model (VLM confirms)"})
    return out


def main_discrepancy(found: list[dict]):
    return dict(found[0]) if found else None


def build_report(*, job, mode, round_no, renders, slide, facades, items, forward, reverse, mat_forward,
                 mat_reverse, vlm) -> dict:
    kept, dropped = _vc.consistent(forward, reverse)
    mats = combine_material(mat_forward, mat_reverse)
    found = findings(items, kept, mats)
    scores = [m["score"] for m in mats.values()]
    doc = {
        "schema": SCHEMA, "job": str(job), "mode": mode, "round": round_no, "edits_model": False, "role": ROLE,
        "inputs": {"renders": str(renders), "slide": str(slide), "views": list(VIEWS), "facades": dict(facades)},
        "vlm": dict(vlm),
        "checklist": {"variant": "A", "items": items, "forward": forward, "reverse": reverse, "kept": kept,
                      "dropped": dropped},
        "materials": {"axes": mats, "fix_order": list(FIX_ORDER), "discrepancy_max": DISCREPANCY_MAX},
        "findings": found,
        "main_discrepancy": main_discrepancy(found),
        "scores": {"checklist_items": len(items), "checklist_kept": len(kept),
                   "checklist_flagged": sum(1 for v in kept.values() if v),
                   "material_min": min(scores), "material_mean": round(sum(scores) / len(scores), 3)},
    }
    return validate_report(doc)


def validate_report(doc):
    """Fail-closed check of verifier.json (mirrors schemas/Verifier.schema.json plus cross-field rules)."""
    if not isinstance(doc, dict):
        raise VerifierError("verifier report is not an object")
    if set(doc) != set(REPORT_KEYS):
        raise VerifierError(f"verifier report keys {sorted(doc)} != {sorted(REPORT_KEYS)}")
    if doc["schema"] != SCHEMA:
        raise VerifierError(f"schema {doc['schema']!r} != {SCHEMA!r}")
    if doc["edits_model"] is not False:
        raise VerifierError("edits_model must be false: the verifier never edits the model")
    if doc["mode"] not in MODES:
        raise VerifierError(f"unknown mode {doc['mode']!r}")
    r = doc["round"]
    if not _is_int_score(r) or not 1 <= r <= MAX_ROUNDS or (doc["mode"] == "observe" and r != 1):
        raise VerifierError(f"round {r!r} invalid for mode {doc['mode']} (observe: 1, fix: 1-{MAX_ROUNDS})")
    mats = doc["materials"]
    if not isinstance(mats, dict) or not isinstance(mats.get("axes"), dict) or list(mats["axes"]) != list(
            MATERIAL_AXES):
        raise VerifierError("materials.axes must hold the 6 axes in order")
    for x, m in mats["axes"].items():
        if not (isinstance(m, dict) and _is_int_score(m.get("score")) and 1 <= m["score"] <= 5):
            raise VerifierError(f"materials.axes.{x}.score must be an integer 1-5")
    found = doc["findings"]
    if not isinstance(found, list):
        raise VerifierError("findings must be a list")
    keys = set()
    for f in found:
        if not isinstance(f, dict) or set(f) != set(FINDING_KEYS) or f["source"] not in ("material", "checklist") \
                or not all(isinstance(f[k], str) and f[k] for k in FINDING_KEYS):
            raise VerifierError(f"bad finding {f!r}")
        if f["id"] in keys:
            raise VerifierError(f"duplicate finding {f['id']!r}")
        keys.add(f["id"])
    main = doc["main_discrepancy"]
    if found and main != found[0]:
        raise VerifierError("main_discrepancy must be the first finding (the ONE thing to fix next)")
    if not found and main is not None:
        raise VerifierError("main_discrepancy must be null when there are no findings")
    if not isinstance(doc["checklist"], dict) or doc["checklist"].get("variant") != "A":
        raise VerifierError("checklist must be variant A")
    if not isinstance(doc["scores"], dict) or not isinstance(doc["inputs"], dict) or not isinstance(doc["vlm"], dict):
        raise VerifierError("scores, inputs and vlm must be objects")
    return doc


# ---------------------------------------------------------------- mode gate

def resolve_mode(job_dir: Path, mode: str, round_no: int):
    """observe: always round 1. fix: only with skeleton.json config.verifier_mode == "fix", rounds 1-3."""
    if mode not in MODES:
        raise VerifierError(f"unknown mode {mode!r} (known: {list(MODES)})")
    if not isinstance(round_no, int) or not 1 <= round_no <= MAX_ROUNDS or (mode == "observe" and round_no != 1):
        raise VerifierError(f"round {round_no} invalid for mode {mode} (observe: 1, fix: 1-{MAX_ROUNDS})")
    if mode == "fix":
        cfg_path = Path(job_dir) / "skeleton.json"
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise VerifierError(f"--mode fix refused: {cfg_path} unreadable ({type(e).__name__}); "
                                f"fix needs config.verifier_mode = \"fix\" there (Artem's word)") from None
        opt = cfg.get("config", {}).get("verifier_mode") if isinstance(cfg, dict) and isinstance(
            cfg.get("config"), dict) else None
        if opt != "fix":
            raise VerifierError(f"--mode fix refused: {cfg_path} config.verifier_mode is {opt!r}, not \"fix\" "
                                f"(observe is the default until Artem widens it)")
    return mode, round_no


# ---------------------------------------------------------------- VLM run

call_vlm = _vc.call_vlm


def _view_lines(renders: Path, facades: dict, order) -> str:
    return _vc._view_lines({"renders": str(renders), "facades": facades}, order)


def prompt(renders: Path, slide: Path, facades: dict, items: list[dict], order, legend: str) -> str:
    qs = "\n".join(f"{i['id']}: {i['question']}" for i in items)
    axes = "\n".join(f"{x}: {MATERIAL_TEXT[x]}" for x in MATERIAL_AXES)
    leg = f"Legend of finishes:\n{legend}\n" if legend else ""
    return (f"You CONFIRM a 3D model against its design slide; you do not locate lines or count positions "
            f"precisely, geometry does that.\nReference slide: {Path(slide).as_posix()}\n{leg}Renders of the "
            f"model:\n{_view_lines(renders, facades, order)}\n{_vc._RULES}\nPart 1 - for each item decide if the "
            f"model has a DEFECT (the statement is false for the model). Items:\n{qs}\nPart 2 - score the "
            f"materials on each axis 1-5 (5 = matches the slide, 1 = wrong) with a one-line reason:\n{axes}\n"
            f"Answer ONLY with JSON: {{\"answers\": [{{\"id\": \"..\", \"defect\": true|false, \"note\": "
            f"\"<=15 words\"}}], \"materials\": [{{\"axis\": \"..\", \"score\": 1-5, \"reason\": \"one line\"}}]}} "
            f"with every id and every axis exactly once.")


def _parse_facades(text: str) -> dict:
    out = {}
    for part in (text or "").split(","):
        side, sep, label = part.partition("=")
        side, label = side.strip(), label.strip()
        if not sep or side not in ("south", "north", "east", "west") or not label or side in out:
            raise VerifierError(f"bad --facades entry {part!r}: need south=..,north=..,east=..,west=.. once each")
        out[side] = label
    if set(out) != {"south", "north", "east", "west"}:
        raise VerifierError(f"--facades must name all four sides, got {sorted(out)}")
    return out


def _check_paths(out: Path, renders: Path, slide: Path, job: Path, legend) -> None:
    r = out.resolve()
    inputs = [renders.resolve(), slide.resolve(), (job / "skeleton.json").resolve()]
    if legend:
        inputs.append(Path(legend).resolve())
    for i in inputs:
        if r == i or i in r.parents:
            raise VerifierError(f"output {out} overlaps input {i}")
    if r.exists() or Path(str(r) + ".partial").exists():
        raise VerifierError(f"output {out} already exists; pass a new --out (e.g. verifier.r2.json)")
    if not r.parent.is_dir():
        raise VerifierError(f"output folder {r.parent} does not exist")


def run(job: Path, renders: Path, slide: Path, facades: dict, out: Path, mode: str, round_no: int, model: str,
        legend=None) -> dict:
    mode, round_no = resolve_mode(job, mode, round_no)
    _check_paths(out, renders, slide, job, legend)
    for v in VIEWS:
        if not (renders / f"{v}.png").is_file():
            raise VerifierError(f"missing view {v}.png in {renders}")
    if not slide.is_file():
        raise VerifierError(f"missing slide {slide}")
    items = checklist_items(facades)
    leg = _vc._legend(Path("/"), {"legend": str(Path(legend).resolve())}) if legend else ""
    res = {}
    for order, views in (("fwd", VIEWS), ("rev", tuple(reversed(VIEWS)))):
        try:
            res[order] = call_vlm(prompt(renders, slide, facades, items, views, leg), out.resolve().parent, model)
        except ChecklistError as e:
            raise VerifierError(f"VLM {order} call failed: {e}") from None
    try:
        fw = parse_answers(items, res["fwd"]["parsed"]["answers"])
        rv = parse_answers(items, res["rev"]["parsed"]["answers"])
    except (ChecklistError, KeyError, TypeError) as e:
        raise VerifierError(f"bad checklist answers: {e}") from None
    try:
        mf = parse_material_scores(res["fwd"]["parsed"]["materials"])
        mr = parse_material_scores(res["rev"]["parsed"]["materials"])
    except (KeyError, TypeError) as e:
        raise VerifierError(f"bad material block: {e!r}") from None
    vlm = {"model": model, "cost_usd": round(sum(c.get("cost_usd") or 0 for c in res.values()), 4),
           "duration_s": round(sum(c.get("duration_s") or 0 for c in res.values()), 1),
           "models": sorted({m for c in res.values() for m in c.get("models", [])})}
    doc = build_report(job=Path(job).as_posix(), mode=mode, round_no=round_no, renders=renders.as_posix(),
                       slide=slide.as_posix(), facades=facades, items=items, forward=fw, reverse=rv,
                       mat_forward=mf, mat_reverse=mr, vlm=vlm)
    _check_paths(out, renders, slide, job, legend)          # state may have changed during the VLM calls
    tmp = Path(str(out) + ".partial")
    try:
        with open(tmp, "x", encoding="utf-8") as fh:
            fh.write(json.dumps(doc, ensure_ascii=False, indent=1))
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--job", type=Path, required=True, help="jobs/<ID> (verifier.json goes here)")
    ap.add_argument("--renders", type=Path, required=True, help=f"folder with {', '.join(VIEWS)} .png")
    ap.add_argument("--slide", type=Path, required=True)
    ap.add_argument("--facades", required=True, help="south=<label>,north=..,east=..,west=..")
    ap.add_argument("--legend", type=Path, default=None, help="vpm_textures.json-style legend (optional)")
    ap.add_argument("--out", type=Path, default=None, help="default <job>/verifier.json; never overwritten")
    ap.add_argument("--mode", default="observe", help="observe (default) | fix (needs skeleton.json opt-in)")
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args(argv)
    try:
        if not a.job.is_dir():
            raise VerifierError(f"job folder {a.job} does not exist")
        resolve_mode(a.job, a.mode, a.round)
        doc = run(a.job, a.renders, a.slide, _parse_facades(a.facades), a.out or a.job / "verifier.json",
                  a.mode, a.round, a.model, a.legend)
    except VerifierError as e:
        print(f"error: {e}")
        return 2
    print(json.dumps({"main_discrepancy": doc["main_discrepancy"], "scores": doc["scores"]}, ensure_ascii=False,
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
