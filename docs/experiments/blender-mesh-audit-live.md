# Experiment: Blender — mesh_audit live vs offline core on benchmark fixtures

Card t_72060caa. Context: `docs/research/blender-bpy-automation.md` (branch
`docs/research-blender-bpy-automation`, methods B/C) and the sibling card t_fea03fc1 (PR #18). All defect
fixtures are **synthetic**.

## Question

1. Does `technical_library/mesh_audit/core.inspect_mesh` give the same answer when run inside the live
   Blender (data extracted exactly as `mesh_audit/blender.py` does) and offline in Python (on the source
   arrays, and on faces written by the `tools/blender/export_faces.py` logic)? What does live cost?
2. Which defect does which check catch: core counters vs BMesh checks (non-manifold, inconsistent
   normals, zero-area, loose verts, near-duplicates, self-intersecting polygon), and does a pure-Python
   port of the BMesh checks reproduce them offline?

## Methods

- **M1 live vs offline parity of `core.inspect_mesh`** (one code, three data paths: live bpy mesh,
  source arrays, export_faces points re-indexed by exact-coordinate weld).
- **M2 BMesh checks + pure-Python port as `core` extras**: inconsistent edges (two loops on one edge start
  at the same vertex), non-manifold edges (`not e.is_manifold`), zero-area (`calc_area < 1e-12`), loose
  verts, near-duplicate verts (`bmesh.ops.find_doubles`, 1 mm; port: 1 mm grid hash), bowtie polygon (two
  fan triangles with opposite normals). Port: `extra_checks()` in `offline.py` (~45 lines, stdlib only).

## Setup

```bash
uv run python experiments/blender-mesh-audit-live/offline.py fixtures "%TEMP%/agr-exp-t_72060caa"
python C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py --code \
  "ROOT=r'<worktree>';OUT=r'<temp>';exec(open(ROOT+'/experiments/blender-mesh-audit-live/live.py').read(),globals())"
uv run python experiments/blender-mesh-audit-live/offline.py audit "%TEMP%/agr-exp-t_72060caa"
```

- Fixtures: engine `from_spec` `body` mesh (all quads) of `bench-b01-box` (156 v / 141 f),
  `bench-b02-corner-niche` (263 / 236), `bench-b02t-terrace` (370 / 324); benchmark files read only.
- Defects on copies (largest facade quad): `flip1` reversed; `del1` deleted; `dup05` one corner re-pointed
  to a new vertex 0.5 mm off in +X; `bowtie` one extra self-intersecting quad 0.3 m in front of the wall.
- Live: Blender 4.4.0 via `blender_exec.py` only; meshes built with `from_pydata` in a temp collection,
  removed at the end (scene 0 objects before / 0 after, no leftover meshes). Timings: median of 5.
- Compact results: `experiments/blender-mesh-audit-live/results.json`.

## Results

### M1 parity (15 fixture variants)

| Comparison | Integer counters equal | Max deviation |
|---|---|---|
| live core vs offline core (source arrays) | 15/15 (v, f, components, dups, zero-area, boundary, multi-face, loose, unused) | `extent_m` 0.000275 mm (float32 storage in Blender) |
| exported faces (welded) vs offline core | 15/15 | — |

| Runtime, ms (median of 5) | B01 | B02 | B02t |
|---|---|---|---|
| live: extraction + core (as blender.py) | 2.3 | 3.9–4.9 | 5.4–5.7 |
| live: export_faces logic | 0.34–0.54 | 0.59–0.64 | 0.81–0.85 |
| offline core | 1.3 | 2.2 | 3.1 |
| offline weld of exported faces | 0.11 | 0.19 | 0.26 |
| live BMesh checks (all 7) | 0.50–0.55 | 0.81–0.86 | 1.09–1.13 |
| offline Python port of BMesh checks | 1.7 | 2.8 | 3.9 |

Plus ~120 ms per `blender_exec` round trip (t_b4af19e2) — dominates every number above.

### M2 detection matrix (same on all 3 fixtures; clean → defect)

Clean baselines: boundary edges 28 / 52 / 90 (open bottom and inset edges by pattern), components 2 / 2 / 3.

| Defect | core (live = offline) | BMesh live | Python port offline |
|---|---|---|---|
| flip1 | **missed** (no counter changes) | inconsistent_edges 0 → **4** | 0 → **4** |
| del1 | boundary +4 (delta only) | non_manifold +4 (delta only) | non_manifold +4 (delta only) |
| dup05 (0.5 mm) | vertices +1, boundary +4 (delta only); `duplicate_vertices_rounded` stays **0** (8 decimals) | near_dup_1mm 0 → **1** | 0 → **1** |
| bowtie | components +1, boundary +4 (delta only); `zero_area_faces_fan` stays 0 | bowtie_faces 0 → **1** | 0 → **1** |

- `zero_area_faces`, `loose_verts`, `multi_face_edges`: 0 everywhere (no fixture variant produces them).
- Python port equals BMesh on all 15 variants and on all 15 exported-and-welded copies.
- "Delta only": an absolute rule cannot gate it, because clean engine models already have boundary
  edges; even excluding ground-level edges leaves 12 / 19 / 50. Detecting `del1` needs a reference count
  (etalon) or an allowed-open-edge list from the builder.
- False positives on clean models: 0 for every BMesh check / port.

## Verdicts

| Method | Verdict | Reason |
|---|---|---|
| M1 run `core` live in Blender instead of offline | **reject** (as a separate path) | Identical counters on 15/15; only float32 extent noise (0.0003 mm). Live costs 2× the core time plus a 120 ms round trip and the Blender session lock; offline on exported faces gives the same answer. Keep `blender.py` for saved blend/FBX readback only. |
| M2 BMesh-equivalent extras in `core` (pure Python) | **adopt** | Catches 3 of 4 defects in absolute terms (flip1, dup05, bowtie) that `core` misses or sees only as deltas; 0 false positives; port = BMesh on 15/15; ≤ 4 ms at 370 verts; stdlib only, so it runs in `core`, `blender.py` and twinqa without Blender. |

## Proposed follow-up task (no issue created)

1. **mesh_audit: add winding, near-duplicate and bowtie counters to core.inspect_mesh** — scope: add
   `inconsistent_winding_edges`, `near_duplicate_vertices` (grid hash, `near_m` param, default 1 mm,
   per-object) and `self_intersecting_polygons` (opposite fan-triangle normals) to `core.py` (port from
   `experiments/blender-mesh-audit-live/offline.py:extra_checks`), surface them in `blender.py` reports,
   extend `tests/test_shared_library.py` with the 4 synthetic defects. Report-only (`delivery_passed`
   stays false). Coordinate with the twinqa orientation follow-up of PR #18 (same winding rule) so one
   implementation is shared. Missing-face detection: separate decision (reference counts or a builder
   allow-list of open edges).

## Not done / limits

- No real DCC/production file was used; fixtures are engine output + synthetic defects. Float32 effect on
  `duplicate_vertices_rounded` at 8 decimals is not exercised by these fixtures (coordinates are on a
  decimeter grid); large georeferenced coordinates could differ.
- Inter-object self-intersection (BVH) is out of scope here (PR #18 M2).
- `tests/test_shared_library.py`: 9 passed (needs `--basetemp` under the scratch dir on this host: the
  default `%TEMP%\pytest-of-artsafro` is access-denied). No project code changed.
