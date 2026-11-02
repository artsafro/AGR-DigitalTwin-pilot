# Source finish QA: can mismatched parallel inventories silently certify a partial stream?

Research card t_b3859e1f (no GitHub issue). Main SHA at work: `acdbec25649a1f059f40f4a44800f7939254a514` (no drift from the pinned SHA; `git merge origin/main` = already up to date). No pytest, no repo-source edits, no TEC26/Drive assets.

## Summary

- `source_finish_report(expected, src_faces, owners, delivered, t_areas=None, p_areas=None)` (`jobs/TEC26-OKS/scripts/qa_packages.py:128`) iterates `zip(owners, delivered)` (line 139) and never compares `len(owners)`, `len(delivered)` or `len(t_areas)`. Verified by probe (below).
- **Silent clean certification (ok=true, all counters 0) is reproduced in two cases:** (a) an extra unmatched owner `()` appended while `delivered` stays `[A]`; (b) an extra wrong finish `B` appended to `delivered` while `owners` stays `[(0,)]`. The excess entry is never visited.
- The returned `tris` is `len(owners)`, not the number of visited entries, so in case (a) it reads 2 while only 1 was judged.
- Shortening either stream on a one-polygon source is NOT silently clean (`source_polygons_not_covered` = 1), but only because the coverage check happens to see the unvisited polygon, not because lengths are compared. An excess tail can still hide behind covered polygons.
- Area path: short `t_areas` (below the visited prefix) and short `p_areas` raise `IndexError` (exception, never success); excess `t_areas`/`p_areas` are ignored silently; supplying only one of the two silently falls back to the count rule.
- Area-aware coverage differs from count coverage: a quad split into 3 triangles is `ok` with areas, `source_polygons_not_covered=1` by count.
- Reachable package QA: both callers (`qa_packages.py:410,412`) build `owners` from `match_source_faces(..., vmain["faces"])` and `delivered` from `vmain["face_uvs"]`, both written from the same `me.polygons` loop in `qa_readback.py:29-31`. Equal lengths hold for a fresh readback, but no code asserts it. No concrete witness of a delivery reaching a mismatch was found, so no delivery exposure is claimed: helper-level gap only, reachable only via a stale/edited/partial readback JSON.

## Findings (all verified by me by reading code and running the probe; no external sources)

Probe: `uv run python probe.py jobs/TEC26-OKS/scripts` (source in Reproduction). Inputs are deep-copied before and compared after each call: `inputs_unchanged` = true in all 24 cases. Source is one triangle `(0,1,2)`, expected `["A"]`, unless stated. Columns of the result: ok / tris / wrong_finish / unmatched / ambiguous / source_polygons_not_covered.

| case | entries visited | polygons that should be covered | returned |
|---|---|---|---|
| clean 1 tri | 1 of 1 | poly 0 | true / 1 / 0 / 0 / 0 / 0 |
| owners `[(0,),()]`, delivered `[A]` | 1 of 2 owners | poly 0 | **true / 2 / 0 / 0 / 0 / 0** |
| control owners `[(0,),()]`, delivered `[A,A]` | 2 of 2 | poly 0 | false / 2 / 0 / 1 / 0 / 0 |
| owners `[(0,)]`, delivered `[A,B]` | 1 of 2 delivered | poly 0 | **true / 1 / 0 / 0 / 0 / 0** |
| owners `[]`, delivered `[A]` | 0 | poly 0 | false / 0 / 0 / 0 / 0 / 1 |
| owners `[(0,)]`, delivered `[]` | 0 | poly 0 | false / 1 / 0 / 0 / 0 / 1 |
| both empty | 0 | poly 0 | false / 0 / 0 / 0 / 0 / 1 |
| equal length, delivered `[B]` | 1 | poly 0 | false / 1 / 1 / 0 / 0 / 0 |
| two source tris, clean `[(0,),(1,)]`, `[A,B]` | 2 | polys 0,1 | true / 2 / 0 / 0 / 0 / 0 |
| two tris, both streams cut to 1 | 1 | polys 0,1 | false / 1 / 0 / 0 / 0 / 1 |
| two tris, delivered cut to 1 | 1 | polys 0,1 | false / 2 / 0 / 0 / 0 / 1 |
| two tris, owners cut to 1 | 1 | polys 0,1 | false / 1 / 0 / 0 / 0 / 1 |
| areas t=[0.5], p=[0.5] | 1 | poly 0 | true / 1 / 0 / 0 / 0 / 0 |
| areas t=[] (short), p=[0.5] | 1 | poly 0 | **IndexError: list index out of range** |
| areas t=[0.5, 9.0] (excess) | 1 | poly 0 | true (excess ignored) |
| areas t=[0.5], p=[] (short) | 1 | poly 0 | **IndexError: list index out of range** |
| areas t=[0.5], p=[0.5, 7.0] (excess) | 1 | poly 0 | true (excess ignored) |
| only `t_areas`, or only `p_areas` | 1 | poly 0 | true (count fallback) |
| quad, 3 tris, no areas | 3 | poly 0 needs len-2 = 2 | false / 3 / 0 / 0 / 0 / 1 |
| quad, 3 tris, t=[.5,.25,.25], p=[1.0] | 3 | poly 0 area 1.0 | true / 3 / 0 / 0 / 0 / 0 |
| quad, 2 tris, t=[.5,.25], p=[1.0] | 2 | poly 0 | false / 2 / 0 / 0 / 0 / 1 |
| quad, 2 tris, count rule | 2 | poly 0 | true / 2 / 0 / 0 / 0 / 0 |
| quad, owners 3 `[(0,),(0,),()]`, delivered 2, areas | 2 of 3 | poly 0 | **true / 3** (unmatched tail unvisited) |

The two exceptions are exceptions (fail loud), not success. The unsafe class is exactly "excess tail on one stream beyond the shorter one": `ok=true`, `unmatched=0`.

## How it applies to this repository

- Function: `jobs/TEC26-OKS/scripts/qa_packages.py:128-157` (`zip` at 139; `tris` = `len(owners)` in the return).
- Callers on main: `qa_packages.py:410` (VPM) and `:412` (NPM), the only production callers. `owners` = `match_source_faces(body..., vmain/nmain)` (`:404-405`, one entry per out face); `delivered` = `vfin`/`nfin` comprehensions over `vmain/nmain["face_uvs"]` (`:406-408`); `t_areas` = `tri_areas(...)` (one per out face); `p_areas` = `poly_areas(body)` (one per source face). Lengths originate from the same polygon loop at `qa_readback.py:29,31`; `face_uvs` exists only when `uv_layers` is non-empty (`:30`), a missing key is a `KeyError` (exception), not a length mismatch.
- Tests: `tests/jobs/test_tec26_ac08_pilot.py:579-665` cover empty, "partial" (both streams cut by one: lines 581, 658), wrong and unmapped finishes. No test shortens or lengthens only one stream, so cases (a)/(b) are undetected by the suite.
- Helper-level behaviour = silent `ok=true` on an excess tail (proven). Reachable package QA = only if readback `faces` and `face_uvs` lengths differ; nothing guards that and no witness produces it.
- Retro: the PR #618 proposal #4 wording was not located by keyword search in `docs/retros/2026-10-22-tec26-colouring-claude.md`; the codex retro was not read (Open question 1).

## Reproduction (self-contained; needs numpy, run in the worktree venv)

```python
"""Standalone probe of qa_packages.source_finish_report. Usage: python probe.py <path to jobs/TEC26-OKS/scripts>"""
import sys, copy, json, importlib.util
sys.path.insert(0, sys.argv[1])
import qa_packages as q
R = q.source_finish_report
def run(name, args, kw, note):
    before = copy.deepcopy((args, kw))
    try:
        r = R(*args, **kw); out = {k: r[k] for k in ("ok","tris","wrong_finish","unmatched","ambiguous","source_polygons_not_covered")}
    except Exception as e:
        out = {"EXC": type(e).__name__ + ": " + str(e)}
    out["inputs_unchanged"] = before == (args, kw)
    print(json.dumps({"case": name, "result": out, "note": note}))
T = [(0,1,2)]; E = ["A"]
run("clean_1tri", (E,T,[(0,)],["A"]), {}, "visited 1/1; polygon 0 covered")
run("extra_owner_only", (E,T,[(0,),()],["A"]), {}, "zip visits 1 of 2 owners; owner () never visited")
run("extra_owner_full", (E,T,[(0,),()],["A","A"]), {}, "control: both visited, unmatched=1 expected")
run("extra_delivered_B", (E,T,[(0,)],["A","B"]), {}, "zip visits 1 of 2 delivered; B never visited")
run("short_owners", (E,T,[],["A"]), {}, "owners empty, delivered has 1")
run("short_delivered", (E,T,[(0,)],[]), {}, "delivered empty, owners 1: polygon 0 never judged")
run("both_empty", (E,T,[],[]), {}, "must be not ok")
run("equal_len_wrong", (E,T,[(0,)],["B"]), {}, "wrong_finish=1 expected")
T2 = [(0,1,2),(0,2,3)]; E2 = ["A","B"]
run("two_clean", (E2,T2,[(0,),(1,)],["A","B"]), {}, "2/2")
run("two_short_both", (E2,T2,[(0,)],["A"]), {}, "polygon 1 uncovered expected")
run("two_short_delivered_only", (E2,T2,[(0,),(1,)],["A"]), {}, "owner 1 visited? zip stops; polygon 1 uncounted")
run("two_short_owners_only", (E2,T2,[(0,)],["A","B"]), {}, "")
# areas
run("areas_paired_ok", (E,T,[(0,)],["A"]), {"t_areas":[0.5],"p_areas":[0.5]}, "")
run("areas_t_short", (E,T,[(0,)],["A"]), {"t_areas":[],"p_areas":[0.5]}, "t_areas shorter than visited")
run("areas_t_excess", (E,T,[(0,)],["A"]), {"t_areas":[0.5,9.0],"p_areas":[0.5]}, "excess ignored")
run("areas_p_short", (E,T,[(0,)],["A"]), {"t_areas":[0.5],"p_areas":[]}, "p_areas shorter than src_faces")
run("areas_p_excess", (E,T,[(0,)],["A"]), {"t_areas":[0.5],"p_areas":[0.5,7.0]}, "excess p ignored")
run("only_t_areas", (E,T,[(0,)],["A"]), {"t_areas":[0.5]}, "falls back to count")
run("only_p_areas", (E,T,[(0,)],["A"]), {"p_areas":[0.5]}, "falls back to count")
Q = [(0,1,2,3)]
run("split_count_path", (E,Q,[(0,)]*3,["A"]*3), {}, "quad, 3 tris: count 3!=2")
run("split_area_path", (E,Q,[(0,)]*3,["A"]*3), {"t_areas":[0.5,0.25,0.25],"p_areas":[1.0]}, "area covers")
run("split_area_short_cover", (E,Q,[(0,)]*2,["A"]*2), {"t_areas":[0.5,0.25],"p_areas":[1.0]}, "area 0.75<1")
run("quad_two_tri_count", (E,Q,[(0,)]*2,["A"]*2), {}, "count covered")
run("area_zip_misalign", (E,Q,[(0,)]*2+[()],["A"]*2), {"t_areas":[0.5,0.5,0.0],"p_areas":[1.0]}, "")
```

## Proposed next tasks

1. **Length-equality precondition in `source_finish_report`**, size S, `Advances #149` (L2 self-checks of the NPM/VPM roadmap). Scope: at entry, if `len(owners) != len(delivered)`, or `t_areas` is given with another length than `owners`, or exactly one of `t_areas`/`p_areas` is given, or `len(p_areas) != len(src_faces)`, return `ok=false` with new keys `length_mismatch` and `lengths` instead of zip-truncating or raising `IndexError`. Acceptance pair: (clean) 1-tri, 2-tri and quad-split-area clean streams return unchanged values for all existing keys; (mismatch) owner excess, delivered excess, `t_areas` short/excess, `p_areas` short/excess and a single area list each give `ok=false` plus an explicit `length_mismatch` diagnostic, no exception. Regression tests in `tests/jobs/test_tec26_ac08_pilot.py`.
2. **Caller length check at `qa_packages.py:404-412`**, size S, `Advances #149`. Scope: before the two calls add `check("source_finish_stream_lengths_vpm"/"_npm", ...)` recording `len(faces)`, `len(face_uvs)`, `len(owners)`, `len(delivered)`, failing when any differs, so readback truncation is reported at package level independent of the helper. Acceptance pair: clean real-shape readback passes with equal lengths; a readback with `face_uvs` shortened or lengthened by one gives an explicit failed check naming the lengths. No change to historical QA outputs.

Proposals only; neither changes `passed`/`ok` of any existing report.

## Open questions for the user

1. Is retro #618 proposal #4 exactly the unequal-length concern, or wider (owner/finish/area ordering)? Equal-length misordered streams are not detectable by length checks and are out of scope here.
2. Proposal 1 alone, or both? Proposal 2 adds new check names to the QA report schema.
