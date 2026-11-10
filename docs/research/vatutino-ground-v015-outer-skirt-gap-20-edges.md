# Vatutino Ground v015: why 20 outer-boundary edges measure GND-03 drop 0

Research card t_b85e92b1 (Kanban, no GitHub issue). Source of the question: PR #1162 "Not done".
Input: `C:/x/t_5e2eb833/v009/readback-npm.json` (Blender readback of `0000_Vatutino_Ground.fbx`,
the PR #1153 run v009; not in git). Code revisions: `main` = `070b0be5`,
`improve/gnd03-skirt-collinear-perimeter-edges` = `9e3694dd` (PR #1162).

## Summary

- The skirt is **not missing**. The 20 edges are not open edges of the Ground mesh. Each of them is
  shared by two `TileLight` faces: one surface face and one face of a steep band (slope 80.1-81.5°).
- The 20 edges are contiguous: outer-loop indices 884..903. They form two near-parallel chains that meet at a
  tip at (-13.325, -92.775). The lower chain is a ramp (z 143.50 -> 145.50). The upper chain is flat
  (z ~145.50-145.53). The band between the chains is 19 closed `TileLight` faces, and no band edge is open.
- GND-03 (`src/twinqa/scene.py:1011` on main, `:1070` on the PR #1162 branch) counts a face as "surface"
  only when `|nz|` dominates, i.e. slope <= 45°. The band is steeper, so the check cuts it out of the
  surface. Its rim then becomes "perimeter" that has no lower copy, and the measured drop is 0.
- The builder is correct. `add_skirt` (`src/dt_ai/geometry/ground_cake.py:1366`, `if len(uses) != 1: continue`)
  extrudes only edges that are open on level 0. The band edges are not open, so no skirt is due there.
  `clip_curtain` (`jobs/VATUTINO-SITE/build_ground_v015.py:59-107`) is not involved: the stretch has no
  `Stairs` faces.
- Control: take every non-`Skirt` face as the surface. The outer loop then has 1,251 edges, all >= 1 m (min 1.000).
  The same holds with a slope-independent classifier (`nz > 1e-6·|n|`): 1,251 / 1,251 >= 1 m.
- Fix (S): change the GND-03 measurement, not the builder. No user decision is needed for the outer
  ring. The overall GND-03 0.000 m of #1153 still stays, because of the inner rings (#1133 case 2,
  a user decision).

## Findings

All numbers come from one command, which runs the script in [Reproduction](#reproduction):

```
uv run python skirt20_repro.py C:/x/t_5e2eb833/v009/readback-npm.json scene_branch.py
# scene_branch.py = git show origin/improve/gnd03-skirt-collinear-perimeter-edges:src/twinqa/scene.py
```

Output, cut to the lines that matter (verified, run on 2026-11-10 in this worktree):

```
mesh 27431 verts 46479 polys; main ('ok', 0.0) branch ('ok', 0.0)
perimeter 10767 loops 503 outer 1270 main >=1m 1250 <1m 20 | branch >=1m 1250 <1m 20
bad loop indices 884 .. 903 contiguous True
steep band faces 19 materials ['M_Vatutino_Ground_TileLight'] slope 80.1..81.5 deg band edges used by <2 faces 0
control non-Skirt surface: outer 1251 >=1m 1251 <1m 0 min 1.000
up-dominant (scene.py:1011) all perimeter edges 10767 zero 587 0<d<1 8322 >=1 1858
non-Skirt control all perimeter edges 8284 zero 545 0<d<1 5866 >=1 1873
variant nz>1e-6|n|: outer 1251 >=1m 1251 <1m 0 min 1.000 skirt faces classified up 13
```

### F1. The 20 edges (main and branch give identical results)

| loop idx | vertex pair | from (x, y, z) | to (x, y, z) | drop main | drop branch | faces on edge |
|---|---|---|---|---|---|---|
| 884 | 637-638 | -9.967, -90.129, 143.875 | -9.191, -89.517, 143.499 | 0.000 | 0.000 | TileLight steep + up |
| 885 | 637-16240 | -9.967, -90.129, 143.875 | -10.711, -90.717, 144.234 | 0.000 | 0.000 | steep + up |
| 886 | 16240-16241 | -10.711, -90.717, 144.234 | -11.219, -91.116, 144.479 | 0.000 | 0.000 | up + steep |
| 887 | 16241-16244 | -11.219, -91.116, 144.479 | -11.729, -91.515, 144.733 | 0.000 | 0.000 | up + steep |
| 888 | 16244-17905 | -11.729, -91.515, 144.733 | -12.236, -91.917, 144.972 | 0.000 | 0.000 | up + steep |
| 889 | 17905-17912 | -12.236, -91.917, 144.972 | -12.656, -92.247, 145.176 | 0.000 | 0.000 | steep + up |
| 890 | 17912-17914 | -12.656, -92.247, 145.176 | -12.668, -92.256, 145.181 | 0.000 | 0.000 | steep + up |
| 891 | 17914-18095 | -12.668, -92.256, 145.181 | -12.742, -92.316, 145.218 | 0.000 | 0.000 | steep + up |
| 892 | 18095-18096 | -12.742, -92.316, 145.218 | -13.249, -92.715, 145.464 | 0.000 | 0.000 | up + steep |
| 893 | 18096-18099 | -13.249, -92.715, 145.464 | -13.325, -92.775, 145.500 | 0.000 | 0.000 | up + steep |
| 894 | 18099-18101 | -13.325, -92.775, 145.500 | -13.258, -92.715, 145.499 | 0.000 | 0.000 | steep + up |
| 895 | 18100-18101 | -12.809, -92.316, 145.502 | -13.258, -92.715, 145.499 | 0.000 | 0.000 | steep + up |
| 896 | 17913-18100 | -12.739, -92.256, 145.497 | -12.809, -92.316, 145.502 | 0.000 | 0.000 | up + steep |
| 897 | 17913-17915 | -12.739, -92.256, 145.497 | -12.359, -91.917, 145.508 | 0.000 | 0.000 | steep + up |
| 898 | 16249-17915 | -11.905, -91.515, 145.511 | -12.359, -91.917, 145.508 | 0.000 | 0.000 | up + steep |
| 899 | 16246-16249 | -11.456, -91.116, 145.515 | -11.905, -91.515, 145.511 | 0.000 | 0.000 | steep + up |
| 900 | 635-16246 | -11.005, -90.717, 145.518 | -11.456, -91.116, 145.515 | 0.000 | 0.000 | up + steep |
| 901 | 633-635 | -10.994, -90.707, 145.518 | -11.005, -90.717, 145.518 | 0.000 | 0.000 | steep + up |
| 902 | 633-634 | -10.994, -90.707, 145.518 | -9.967, -89.796, 145.527 | 0.000 | 0.000 | up + steep |
| 903 | 634-636 | -9.967, -89.796, 145.527 | -9.652, -89.517, 145.529 | 0.000 | 0.000 | up + steep |

The loop index counts along an ordered walk of the outer loop. The walk starts at the first vertex of the
first edge in the loop, so the index is stable only for this script and this readback. The stretch runs from
the site boundary line y = -89.517 (x = -9.191) down the ramp to the tip and back along the flat chain to
y = -89.517 (x = -9.652). Indices 883 and 904 (drop 1.0 each) are the skirted boundary edges on y = -89.517.

### F2. Why the drop is 0: the GND-03 surface classifier, not a missing skirt quad

- `_skirt_perimeter_drop` (main, `src/twinqa/scene.py:1008-1013`) keeps a polygon as "surface" only if
  `nz > 0 and |nz| >= |nx| and |nz| >= |ny|`, i.e. slope <= 45°. The 19 band faces are 80.1-81.5°, so the
  check drops them. The surface outer loop then detours around the band, and the band rim becomes a
  "perimeter". These rim edges have no lower copy at the same XY, because they are interior creases.
  The drop is therefore 0 (`scene.py:1063`: the only XY copy is the rim edge itself at the same Z). PR #1162 changes only the pairing
  (collinear coverage), not the classifier (branch `scene.py:1070`), so it gives the same 20 zeros.
- Every one of the 20 edges is used by exactly two faces (one `up`, one `steep`), and none of the 19 band faces
  has an open edge (`band edges used by <2 faces 0`). For the builder this stretch is closed surface.

### F3. Builder trace (read the code; not re-run)

- `jobs/VATUTINO-SITE/build_ground_v015.py:214` builds the curtain:
  `clip_curtain(gc.add_skirt(surface), <Stairs triangles>)`.
- `src/dt_ai/geometry/ground_cake.py:1352-1377` `add_skirt` emits two triangles per edge that is used by exactly one
  level-0 face (`:1366`). The band faces are level-0 `TileLight` faces of the base surface, so their edges
  are counted twice and get no skirt. This is correct: they are not boundary edges.
- `clip_curtain` (`build_ground_v015.py:59-107`) cuts or drops `Skirt` faces only near `Stairs` triangles
  (`:90-105`). The window x -13.6..-8.9, y -93.1..-89.2 holds 31 up faces (24 TileLight, 7 TileRed) and
  35 steep faces (4 Skirt, 23 TileLight, 8 TileRed), and no `Stairs` face (scratch `skirt20_mats.py`, same readback).
  So the stair-wall drop path does not apply here.
- `ground-notch-approval-v015.json` (D191) works in another coordinate frame (triangle near -7691, -15248).
  I did not map it to this local frame, so its relation to this stretch is **unverified**. The band does not
  depend on it: it is relief, a near-vertical step of up to ~2 m over ~0.33 m between the ramp and the
  platform.
- Where the step comes from in the source (TIN elevations of the adapter, or a v014 source-mesh feature)
  is **unverified**. The adapter JSON was not opened, because it is outside this card's time box.

### F4. Note on PR #1162's inner-ring numbers (side finding)

PR #1162 reports the inner loops as "9,497 edges: 357 measure 0 and 8,888 are under 1 m". This run gives
10,767 perimeter edges in total: 587 zero, 8,322 with 0 < d < 1, and 1,858 >= 1. Taking away the outer loop's
20 zero and 1,250 >= 1 edges leaves 9,497 inner edges: 567 zero, 8,322 with 0 < d < 1, and 608 >= 1. The
9,497 total matches, but the split does not match #1162 (357 + 8,888 = 9,245 ≠ 9,497). The outer-ring numbers
match exactly. This report does not depend on the inner split, and #1162 should re-check it.

No external sources were needed. Every finding above was checked by running the script or reading the code.

## How it applies to this repository

- `src/twinqa/scene.py:1008-1013` (main) / branch `:1067-1072`: the surface classifier is the cause.
- `src/dt_ai/geometry/ground_cake.py:1352-1377` (`add_skirt`): correct for this stretch, no change.
- `jobs/VATUTINO-SITE/build_ground_v015.py:59-107, 214` (`clip_curtain`): not involved here.
- `tests/qa/test_decision_checks.py`: the GND-03 tests (#1133) need one new regression for a steep interior band.
- The [D125] sheet `docs/deliveries/vatutino-site-2026-11-09.md` (PR #1153) says "Ground skirt drop 0.000 m".
  For the outer ring that is a false fail of the check. The remaining 0.000 comes from the inner rings.

## Proposed next tasks

1. **GND-03: steep interior Ground faces are surface, not perimeter** (effort S, value M).
   Change the "surface" classifier in `_skirt_perimeter_drop` (`src/twinqa/scene.py`). Count every face with an
   upward component (`nz > ε·|n|`, ε ≈ 1e-6) and keep the skirt walls (`nz ≈ 0`) out. An alternative is to
   exclude faces whose material ends in `_Skirt`, but that ties the check to a naming convention. Measured on this
   readback, the outer loop becomes 1,251 / 1,251 >= 1 m. Risk: 13 `Skirt` faces also get `nz > 1e-6·|n|`
   (float noise or skirts that are not quite vertical). The tolerance must exclude them, so pick ε from the
   largest skirt `nz/|n|`, or combine it with the material test. Test first: a synthetic quad Ground with a
   75° interior step band and a full skirt must pass at 1.0. Today it gives 0.0, which is the RED test.
   Files: `src/twinqa/scene.py`, `tests/qa/test_decision_checks.py`. Stack on PR #1162's branch, or wait
   for its merge. Advances #298.
2. **Vatutino D125 sheet: re-state the Ground skirt row after task 1** (effort S, value S). Re-run GND-03 on
   the #1153 readback and split the result into outer ring (expected pass) and inner rings (#1133 case 2). Files:
   `docs/deliveries/vatutino-site-2026-11-09.md` only. Advances #298.
3. **Trace the 80° relief step at (-13..-9, -93..-89.5) to its source** (effort S, value S). Open the
   adapter `ground_elements` / `elevations` near this XY. Find out whether the step is a real retaining
   edge (a ramp beside a platform) or a TIN artefact of two close elevation marks. Report only. Advances #298.

## Open questions for the user

1. Is the near-vertical ~2 m step between the ramp and the platform at the south boundary
   (x -13.3..-9.2, y -92.8..-89.5) intended relief, for example a retaining edge? If it is, the
   mesh is correct and only GND-03 needs task 1. If not, task 3 becomes a geometry fix.
2. For GND-03, should "surface" be defined by geometry (any upward normal) or by material (everything except
   `*_Skirt`)? Recommendation: geometry with a tolerance, plus the material test as a guard.

## Reproduction

Run from the repository root (`src/` on `sys.path`). Argument 2 is the PR #1162 version of `scene.py`
(`git show origin/improve/gnd03-skirt-collinear-perimeter-edges:src/twinqa/scene.py > scene_branch.py`).

```python
"""Repro: the 20 GND-03 zero-drop edges of Vatutino Ground v015 (readback of PR #1153 run v009).

uv run python skirt20_repro.py <readback-npm.json> <scene_branch.py>
"""
import importlib.util, json, math, sys
from collections import defaultdict
sys.path.insert(0, "src")
from twinqa.scene import _skirt_perimeter_drop, _polygon_normal, _xy_key

spec = importlib.util.spec_from_file_location("scene_branch", sys.argv[2])
br = importlib.util.module_from_spec(spec); spec.loader.exec_module(br)

d = json.load(open(sys.argv[1]))
m = next(x for x in (d["meshes"] if isinstance(d, dict) else d) if x["name"] == "SM_Vatutino_Ground")
fg = m["face_geometry"]; V, P, M = fg["vertices"], fg["polygons"], fg["polygon_material"]
print("mesh", len(V), "verts", len(P), "polys; main", _skirt_perimeter_drop(m), "branch", br._skirt_perimeter_drop(m))

def is_up(p):
    n = _polygon_normal(V, p)
    return n[2] > 0 and abs(n[2]) >= abs(n[0]) and abs(n[2]) >= abs(n[1])
segs = []; seen = set(); low = {}; use = defaultdict(list)
for f, p in enumerate(P):
    for k in range(len(p)):
        a, b = p[k], p[(k + 1) % len(p)]; e = (min(a, b), max(a, b)); use[e].append(f)
        ka, kb = _xy_key(*V[a][:2]), _xy_key(*V[b][:2])
        if ka != kb:
            key, z = ((ka, kb), (V[a][2], V[b][2])) if ka <= kb else ((kb, ka), (V[b][2], V[a][2]))
            c = low.setdefault(key, list(z)); c[0] = min(c[0], z[0]); c[1] = min(c[1], z[1])
        if e not in seen and math.hypot(V[b][0] - V[a][0], V[b][1] - V[a][1]) > br._SKIRT_XY_TOL:
            seen.add(e); segs.append((*map(float, V[a][:3]), *map(float, V[b][:3])))

def drop_main(i, j):  # same pairing as main::_skirt_perimeter_drop
    ki, kj = _xy_key(*V[i][:2]), _xy_key(*V[j][:2])
    key, zt = ((ki, kj), (V[i][2], V[j][2])) if ki <= kj else ((kj, ki), (V[j][2], V[i][2]))
    b = low.get(key); return max(0.0, min(zt[0] - b[0], zt[1] - b[1])) if b else 0.0

def outer_loop(faces):
    cnt = defaultdict(int)
    for f in faces:
        p = P[f]
        for k in range(len(p)):
            a, b = p[k], p[(k + 1) % len(p)]; cnt[(min(a, b), max(a, b))] += 1
    per = [e for e, c in cnt.items() if c == 1]; adj = defaultdict(list)
    for e in per: adj[e[0]].append(e); adj[e[1]].append(e)
    seen_e, loops = set(), []
    for e in per:
        if e in seen_e: continue
        comp, st = [], [e]
        while st:
            x = st.pop()
            if x in seen_e: continue
            seen_e.add(x); comp.append(x); st += [y for v in x for y in adj[v] if y not in seen_e]
        loops.append(comp)
    area = lambda c: (max(V[v][0] for e in c for v in e) - min(V[v][0] for e in c for v in e)) * \
                     (max(V[v][1] for e in c for v in e) - min(V[v][1] for e in c for v in e))
    loops.sort(key=area, reverse=True); outer = set(loops[0])
    cur = loops[0][0][0]; order = []; used = set()  # ordered walk
    while True:
        nxt = [e for e in adj[cur] if e in outer and e not in used]
        if not nxt: break
        e = nxt[0]; used.add(e); order.append(e); cur = e[1] if e[0] == cur else e[0]
    return per, len(loops), order

top = [f for f, p in enumerate(P) if is_up(p)]
n_per, n_loops, order = outer_loop(top)
dm = [drop_main(*e) for e in order]
db = [br._skirt_edge_drop(V[i], V[j], segs) for i, j in order]
bad = [k for k, x in enumerate(dm) if x < 1.0]
print("perimeter", len(n_per), "loops", n_loops, "outer", len(order),
      "main >=1m", sum(x >= 1 for x in dm), "<1m", len(bad), "| branch >=1m", sum(x >= 1 for x in db), "<1m", sum(x < 1 for x in db))
print("bad loop indices", bad[0], "..", bad[-1], "contiguous", bad == list(range(bad[0], bad[-1] + 1)))
band = set()
for k in bad:
    i, j = order[k]; e = (min(i, j), max(i, j))
    fs = use[e]; band |= {f for f in fs if not is_up(P[f])}
    print(k, e, [round(c, 3) for c in V[i]], [round(c, 3) for c in V[j]],
          f"main {dm[k]:.3f} branch {db[k]:.3f}", "faces", [(M[f][len("M_Vatutino_Ground_"):], "up" if is_up(P[f]) else "steep") for f in fs])
# the steep band between the two chains
ang = []
for f in band:
    n = _polygon_normal(V, P[f]); ang.append(math.degrees(math.atan2(math.hypot(n[0], n[1]), abs(n[2]))))
open_e = [e for f in band for e in ((min(P[f][k], P[f][(k + 1) % len(P[f])]), max(P[f][k], P[f][(k + 1) % len(P[f])])) for k in range(len(P[f]))) if len(use[e]) < 2]
print("steep band faces", len(band), "materials", sorted({M[f] for f in band}), f"slope {min(ang):.1f}..{max(ang):.1f} deg", "band edges used by <2 faces", len(open_e))
# control: surface = every non-Skirt face (steep band included); is the outer loop fully skirted?
n_per2, n_loops2, order2 = outer_loop([f for f in range(len(P)) if not M[f].endswith("_Skirt")])
dm2 = [drop_main(*e) for e in order2]
print("control non-Skirt surface: outer", len(order2), ">=1m", sum(x >= 1 for x in dm2), "<1m", sum(x < 1 for x in dm2), f"min {min(dm2):.3f}")
for name, per in (("up-dominant (scene.py:1011)", n_per), ("non-Skirt control", n_per2)):
    ds = [drop_main(*e) for e in per]
    print(name, "all perimeter edges", len(per), "zero", sum(x == 0 for x in ds), "0<d<1", sum(0 < x < 1 for x in ds), ">=1", sum(x >= 1 for x in ds))
# variant classifier: any upward component (nz > 1e-6 |n|), slope-independent, still excludes vertical skirt walls
def any_up(p):
    n = _polygon_normal(V, p); return n[2] > 1e-6 * math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
n_per3, n_loops3, order3 = outer_loop([f for f, p in enumerate(P) if any_up(p)])
dm3 = [drop_main(*e) for e in order3]
print("variant nz>1e-6|n|: outer", len(order3), ">=1m", sum(x >= 1 for x in dm3), "<1m", sum(x < 1 for x in dm3), f"min {min(dm3):.3f}",
      "skirt faces classified up", sum(1 for f, p in enumerate(P) if M[f].endswith("_Skirt") and any_up(p)))
```
