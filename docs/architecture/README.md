# Route maps: two reading views (#1425)

Start with the short scheme to answer how today's route hands artifacts to the next step.
Open its owners/migration table for rules, module owners, live-bypass counts, exact locations,
reasons for differences, migration issues and completion criteria. Russian labels are for Artem.

| Route | Short scheme (SVG / editable) | Owners and migration |
|---|---|---|
| НПМ / ОКС | [SVG](npm-oks-route-scheme.svg) / [Excalidraw](npm-oks-route-scheme.excalidraw) | [Table](npm-oks-route-owners.md) |
| ВПМ / ОКС | [SVG](vpm-oks-route-scheme.svg) / [Excalidraw](vpm-oks-route-scheme.excalidraw) | [Table](vpm-oks-route-owners.md) |
| Ground | [SVG](ground-route-scheme.svg) / [Excalidraw](ground-route-scheme.excalidraw) | [Table](ground-route-owners.md) |
| МАФ | [SVG](maf-route-scheme.svg) / [Excalidraw](maf-route-scheme.excalidraw) | [Table](maf-route-owners.md) |
| Флора | [SVG](flora-route-scheme.svg) / [Excalidraw](flora-route-scheme.excalidraw) | [Table](flora-route-owners.md) |
| Пакет и сдача | [SVG](package-route-scheme.svg) / [Excalidraw](package-route-scheme.excalidraw) | [Table](package-route-owners.md) |

## Source of truth and regeneration

Existing `*-route.events.yaml` and `*contexts.yaml` remain the only inputs. `scheme` in each events
YAML groups the existing ordered stages into at most seven handoffs; every stage must occur exactly
once and in order. `ru`, `artifact_ru` and `gate_ru` give the working step, passed artifact and acceptance
condition. Conditions are not claims that a real delivery has passed. Detailed event storms and context
interfaces remain available as supplementary views, not the starting canvas. Context arrows now bind
owner nodes, never duplicate lists; exact duplicate locations occur in the Markdown tables only.

```bash
uv run python tools/architecture/route_map.py
uv run python tools/architecture/route_map.py --check
uv run python tools/architecture/duplicate_guard.py
uv run python tools/architecture/regen_after_merge.py --merge origin/main   # merge conflict on maps (#1558)
```

Generated maps are `merge=ours` in `.gitattributes`: never resolve them by hand; merge, then regenerate
(`docs/agents/WORKFLOW.md`, "Merging PRs: generated maps and decision rows").

Both new views carry the same SHA-256 revision of their parsed YAML snapshot. This is the architecture
source revision, **not** a fabricated revision/hash of a customer's input or an execution receipt.
Each scheme separately names the source-revision evidence required by its route. A concrete run must
supply its actual revision/manifest; this documentation does not fill missing provenance.

Counts reuse `duplicate_guard.rows_of` and #1424's statuses. They count unique `(owner, at)` registry
locations across the maps relevant to that owner, not files, pink notes or historical copies. A repeated
map description is not an extra bypass. `historical`, `wrapper` and `own-duty` remain distinct and are
listed in the table. `live-bypass` rows link their migration issue, or explicitly say no card exists.
Run the existing guard to validate those declarations against actual call chains; generation itself
is not a second call-chain checker or a new package-control layer.

The export owner is explicit: Max `export_core.py`; Blender NPM `tools/derive/export_npm.py`, and the
existing job-specific VPM producer. ZIP writing stays in `package_core.py`; package composition and
validation remain the existing checks. No core, DCC protocol, runtime manifest or acceptance policy
is introduced or changed here. Technical QA, visual acceptance and publication stay separate.

PNG renders for Artem are external evidence under `G:/Мой диск/AGR-evidence/1425-route-maps/`
(with `SHA256SUMS.txt`), attached to the card's review handoff; no PNG or LFS pointer is committed.
