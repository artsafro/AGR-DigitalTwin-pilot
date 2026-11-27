# Ground/Site: map Moskovsky draft evidence to the three shared handoffs

Status: pilot research, read-only. Scope: does draft PR #1979 (head `5f5cf971`) prove any of the three
shared Ground/Site handoffs tracked by #1969, or only a job-local route?

## Summary

Draft PR #1979 commits a **job-local NPM-only** site assembly for `moskovsky-sosh1200`
(`jobs/moskovsky-sosh1200/scripts/assemble_site_npm.py`): Ground v003 + MAF v002 + Flora v002 are
baked, re-named to the NPM grammar, joined and exported as **one** triangulated Ground FBX
(`use_triangles=True`), plus a `assembled.blend` and an **incomplete** NPM ZIP (`--allow-incomplete`,
no OKS → V001 fail). It does **not** prove any of the three shared handoffs: there is no committed
working quad master (row 1), no VPM profile or surface-parity readback (row 2), and no dual-profile
export with a separate working FBX per D366 (row 3). The three shared gaps remain open in
`docs/architecture/ground-route.events.yaml` (`pairing`, `ground-atlas`, `obj-to-export`), each with no
shared owner. The PR is a job-local instance of route step 11 (NPM → export), not a shared route.

## Findings

The three shared gaps named by #1969 are already tracked as open, owner-unset stages in the route map
`docs/architecture/ground-route.events.yaml`: `pairing` (stage `quads`), `ground-atlas` (stage `npm`),
`obj-to-export` (stage `export`). Below is the gap-to-deliverable table required before #1969 can split.

| # | Gap (shared handoff) | Job evidence (PR #1979 `5f5cf971`) | Current shared owner / path | Matching or adjacent issue/PR | Missing verifiable deliverable | Remaining prerequisites / decision gates | Conclusion |
|---|---|---|---|---|---|---|---|
| 1 | Flat working quads before relief | No working quad FBX committed. `STATE.md`: Ground "v002 geometry accepted … (frozen)"; v003 = "IDs + textures on frozen geometry"; outputs (gpzu 2 940 tris, uncut 4 580 tris) live in `C:/x`, not git. `assemble_site_npm.py` imports OBJ (`bpy.ops.wm.obj_import`) then `bake()`/join and exports `use_triangles=True` — no quad stage. | **No shared owner verified.** `routes/site.md` step 3: builder writes *triangulated* OBJ, "not a working quad FBX; v015 replays Vatutino only". Map `pairing` open, owner unset. | #1968 (marks `pairing` open); #1919 (validator must check a named Ground *work* FBX under D312/D366); D312, D366 | Reusable shared pre-relief working master (quad FBX) keeping boundary, holes, seams, slot/material IDs and UV, judged under D312 (not the Vatutino D157 threshold) | None — stage is unimplemented; #1919 is the first verifiable consumer of such a file | **NOT PROVEN** (job-local, no quad stage) |
| 2 | NPM atlas preserving surface & placement against VPM | Job-local atlas derivation only: Ground tiled maps (`npm_tiled_maps.py`), MAF 512 atlas v008, Flora atlas d/o, applied in `assemble_site_npm.py`. NPM-only, no VPM profile, no surface-parity readback. Triangle totals (Ground 11 736 / GroundEl 47 344 / Flora 44 615 = 103 707) are budget evidence, not parity. | **No shared owner verified.** `routes/site.md` step 10: "the OKS derive alias does not convert Ground"; `npm-light` covers MAF only. Map `ground-atlas`: "agr vpm-to-npm не конвертирует Ground … npm_atlas_udim.py — job-specific … переход мастер→атлас→НПМ FBX не доказан, не измерен." | #1954 / #1956 (Ground methods benchmark — trustworthy readback before any parity); #1968 | Shared Ground atlas derivation preserving the same surface and placement coordinates under D293(5), with distinct atlas/UDIM evidence and a trusted readback proving parity vs VPM | #1954/#1956 readback repair must land before any parity/tolerance/diagonal rule can be proposed | **NOT PROVEN** (job-local NPM atlas; matching triangle count alone ≠ parity) |
| 3 | Assembled export: both delivery profiles + separate work FBX | One combined **NPM** FBX (`SM_Ground`/`SM_GroundEl`/`SM_GroundElGlass`/`SM_Flora`) exported `use_triangles=True` (triangulated delivery), plus `assembled.blend` (Blender source, not a work FBX) and an incomplete NPM ZIP (`agr package-npm --allow-incomplete`, no OKS → V001). No VPM delivery; no separate working FBX with quads. | **No shared owner verified.** `routes/site.md` step 11: "Assembled-site export is job/DCC work, not a generic command." Map `obj-to-export`: `ground_json_to_fbx.py` is surface-only; historical `assemble_delivery.py` is triangulated (`use_triangles=True`), not D366. | #1968; #1919 (validator); #1908 (closed, VPM packager UDIM table) | Shared combined exporter producing **both** profile deliveries (NPM + VPM) and a separate working FBX per D366, proven by readback (roles, coordinates, distinct exported files) | **Depends on row 2 (NPM → export).** #1919 must first accept a named Ground work FBX | **NOT PROVEN** at shared level. Job-local NPM-only assembly + incomplete package alone = no shared dual-profile export; work FBX absent → **not measured** |

Dependency: row 3 (`export`) depends on row 2 (`npm`). NPM → export is explicit; a job-local NPM
assembly does not by itself establish the shared export handoff.

### Verification of citations

All citations below were read directly (git show / gh view / read_file), not taken on faith:

- `gh pr view 1979` — draft, head `5f5cf97146e6398e843c30f1f2ebad4ea0bd9976`, base `main`.
- `git show 5f5cf971:jobs/moskovsky-sosh1200/STATE.md` — "Site NPM package v001 … diagnostic, not passed";
  Fails: V001 (no OKS), V003 skirt, V004 topology, xview, 7 Ground PNG > 3 MiB.
- `git show 5f5cf971:jobs/moskovsky-sosh1200/scripts/assemble_site_npm.py` — full script; exports only a
  single NPM FBX with `use_triangles=True`; writes `assembly.json` + `assembled.blend`; no VPM, no work FBX.
- `git show 5f5cf971:jobs/moskovsky-sosh1200/TASK.md` — job decisions, Ground v002 geometry accepted.
- `routes/site.md` steps 3, 9, 10, 11 — read in full.
- `docs/decisions.md` D293 (line 305), D312 (line 322), D366 (line 354).
- `docs/architecture/ground-route.events.yaml` — `pairing` (line 324), `ground-atlas` (line 384),
  `obj-to-export` (line 408); all open, owner unset.
- Rechecked for overlap: #1404/#1406/#1407 (CLOSED — UCX / Ground command / placement, adjacent, not this
  scope), #1908 (CLOSED — VPM packager UDIM table), #1919 (OPEN — package validator, Ground work FBX),
  #1954/#1956 (OPEN — Ground methods benchmark, one measurement-path repair), #1968 (OPEN — route map marks
  the three gaps). None of these implement any of the three shared handoffs.

### Exercised vs read-only

- **Exercised (read directly):** routes/site.md; docs/decisions.md (D293/D312/D366); #1969; PR #1979;
  `STATE.md`, `TASK.md`, `scripts/assemble_site_npm.py` at `5f5cf971`; `ground-route.events.yaml`;
  #1404/#1406/#1407/#1908/#1919/#1954/#1956/#1968 via `gh issue view`.
- **Not exercised:** the actual FBX/OBJ/blend/ZIP outputs (they live in `C:/x/moskovsky-sosh1200/`, not in
  git). No DCC, no readback, no tests were run. The work-FBX sub-criterion of row 3 is therefore
  **not measured** (file absent from the commit), not a pass or fail.

## How it applies to this repository

- `routes/site.md` steps 3, 9, 10, 11 already document that the shared command surface stops short of all
  three handoffs; PR #1979 does not close that gap.
- `docs/architecture/ground-route.events.yaml` already names the three gaps (`pairing`, `ground-atlas`,
  `obj-to-export`); the map is truthful and needs no edit from this evidence.
- `jobs/moskovsky-sosh1200/scripts/assemble_site_npm.py` is a job-local analogue of the historical
  `jobs/VATUTINO-SITE/assemble_delivery.py` (also `use_triangles=True`), confirming route step 11 is still
  job/DCC work rather than a shared exporter.
- `docs/decisions.md` D366 (work FBX with quads for every package type) has no shared owner yet; the
  Moskovsky assembly ships no work FBX.

## Proposed next tasks

1. **Split #1969 `quads`: shared pre-relief working-master stage** — Add a reusable route stage that emits
   a quad working master (boundary, holes, seams, slot/material IDs, UV evidence) before relief, judged
   under D312. Scope: a command + verifier for the master, with a Ground test object. Value/effort: **M**.
   `Advances #1969`.

2. **Split #1969 `npm`: shared Ground atlas derivation + parity readback** — Reuse existing atlas cores to
   derive a Ground NPM atlas from a VPM master preserving surface/placement (D293(5)); gate the parity proof
   on the repaired readback from #1954/#1956. Scope: derive command + trusted readback evidence, no
   tolerance until #1954/#1956 land. Value/effort: **M**. `Advances #1969`.

3. **Split #1969 `export` (depends on `npm`): combined dual-profile exporter + work FBX** — A shared
   combined-site exporter producing both NPM and VPM deliveries and a separate working FBX per D366, proven
   by readback (roles, coordinates, distinct files). Scope: export + readback + #1919 validator wiring.
   Value/effort: **L**. `Advances #1969`.

## Open questions for the user

1. Is a job-local NPM-only assembly acceptable as the near-term `export` evidence for *this* job, or must
   the shared exporter (row 3) land before Moskovsky can package further?
2. Should the `npm` parity rule wait for #1954/#1956 readback, or is a controlled round-trip on one job an
   acceptable interim (issue #1969 explicitly prefers waiting)?

## Agent trace

- Sessions: 1 (kanban worker t_d180b473, dt-worker-deepseek)
- Written by: deepseek-v4-pro (Hermes kanban worker)
- Subagents: none
- Skills: none loaded (research-only card)
- Commands: `git show 5f5cf971:<file>` (STATE.md, TASK.md, assemble_site_npm.py, --stat, ls-tree),
  `gh pr view 1979`, `gh issue view 1969/1404/1406/1407/1908/1919/1954/1968`, `gh issue list --label roadmap`,
  read `routes/site.md`, `docs/decisions.md`, `docs/architecture/ground-route.events.yaml`
- Hook denials: none
- Retries: none
- Context at handover: branch `docs/research-ground-site-moskovsky-gap-evidence` (worktree `t_d180b473`)
  at main head `a11bb636`
- Duration: ~30 min
- Commits: 1
