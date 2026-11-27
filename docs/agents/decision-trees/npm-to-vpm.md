# Decision tree: `npm-to-vpm`

Generated from [`decision-trees.json`](../decision-trees.json) by `python tools/architecture/decision_trees.py --render` (#2039); do not edit by hand.
Trail: `docs/scenarios/npm-to-vpm.md`. Stages: `skeletons.json` cell `npm-to-vpm`. AGENT = the agent decides by the quoted rule; ARTEM = Artem decides on a picture sheet; gap = no shared step - manual.

```mermaid
flowchart TD
  N0["passport<br/>Is there a job passport?"]
  class N0 stage
  N1["intake<br/>Are sources, scope, budget and acceptance clear?"]
  class N1 stage
  N2["check-level<br/>Which check level: fast, standard or full?"]
  class N2 stage
  N3["dcc<br/>Blender or Max for this step?"]
  class N3 stage
  N4["auto-open<br/>Open each finished stage for acceptance automatically?"]
  class N4 stage
  N5["npm-ids<br/>Where do the material IDs come from?"]
  class N5 stage
  N6["npm-udim-fit<br/>Does every ID fit one UDIM at 512-1706 px/m?"]
  class N6 stage
  N7["npm-to-vpm<br/>Which conversion mode?"]
  class N7 stage
  N8["readback<br/>Does the exported file read back clean?"]
  class N8 stage
  N9["checker<br/>Run the checker on this conversion?"]
  class N9 stage
  N10["package-vpm<br/>Is the VPM ZIP allowed now?"]
  class N10 stage
  N11["validate<br/>Is a validator result a pass?"]
  class N11 stage
  N0 -->|"no jobs/<ID>/passport.json"| N0B0("AGENT (D397)")
  class N0B0 agent
  N0B0 --> N1
  N1 -->|"open questions remain"| N1B0("AGENT (D186)")
  class N1B0 agent
  N1B0 --> N2
  N1 -->|"sources disagree (conflicts.md item open)"| N1B1("ARTEM (fact)")
  class N1B1 artem
  N1B1 -.-> STOP
  N2 -->|"set at intake"| N2B0("AGENT (D273)")
  class N2B0 agent
  N2B0 --> N3
  N3 -->|"any step"| N3B0("AGENT (D270)")
  class N3B0 agent
  N3B0 --> N4
  N3 -->|"Max is held by Artem"| N3B1("AGENT (D255)")
  class N3B1 agent
  N3B1 --> N4
  N4 -->|"first time in the task"| N4B0("ARTEM (D270)")
  class N4B0 artem
  N4B0 --> N5
  N5 -->|"npm_table.json exists"| N5B0("AGENT (fact)")
  class N5B0 agent
  N5B0 --> N6
  N5 -->|"no table"| N5B1("AGENT (fact)")
  class N5B1 agent
  N5B1 --> N6
  N5 -->|"unresolved, mixed or straddling faces"| N5B2("ARTEM (fact)")
  class N5B2 artem
  N5B2 -.-> STOP
  N5 -->|"glass or window look"| N5B3("AGENT (fact)")
  class N5B3 agent
  N5B3 --> N6
  N6 -->|"fits"| N6B0("AGENT (fact)")
  class N6B0 agent
  N6B0 --> N7
  N6 -->|"does not fit"| N6B1("ARTEM (fact)")
  class N6B1 artem
  N6B1 -.-> STOP
  N7 -->|"table / no table"| N7B0("AGENT (fact)")
  class N7B0 agent
  N7B0 --> N8
  N7 -->|"a seam policy was answered"| N7B1("AGENT (fact)")
  class N7B1 agent
  N7B1 --> N8
  N7 -->|"job G22: deep overlaps"| N7B2("AGENT (D374)")
  class N7B2 agent
  N7B2 --> N8
  N8 -->|"export written (exit 0)"| N8B0("AGENT (fact)")
  class N8B0 agent
  N8B0 --> N9
  N8 -->|"xView overlaps"| N8B1("AGENT (D152)")
  class N8B1 agent
  N8B1 --> N9
  N8 -->|"an inset touches the body plane"| N8B2("AGENT (fact)")
  class N8B2 agent
  N8B2 --> N9
  N9 -->|"conversion plan blocked"| N9B0("AGENT (fact)")
  class N9B0 agent
  N9B0 -.-> STOP
  N9 -->|"valid conversion"| N9B1("ARTEM (D365)")
  class N9B1 artem
  N9B1 --> N10
  N10 -->|"no export_meta of the new FBX and its readback"| N10B0("AGENT (fact)")
  class N10B0 agent
  N10B0 -.-> STOP
  N10 -->|"every package"| N10B1("AGENT (D366, D198)")
  class N10B1 agent
  N10B1 --> N11
  N11 -->|"unsupported, missing, review, not_run or partial"| N11B0("AGENT (fact)")
  class N11B0 agent
  N11B0 --> DONE
  N11 -->|"any mandatory check or manual gate open"| N11B1("AGENT (fact)")
  class N11B1 agent
  N11B1 --> DONE
  STOP(["stop: wait for the answer"])
  DONE(["done"])
  classDef agent fill:#d8f0d8,stroke:#2e7d32
  classDef artem fill:#ffe0b2,stroke:#e65100
  classDef gap fill:#eeeeee,stroke:#616161,stroke-dasharray:4
  classDef stage fill:#e3f2fd,stroke:#1565c0
```

| # | Stage | Question | Branch | Decider | Rule | Next |
|---|---|---|---|---|---|---|
| 1 | `passport` (entry) | Is there a job passport? | no jobs/<ID>/passport.json -> write the passport before any stage | AGENT | [D397]: «`jobs/<ID>/passport.json` (K1) is mandatory for every task» | intake |
| 2 | `intake` (entry) | Are sources, scope, budget and acceptance clear? | open questions remain -> ask ONE batch of <= 5 questions with recommendations | AGENT | [D186]: «ONE batch of <= 5 questions with recommendations» | check-level |
|  |  |  | sources disagree (conflicts.md item open) -> ask, never pick a side | ARTEM (sheet: both sources side by side with the place of the conflict) | `AGENTS.md`: «Where sources disagree (`docs/domain/conflicts.md`), ask the user; never pick a side silently.» | stop |
| 3 | `check-level` (entry) | Which check level: fast, standard or full? | set at intake -> agent sets it; may raise it with a reason, never lower it alone | AGENT | [D273]: «orchestrator/agent sets at intake, Artem overrides with one word» | dcc |
| 4 | `dcc` (entry) | Blender or Max for this step? | any step -> choose per step and state a one-line reason | AGENT | [D270]: «The agent chooses DCC per step from the known toolset/context and states a one-line reason» | auto-open |
|  |  |  | Max is held by Artem -> use an agent-owned Blender on a hashed copy | AGENT | [D255]: «Whenever 3ds Max is held by Artem, any modelling or check step that would use Max may run in an agent-owned Blender» | auto-open |
| 5 | `auto-open` (entry) | Open each finished stage for acceptance automatically? | first time in the task -> ask once; yes = open the new version + path, no = path only | ARTEM (sheet: one-line question in the intake batch) | [D270]: «Ask once per task whether to auto-open each completed stage» | npm-ids |
| 6 | `npm-ids` | Where do the material IDs come from? | npm_table.json exists -> validate it, table mode | AGENT | `docs/scenarios/npm-to-vpm.md`: «With table: validate it, use `npm.to_vpm` table mode» | npm-udim-fit |
|  |  |  | no table -> recover provisional IDs from atlas cells (not library approval) | AGENT | `docs/agents/SKELETONS-stages.md`: «IDs from atlas cells are provisional layout labels, **not** library-material approval» | npm-udim-fit |
|  |  |  | unresolved, mixed or straddling faces -> list with indices, ID0, conversion blocked | ARTEM (sheet: numbered atlas/model sheet of the unresolved faces) | `docs/agents/SKELETONS-stages.md`: «Unresolved/mixed/straddling faces are listed with source indices and remain ID0; they block conversion.» | stop |
|  |  |  | glass or window look -> never infer from colour | AGENT | `docs/scenarios/npm-to-vpm.md`: «Never infer glass/window semantics from colour» | npm-udim-fit |
| 7 | `npm-udim-fit` | Does every ID fit one UDIM at 512-1706 px/m? | fits -> continue to conversion | AGENT | `docs/agents/SKELETONS-stages.md`: «world metres, 4096 tile, 512-1706 px/m» | npm-to-vpm |
|  |  |  | does not fit -> stop before writes; one grouped question | ARTEM (sheet: per-ID fit table + options: seam cuts / extra tiles / allowed density) | `docs/agents/SKELETONS-stages.md`: «ask one grouped question with seam cuts / extra tiles / allowed density / other» | stop |
| 8 | `npm-to-vpm` | Which conversion mode? | table / no table -> table mode / regions mode | AGENT | `docs/agents/SKELETONS-stages.md`: «`regions` without table, `table` with `npm_table.json`» | readback |
|  |  |  | a seam policy was answered -> still no deleting or cropping unassigned faces | AGENT | `docs/scenarios/npm-to-vpm.md`: «An answered seam policy is not authority to ignore unassigned faces, crop mixed materials or delete faces.» | readback |
|  |  |  | job G22: deep overlaps -> keep the exterior finish, trim the neighbour up to 275 mm on a copy | AGENT | [D374]: «preserve the confirmed exterior facade finish» (job-local: `jobs/G22`) | readback |
| 9 | `readback` | Does the exported file read back clean? | export written (exit 0) -> read back topology, UV, materials, transforms | AGENT | `AGENTS.md`: «A successful import or exit code 0 is not a finished model» | checker |
|  |  |  | xView overlaps -> must be 0 at 2 mm / 5 mm | AGENT | [D152]: «Overlapping Vertices at 0.002 m = 0 and Overlapping Faces at 0.005 m = 0» | checker |
|  |  |  | an inset touches the body plane -> offset/embed, never weld | AGENT | `docs/agents/SKELETONS-stages.md`: «never by welding» | checker |
| 10 | `checker` | Run the checker on this conversion? | conversion plan blocked -> no checker and no package | AGENT | `docs/agents/SKELETONS-stages.md`: «no checker/package on a blocked conversion plan» | stop |
|  |  |  | valid conversion -> agr checker; fix findings only when Artem asks | ARTEM (sheet: checker summary: codes, counts, recommended fixes) | [D365]: «we fix SINTEZ findings ONLY when Artem asks, never automatically» | package-vpm |
| 11 | `package-vpm` | Is the VPM ZIP allowed now? | no export_meta of the new FBX and its readback -> stop before the ZIP | AGENT | `docs/agents/SKELETONS-stages.md`: «STOP до ZIP без `export_meta` нового FBX и его readback» | stop |
|  |  |  | every package -> a quad work FBX next to the ZIP | AGENT | [D366, D198]: «Work FBX with quads is made for EVERY package type» | validate |
| 12 | `validate` | Is a validator result a pass? | unsupported, missing, review, not_run or partial -> not a pass; report it | AGENT | `routes/npm-oks.md`: «Unsupported, missing, review, not_run and partial results are not passes» | done |
|  |  |  | any mandatory check or manual gate open -> passed=true forbidden | AGENT | `AGENTS.md`: «`passed=true` is forbidden while any mandatory check or manual gate is open.» | done |
