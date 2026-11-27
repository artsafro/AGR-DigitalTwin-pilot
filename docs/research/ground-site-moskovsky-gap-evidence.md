# Ground/Site: map Moskovsky draft evidence to the three shared handoffs

Status: pilot research, read-only. Pre-split evidence for #1969. The draft findings below are distinct
from the current state of the shared prerequisites.

## Historical snapshot: Moskovsky draft #1979 at `5f5cf971`

Draft PR #1979 records a **job-local NPM-only** site assembly for `moskovsky-sosh1200`:
Ground v003 + MAF v002 + Flora v002 are baked, renamed to the NPM grammar, joined and exported as
**one** triangulated Ground FBX
(`use_triangles=True`), plus a `assembled.blend` and an **incomplete** NPM ZIP (`--allow-incomplete`,
no OKS → V001 fail). It does **not** prove any of the three shared handoffs: there is no committed
working quad master (row 1), no VPM profile or surface-parity readback (row 2), and no dual-profile
export with a separate working FBX per D366 (row 3). The draft is a job-local instance of route
step 11 (NPM → export), not a shared route.

## Current pilot status

Checked 2026-11-27 against pilot main `2e243d57e902d22dcff43a6cc49171948aa7a170` and GitHub.
The [Ground route map](../architecture/ground-route.events.yaml) still lists three gaps without shared
owners: `pairing` (`quads`), `ground-atlas` (`npm`), `obj-to-export` (`export`). The adjacent merges
advance prerequisites, not the three deliverables.

| # | Gap (shared handoff) | Historical job evidence (#1979 at `5f5cf971`) | Current shared owner / path | Missing verifiable deliverable | Current prerequisites / decision gates | Conclusion |
|---|---|---|---|---|---|---|
| 1 | Flat working quads before relief | No working quad FBX committed. Ground v002 geometry accepted and frozen; v003 added IDs and textures on it (GPZU 2 940 tris, uncut 4 580 tris). The pinned assembly imports OBJ, bakes and joins meshes, and exports triangles; no quad stage. | **No shared owner verified.** [Site route][site] step 3 writes triangulated OBJ; v015 pairs triangles after relief for Vatutino only. Map: `pairing`. | Reusable pre-relief working quad FBX preserving boundary, holes, seams, slot/material IDs and UVs, judged under D312, not the Vatutino D157 threshold. | [#2048][intake] **MERGED**: records source intent (boundary, holes, coverings, markings and nested schedules); does not produce a working quad artifact. [#1919][validator] **OPEN**: named Ground work-FBX topology validation under D312/D366 is a consumer, not a producer. | **NOT PROVEN** — no shared pre-relief quad artifact. |
| 2 | NPM atlas preserving surface and placement against VPM | Job-local Ground tiled maps (`npm_tiled_maps.py`), MAF 512 atlas v008 and Flora diffuse/opacity atlas. NPM only; no VPM profile or surface-parity readback. Ground 11 736 / GroundEl 47 344 / Flora 44 615 = 103 707 triangles is budget evidence, not parity. | **No shared owner verified.** [Site route][site] step 10: the OKS derive alias does not convert Ground; `npm-light` covers MAF only. Map: `ground-atlas`. | Shared Ground atlas derivation with trusted readback proving surface and placement parity against VPM under D293(5), with distinct atlas/UDIM evidence. | [#1956][repair] **MERGED**, resolving [#1954][readback]: bound readback no longer mixes vertices and triangle indices from separate imports. [#1997][diagnostic] **MERGED**: the [controlled synthetic round-trip](ground-npm-atlas-fbx-roundtrip.md) measured zero surface deviation for a UV-only remap and the injected +0.5 m shift for a geometry change. Raw readback distinguishes two tiles from one; the terrain metric reports only UV presence. This is not shared Ground atlas parity and establishes no tolerance or diagonal rule. | **NOT PROVEN** — the real shared derivation and its parity readback are still missing. |
| 3 | Assembled export: both delivery profiles plus separate work FBX | One triangulated combined NPM FBX (`SM_Ground`/`SM_GroundEl`/`SM_GroundElGlass`/`SM_Flora`), Blender source and an incomplete NPM ZIP. No VPM delivery or separate work FBX with quads. | **No shared owner verified.** [Site route][site] step 11 is job/DCC work. Map: `obj-to-export`; the Ground JSON helper exports only the surface. Historical Vatutino source (`5f5cf97146e6398e843c30f1f2ebad4ea0bd9976:jobs/VATUTINO-SITE/assemble_delivery.py`) also triangulates delivery. | Shared combined exporter producing both profile deliveries and a separate work FBX per D366, with readback of roles, coordinates and distinct files. | **Depends on row 2 (NPM → export).** [#1919][validator] **OPEN**: the validator must separately check the named Ground work FBX, not substitute delivery checks. #1908's VPM package UDIM table does not assemble the site. | **NOT PROVEN** — job-local NPM assembly is not shared dual-profile export; the absent draft work FBX was **not measured**. |

Dependency: row 3 (`export`) depends on row 2 (`npm`). NPM → export is explicit; a job-local NPM
assembly does not by itself establish the shared export handoff.

### Historical source and evidence location

- Draft `STATE.md` at `5f5cf971` — "Site NPM package v001 … diagnostic, not passed";
  Fails: V001 (no OKS), V003 skirt, V004 topology, xview, 7 Ground PNG > 3 MiB.
- Pinned assembly source: `5f5cf97146e6398e843c30f1f2ebad4ea0bd9976:jobs/moskovsky-sosh1200/scripts/assemble_site_npm.py`.
  It exports only a
  single NPM FBX with `use_triangles=True`; writes `assembly.json` + `assembled.blend`; no VPM, no work FBX.
- Draft `TASK.md` at `5f5cf971` records acceptance of Ground v002 geometry for the job.
- [Job STATE — Evidence location](../../jobs/moskovsky-sosh1200/STATE.md#evidence-location) records the
  historical scripts seal at `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200-scripts/`. Its
  `SHA256SUMS.txt` covers 12 originals (`original/`, `5f5cf971`) and two relocated variants
  (`relocated/`, `1ae7efb4`). These are historical sources, not live route entrypoints.
- The same STATE section points to the separate 507-file read-only output snapshot at
  `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/`; Ground v003 outputs are under
  `outputs/ground-npm-v003/`. The sealed reports can retain their original workstation paths.

No new mesh readback, DCC run or inspection of the sealed binaries was performed for this refresh.
The draft work FBX was absent, so that sub-criterion was not measured, not a pass or fail.

## How it applies to this repository

- `routes/site.md` steps 3, 9, 10, 11 already document that the shared command surface stops short of all
  three handoffs; PR #1979 does not close that gap.
- `docs/architecture/ground-route.events.yaml` already names the three gaps (`pairing`, `ground-atlas`,
  `obj-to-export`); the map is truthful and needs no edit from this evidence.
- The two pinned assembly sources are job-local examples of triangulated delivery, not a shared exporter.
- `docs/decisions.md` D366 (work FBX with quads for every package type) has no shared owner yet; the
  Moskovsky assembly ships no work FBX.

## Proposed next tasks (not adopted here)

1. **Split #1969 `quads`: shared pre-relief working-master stage** — Add a reusable route stage that emits
   a quad working master (boundary, holes, seams, slot/material IDs, UV evidence) before relief, judged
   under D312. Scope: a command + verifier for the master, with a Ground test object. Value/effort: **M**.
   `Advances #1969`.

2. **Split #1969 `npm`: shared Ground atlas derivation + parity readback** — Reuse existing atlas cores to
   derive a Ground NPM atlas from a VPM master preserving surface/placement (D293(5)); use the repaired
   readback for the real derivation. The synthetic measurement does not establish an acceptance tolerance.
   Value/effort: **M**. `Advances #1969`.

3. **Split #1969 `export` (depends on `npm`): combined dual-profile exporter + work FBX** — A shared
   combined-site exporter producing both NPM and VPM deliveries and a separate working FBX per D366, proven
   by readback (roles, coordinates, distinct files). Scope: export + readback + #1919 validator wiring.
   Value/effort: **L**. `Advances #1969`.

## Open questions for the user

1. Is a job-local NPM-only assembly acceptable as the near-term `export` evidence for *this* job, or must
   the shared exporter (row 3) land before Moskovsky can package further?
2. The draft asked whether a controlled round-trip could serve as interim evidence while waiting for the
   readback repair. The repair and synthetic diagnostic have landed; the shared parity proof is still open.

## Agent trace (original research)

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

[site]: ../../routes/site.md
[intake]: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/2048
[validator]: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1919
[repair]: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/1956
[readback]: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1954
[diagnostic]: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/1997
