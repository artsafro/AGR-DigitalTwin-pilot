# Dry run of routes/revit-intake.md on KPP1 (#1362) — read-only, from existing dumps

**Mode: documented dry run from existing evidence, not a live Revit session.** Nothing was opened, saved,
exported or modified. Date 2026-11-14, card t_9d1089b9.

## Step 1 — intake

| Check | Command | Result |
|---|---|---|
| Revit process | `tasklist` | `Revit.exe` running (pid 785380) |
| revit-http-2025 | `python C:/Users/artsafro/hermes_kanban/scripts/revit_exec.py --ping` | exit 2, `status: unreachable` (WinError 10061, port 7891 not listening); lock file absent |
| revit-bridge | `callBridge("revit_status")` (read-only class) | `revit_unavailable`: "RevitBridge session not found" |

Neither add-in answered, so the route's offline branch applies: the inventory below is read from the
dumps of the earlier KPP1 runs (local, gitignored, outside this repo):
`C:/Users/artsafro/AGR-DigitalTwin/.claude/worktrees/laughing-hawking-e62961/jobs/KPP1/outputs/`
(`census-v001/inspect_revit.json`, `census-v001/elements.json`, `source-v001/*.export.json`,
`revit-twin-v005/twin-data.json`). Their age is not a fresh measurement.

Hashes taken now (read-only `sha256sum`; reading does not change the files):

| File | Size, B | mtime | SHA-256 |
|---|---:|---|---|
| source `C:/Users/artsafro/DigitalTwinProject/Revit/26_КПП1_АР_МЭП_RVT22.rvt` | 109498368 | 2026-10-06 14:08 | `f0a46b8a64dcde6474174d8ad72c61a68bb2d6f1b50415df2e9661744de9f347` |
| copy `C:/Users/artsafro/Documents/26_КПП1_АР_МЭП_RVT25_artsafro.rvt` | 111906816 | 2026-10-21 00:21 | `b5b881752b35e0f5ce6360408d94f7a2cff039ab376d61278f53fdd6b2cc6dbd` |

## Steps 2–3 — what the checklist found in the dumps

| # | Checklist line | Dump value | Caught by the route |
|---|---|---|---|
| 1 | Source registry | `jobs/KPP1/sources.json` lists only the three АС.03 DWGs | **Gap**: neither RVT is registered; #1330 recorded "RVT hash unavailable". Hashes above are the first record; adding them to `sources.json` is the job's next intake step (not done here, out of this card's scope) |
| 2 | Copy freshness | copy mtime 2026-10-21, later than the 2026-10-08 read-only checks in `STATE.md` | **Stale-receipt risk**: older dumps may not describe the current copy; re-inventory before reuse |
| 3 | Document identity | census: `26_КПП1_АР_МЭП_RVT25_artsafro_отсоединено`, `isWorkshared: true`; twin: `26_КПП1_АР_МЭП_RVT25_artsafro`, path of the copy | **Two identities** (detached session vs file) across dumps; the route requires title/path + `modified` per session |
| 4 | Units | `units: "Миллиметры"`, but `inspect_revit.json` level elevations are feet (−13.7795 → −4.200 m); `twin-data.json` is metres | **Unit trap** made explicit (checklist 2) |
| 5 | Levels | `отм. -4,200`, `0,000`, `+3,900`, `+7,700`, `+8,650` | **Level −4.200 is absent** from `STATE.md` ("Levels 0.000 / +3.900 / +7.700 / +8.650") and from `object.json` `levels`; its use is a question for Artem. +7.700/+8.650 are not floors ([D045]) — already recorded |
| 6 | Coordinates | PBP [0,0,0], Survey Point [0,0,−171.05], shared elevation 171.05, angle 0° | Matches `object.json` (0.000 = 171.050). `height_system` stays `unknown` (#1330, [D279]) |
| 7 | Links / worksets | `links: []`; **no worksets field** in any dump although the model is workshared | **Gap**: worksets never inventoried; the route requires `revit_get_worksets` (or an explicit empty list) |
| 8 | Categories vs export groups | census 22 categories; `export_revit_groups.mjs` groups 18; not exported: Ceilings 54, Mass 1, Furniture 220, PlumbingFixtures 49 | **No drop list with reasons** was recorded; the route requires one (interior/non-facade per OBR22 lesson) |
| 9 | Export sidecars | `source-v001/*.export.json` keys `fbx, document, types` only; `fbx` path points to another worktree (`vpm-npm-revit-model-fc8a24`) | **Not self-proving**: `savedDocument`, `elementCount`, `bytes` were stdout only; absolute paths are stale after a move, no `SHA256SUMS.txt` on Drive |

Other facts read: 158 families, 1474 types, 465 materials (many with `instanceCount: 0`; names may be bare
RAL codes such as «1021»), 2 views; roofs `Покрытие_ТН-КРОВЛЯ Классик (бет. осн)` on +7.700 (60.36 m³,
288.44 m²) and the parapet type on +8.650. The census producer of `inspect_revit.json` is not committed; its
fields match RevitBridge `agr_census`, which the risk table does not class as read-only — hence candidate
command 1 over the read-only `revit-http-2025` tools.

## Steps 4–5

Not run: no model is built by this card. Existing KPP1 builds (v005 accepted, windowgen #1338 measurement)
are unchanged. Open Revit questions for Artem: use of level −4.200; whether the RVT entries above may be
added to `sources.json` as source/working copy.
