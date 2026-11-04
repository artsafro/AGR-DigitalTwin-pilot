"""Advisory 6-view VLM defect checklist (research, issue #768).

new-case: advisory VLM judge over existing renders; measures recall/false positives against a fixed ground
truth. It is NOT a gate: nothing in tools/qa, standards or the pipeline reads its output.

Variant A: a fixed 12-item binary checklist. Variant B: the VLM first turns the slide and its legend into
8-12 yes/no questions, then answers them on the renders. Every checklist is answered twice with the views in
forward and reversed order; only order-consistent answers are kept. Pairwise: two models of one building are
compared per item in both orders; only order-consistent winners are kept.

The VLM is the Claude Code CLI (`claude -p`, image Read tool); time and cost come from its JSON result.
Scoring functions are pure and fail closed: a missing, duplicated, unknown or non-boolean answer is an error.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VIEWS = ("vpm_south", "vpm_north", "vpm_east", "vpm_west", "vpm_iso", "npm_iso")
CATEGORIES = ("panel_color", "frame_color", "plinth_color", "rib_count", "field_outline", "door", "windows",
              "no_extra", "npm_vpm_consistency", "other")

# Variant A: fixed checklist. {facade:<side>} is filled with the slide label of that render side.
CHECKLIST_A = (
    ("A01", "panel_color", None, "The ribbed panel field has the colour shown on the slide on every facade."),
    ("A02", "frame_color", None, "The band/frame around the panel field (corners, top and bottom edging) has the "
                                 "colour shown on the slide."),
    ("A03", "plinth_color", None, "The plinth/base at and below the ground line (red line in the renders) has the "
                                  "colour shown on the slide."),
    ("A04", "rib_count", "north", "Facade {facade}: the number of vertical ribs/seams equals the slide (within 10 %)."),
    ("A05", "rib_count", "south", "Facade {facade}: the number of vertical ribs/seams equals the slide (within 10 %)."),
    ("A06", "rib_count", "west", "Facade {facade}: the number of vertical ribs/seams equals the slide (within 10 %)."),
    ("A07", "rib_count", "east", "Facade {facade}: the number of vertical ribs/seams equals the slide (within 10 %)."),
    ("A08", "field_outline", None, "A thin dark outline runs along the edge of the panel field, as on the slide."),
    ("A09", "door", None, "Doors: same facade, position, size and colour as on the slide (none if the slide has none)."),
    ("A10", "windows", None, "Windows: same facade, position, size, frame colour as on the slide (none if none)."),
    ("A11", "no_extra", None, "No element, seam, hole, missing face or stretched texture that the slide does not show."),
    ("A12", "npm_vpm_consistency", None, "The NPM iso view shows the same colours and pattern as the VPM iso view."),
)


class ChecklistError(ValueError):
    """An answer or question list that cannot be scored; never treated as pass."""


def checklist_a(facades: dict) -> list[dict]:
    out = []
    for item_id, cat, side, text in CHECKLIST_A:
        label = None
        if side is not None:
            if side not in facades:
                raise ChecklistError(f"no slide label for render side {side!r}")
            label = facades[side]
        out.append({"id": item_id, "category": cat, "facade": label or "all",
                    "question": text.format(facade=label) if label else text})
    return out


def validate_questions(questions) -> list[dict]:
    """Variant B generator output: 8-12 unique ids, known category, non-empty question."""
    if not isinstance(questions, list) or not 8 <= len(questions) <= 12:
        raise ChecklistError(f"need 8-12 questions, got {len(questions) if isinstance(questions, list) else type(questions).__name__}")
    seen = set()
    for q in questions:
        if not isinstance(q, dict):
            raise ChecklistError(f"question is not an object: {q!r}")
        qid, cat, text = q.get("id"), q.get("category"), q.get("question")
        if not isinstance(qid, str) or not qid or qid in seen:
            raise ChecklistError(f"missing or duplicate question id {qid!r}")
        if cat not in CATEGORIES:
            raise ChecklistError(f"unknown category {cat!r} in {qid}")
        if not isinstance(text, str) or not text.strip():
            raise ChecklistError(f"empty question {qid}")
        if not isinstance(q.get("facade", "all"), str):
            raise ChecklistError(f"facade of {qid} is not a string")
        seen.add(qid)
    return questions


def parse_answers(items: list[dict], answers) -> dict[str, bool]:
    """{id: defect}. Every item exactly once, defect strictly bool, no unknown ids."""
    if not isinstance(answers, list):
        raise ChecklistError("answers is not a list")
    ids = [i["id"] for i in items]
    out: dict[str, bool] = {}
    for a in answers:
        aid = a.get("id") if isinstance(a, dict) else None
        if aid not in ids:
            raise ChecklistError(f"unknown answer id {aid!r}")
        if aid in out:
            raise ChecklistError(f"duplicate answer id {aid!r}")
        if not isinstance(a.get("defect"), bool):
            raise ChecklistError(f"defect of {aid} is not a boolean: {a.get('defect')!r}")
        out[aid] = a["defect"]
    missing = [i for i in ids if i not in out]
    if missing:
        raise ChecklistError(f"missing answers: {missing}")
    return out


def consistent(forward: dict[str, bool], reverse: dict[str, bool]) -> tuple[dict[str, bool], list[str]]:
    """Keep answers equal in both view orders; the rest are dropped (returned by id)."""
    if set(forward) != set(reverse):
        raise ChecklistError("forward and reverse runs answered different item sets")
    kept = {k: v for k, v in forward.items() if reverse[k] == v}
    return kept, sorted(k for k in forward if k not in kept)


def defect_keys(item: dict, facade_labels) -> set[str]:
    """Ground-truth keys an item covers: rib_count per facade, other categories by name."""
    cat = item["category"]
    if cat == "rib_count":
        fac = item.get("facade", "all")
        if fac == "all":
            return {f"rib_count:{f}" for f in facade_labels}
        if fac not in facade_labels:
            raise ChecklistError(f"item {item['id']} names unknown facade {fac!r}")
        return {f"rib_count:{fac}"}
    return {cat}


def score(items: list[dict], kept: dict[str, bool], known_defects, facade_labels) -> dict:
    """Recall over known defects (dropped answers count as missed) and flagged items outside them."""
    flagged = [i for i in items if kept.get(i["id"]) is True]
    covered = set()
    for i in flagged:
        covered |= defect_keys(i, facade_labels)
    res = {"flagged": [i["id"] for i in flagged], "n_items": len(items), "n_kept": len(kept)}
    if known_defects is None:
        return res
    known = set(known_defects)
    hits = sorted(known & covered)
    res.update({
        "known": len(known), "detected": hits, "missed": sorted(known - covered),
        "recall": (len(hits) / len(known)) if known else None,
        "false_positive_items": [i["id"] for i in flagged if not (defect_keys(i, facade_labels) & known)],
    })
    res["false_positives"] = len(res["false_positive_items"])
    return res


def parse_pairwise_answers(items: list[dict], answers) -> dict[str, str]:
    """{id: better} from the raw list. Every item exactly once, better in first/second/equal, no unknown ids.

    Validated on the original list so duplicates (even conflicting ones) are never collapsed by a dict.
    """
    if not isinstance(answers, list):
        raise ChecklistError("pairwise answers is not a list")
    ids = [i["id"] for i in items]
    out: dict[str, str] = {}
    for a in answers:
        aid = a.get("id") if isinstance(a, dict) else None
        if aid not in ids:
            raise ChecklistError(f"unknown pairwise answer id {aid!r}")
        if aid in out:
            raise ChecklistError(f"duplicate pairwise answer id {aid!r}")
        v = a.get("better")
        if v not in ("first", "second", "equal"):
            raise ChecklistError(f"pairwise answer must be first/second/equal, got {v!r} for {aid}")
        out[aid] = v
    missing = [i for i in ids if i not in out]
    if missing:
        raise ChecklistError(f"missing pairwise answers: {missing}")
    return out


def pairwise(items: list[dict], ab: dict[str, str], ba: dict[str, str], a: str, b: str) -> dict:
    """ab: answers with a shown first; ba: b first. Values 'first'|'second'|'equal'. Kept if same winner."""
    def winner(v, first, second):
        if v not in ("first", "second", "equal"):
            raise ChecklistError(f"pairwise answer must be first/second/equal, got {v!r}")
        return {"first": first, "second": second, "equal": "equal"}[v]
    ids = [i["id"] for i in items]
    for run in (ab, ba):
        if sorted(run) != sorted(ids):
            raise ChecklistError(f"pairwise run items {sorted(run)} != {sorted(ids)}")
    kept, dropped = {}, []
    for k in ids:
        w1, w2 = winner(ab[k], a, b), winner(ba[k], b, a)
        if w1 == w2:
            kept[k] = w1
        else:
            dropped.append(k)
    return {"kept": kept, "dropped": dropped, "consistent_share": len(kept) / len(ids)}


# ---------------------------------------------------------------- VLM calls (not unit tested: real runs)

def _extract_json(text: str):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(body)


def call_vlm(prompt: str, workdir: Path, model: str) -> dict:
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json", "--allowedTools", "Read",
           "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence"]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, encoding="utf-8", timeout=900)
    wall = time.time() - t0
    if p.returncode != 0:
        raise ChecklistError(f"claude exit {p.returncode}: {p.stderr[-400:]}")
    env = json.loads(p.stdout)
    if env.get("is_error"):
        raise ChecklistError(f"claude error: {env.get('result')!r}")
    return {"result": env["result"], "parsed": _extract_json(env["result"]), "cost_usd": env.get("total_cost_usd"),
            "duration_s": round(wall, 1), "models": sorted(env.get("modelUsage", {}))}


def _view_lines(obj: dict, order) -> str:
    rd = Path(obj["renders"])
    lines = []
    for v in order:
        side = v.split("_")[1]
        what = f"facade {obj['facades'][side]}" if side in obj["facades"] else (
            "VPM iso view" if v == "vpm_iso" else "NPM (low-poly) iso view")
        lines.append(f"- {(rd / (v + '.png')).as_posix()} : {v} = {what}")
    return "\n".join(lines)


def _legend(root: Path, obj: dict) -> str:
    leg = json.loads((root / obj["legend"]).read_text(encoding="utf-8"))["legend"]
    return "\n".join(f"- {r['material']}: RAL {r['ral']}, {r['texture']}" for r in leg)


_RULES = ("The renders are orthographic, flat-lit; the red horizontal line is the ground level; below it is the "
          "part of the model under ground. Ignore background colour, lighting and text. Read EVERY image file "
          "with the Read tool before answering.")


def prompt_checklist(obj: dict, items: list[dict], order) -> str:
    qs = "\n".join(f"{i['id']}: {i['question']}" for i in items)
    return (f"You check a 3D building model against its design slide.\nReference slide: "
            f"{Path(obj['slide']).as_posix()}\nRenders of the model:\n{_view_lines(obj, order)}\n{_RULES}\n"
            f"For each item decide if the model has a DEFECT (the statement is false for the model). "
            f"Items:\n{qs}\nAnswer ONLY with JSON: {{\"answers\": [{{\"id\": \"..\", \"defect\": true|false, "
            f"\"note\": \"<=15 words\"}}]}} with every id exactly once.")


def prompt_generate(obj: dict, legend: str) -> str:
    labels = ", ".join(sorted(set(obj["facades"].values())))
    return (f"Read the design slide {Path(obj['slide']).as_posix()} (facade colour scheme of one building; "
            f"facades {labels}). Legend of finishes:\n{legend}\nWrite 8 to 12 yes/no validation questions that "
            f"a reviewer can answer on renders of the 3D model, e.g. 'Is the frame blue?', 'Does facade 1-2 show "
            f"12 ribs?'. Phrase each so that YES means the model matches the slide. Count ribs on the slide "
            f"yourself where you ask about them. Category of each question, one of {list(CATEGORIES)}; facade = "
            f"one of {labels} or 'all'.\nAnswer ONLY with JSON: {{\"questions\": [{{\"id\": \"B01\", \"category\": "
            f"\"..\", \"facade\": \"..\", \"question\": \"..\"}}]}}")


def prompt_pairwise(first: dict, second: dict, items: list[dict]) -> str:
    qs = "\n".join(f"{i['id']}: {i['question']}" for i in items)
    return (f"Two versions of one 3D building model are compared with the design slide "
            f"{Path(first['slide']).as_posix()}.\nFIRST model renders:\n{_view_lines(first, VIEWS)}\n"
            f"SECOND model renders:\n{_view_lines(second, VIEWS)}\n{_RULES}\nFor each item say which model "
            f"satisfies it better: \"first\", \"second\" or \"equal\".\nItems:\n{qs}\nAnswer ONLY with JSON: "
            f"{{\"answers\": [{{\"id\": \"..\", \"better\": \"first\"|\"second\"|\"equal\"}}]}} every id once.")


def _check_out(out: Path, cfg: dict) -> None:
    inputs = []
    for o in cfg["objects"].values():
        inputs += [Path(o["renders"]).resolve(), Path(o["slide"]).resolve()]
    r = out.resolve()
    for i in inputs:
        if r == i or i in r.parents or r in i.parents:
            raise ChecklistError(f"output {out} overlaps input {i}")
    if out.exists() and any(out.iterdir()):
        raise ChecklistError(f"output {out} is not empty; use a new versioned folder")


def run(cfg_path: Path, out: Path, model: str, workers: int) -> dict:
    root = Path(__file__).resolve().parents[2]
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    _check_out(out, cfg)
    for o in cfg["objects"].values():
        for v in VIEWS:
            if not (Path(o["renders"]) / f"{v}.png").is_file():
                raise ChecklistError(f"missing view {v} in {o['renders']}")
    out.mkdir(parents=True, exist_ok=True)
    work = out / "cwd"
    work.mkdir()
    objs = cfg["objects"]
    calls = {}

    def go(key, prompt):
        try:
            calls[key] = call_vlm(prompt, work, model)
        except Exception as e:  # recorded as a failure, never as pass
            calls[key] = {"error": f"{type(e).__name__}: {e}"}

    # Variant B question generation, one per distinct slide.
    slides = {}
    for name, o in objs.items():
        slides.setdefault(o["slide"], name)
    with ThreadPoolExecutor(workers) as ex:
        for slide, name in slides.items():
            ex.submit(go, ("gen", slide), prompt_generate(objs[name], _legend(root, objs[name])))
    questions, gen_errors = {}, {}
    for slide in slides:
        c = calls[("gen", slide)]
        try:
            questions[slide] = validate_questions(c["parsed"]["questions"])
        except (ChecklistError, KeyError, TypeError) as e:
            questions[slide] = None
            gen_errors[f"gen/{Path(slide).name}"] = f"{e}; call={c.get('error')}"
    items = {}
    for name, o in objs.items():
        items[(name, "A")] = checklist_a(o["facades"])
        if questions[o["slide"]] is not None:
            items[(name, "B")] = questions[o["slide"]]
    with ThreadPoolExecutor(workers) as ex:
        for (name, var), its in items.items():
            for order, views in (("fwd", VIEWS), ("rev", tuple(reversed(VIEWS)))):
                ex.submit(go, ("chk", name, var, order), prompt_checklist(objs[name], its, views))
        for a, b in cfg.get("pairs", []):
            for var in ("A", "B"):
                if (a, var) in items:
                    its = items[(a, var)]
                    ex.submit(go, ("pair", a, b, var), prompt_pairwise(objs[a], objs[b], its))
                    ex.submit(go, ("pair", b, a, var), prompt_pairwise(objs[b], objs[a], its))
    results = {"model": model, "objects": {}, "pairs": {}, "errors": dict(gen_errors)}
    for (name, var), its in items.items():
        labels = sorted(set(objs[name]["facades"].values()))
        f, r = calls[("chk", name, var, "fwd")], calls[("chk", name, var, "rev")]
        key = f"{name}/{var}"
        try:
            fw = parse_answers(its, f["parsed"]["answers"])
            rv = parse_answers(its, r["parsed"]["answers"])
            kept, dropped = consistent(fw, rv)
            s = score(its, kept, objs[name]["known_defects"], labels)
            s.update({"forward": fw, "reverse": rv, "dropped": dropped,
                      "order_consistent_share": len(kept) / len(its)})
        except (ChecklistError, KeyError, TypeError) as e:
            results["errors"][key] = f"{e}; fwd={f.get('error')}; rev={r.get('error')}"
            s = {"error": str(e)}
        s["cost_usd"] = sum(c.get("cost_usd") or 0 for c in (f, r))
        s["duration_s"] = sum(c.get("duration_s") or 0 for c in (f, r))
        results["objects"][key] = s
    for a, b in cfg.get("pairs", []):
        for var in ("A", "B"):
            if (a, var) not in items:
                continue
            its = items[(a, var)]
            c1, c2 = calls[("pair", a, b, var)], calls[("pair", b, a, var)]
            key = f"{a}~{b}/{var}"
            try:
                ab = parse_pairwise_answers(its, c1["parsed"]["answers"])
                ba = parse_pairwise_answers(its, c2["parsed"]["answers"])
                p = pairwise(its, ab, ba, a, b)
            except (ChecklistError, KeyError, TypeError) as e:
                results["errors"][key] = f"{e}; ab={c1.get('error')}; ba={c2.get('error')}"
                p = {"error": str(e)}
            p["cost_usd"] = sum(c.get("cost_usd") or 0 for c in (c1, c2))
            p["duration_s"] = sum(c.get("duration_s") or 0 for c in (c1, c2))
            results["pairs"][key] = p
    results["generated_questions"] = {Path(s).name: q for s, q in questions.items()}
    results["generation"] = {Path(s).name: {k: calls[("gen", s)].get(k) for k in ("cost_usd", "duration_s", "error")}
                             for s in slides}
    (out / "raw_calls.json").write_text(json.dumps({"|".join(k): v for k, v in calls.items()}, ensure_ascii=False,
                                                   indent=1), encoding="utf-8")
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=Path("docs/experiments/vlm-6view-checklist.objects.json"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    try:
        res = run(a.config, a.out, a.model, a.workers)
    except ChecklistError as e:
        print(f"error: {e}")
        return 2
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("recall", "false_positives", "flagged",
                                                                  "order_consistent_share", "consistent_share",
                                                                  "error")}
                      for k, v in {**res["objects"], **res["pairs"]}.items()}, ensure_ascii=False, indent=1))
    return 1 if res["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
