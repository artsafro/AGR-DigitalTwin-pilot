# Decision tree: `sintez-fix`

Generated from [`decision-trees.json`](../decision-trees.json) by `python tools/architecture/decision_trees.py --render` (#2039); do not edit by hand.
Trail: `docs/research/sintez-fix-1744.md`. Stages: `skeletons.json` cell `sintez-fix`. AGENT = the agent decides by the quoted rule; ARTEM = Artem decides on a picture sheet; gap = no shared step - manual.

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
  N5["request<br/>Did Artem ask for this SINTEZ fix?"]
  class N5 stage
  N6["checker<br/>Is the baseline pinned?"]
  class N6 stage
  N7["sintez-classify<br/>Which owner handles each finding?"]
  class N7 stage
  N8["sintez-recipe (gap: no shared step - manual)<br/>How is the finding fixed on the copy?"]
  class N8 gap
  N9["sintez-uv-drift<br/>Did the fix move UV or world registration?"]
  class N9 stage
  N10["sintez-recheck<br/>Did the fix clear the targeted findings without new ones?"]
  class N10 stage
  N11["sintez-sheet (gap: no shared step - manual)<br/>Accept the repaired copy?"]
  class N11 gap
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
  N5 -->|"no request_ref or no agreed fix list"| N5B0("ARTEM (D365)")
  class N5B0 artem
  N5B0 -.-> STOP
  N6 -->|"baseline run"| N6B0("AGENT (fact)")
  class N6B0 agent
  N6B0 --> N7
  N7 -->|"known code and message"| N7B0("AGENT (fact)")
  class N7B0 agent
  N7B0 --> N8
  N7 -->|"unknown, partial or ambiguous"| N7B1("ARTEM (fact)")
  class N7B1 artem
  N7B1 -.-> STOP
  N8 -->|"agreed fix list"| N8B0("AGENT (fact)")
  class N8B0 agent
  N8B0 --> N9
  N9 -->|"any movement"| N9B0("AGENT (fact)")
  class N9B0 agent
  N9B0 --> N10
  N9 -->|"exceptions"| N9B1("ARTEM (fact)")
  class N9B1 artem
  N9B1 -.-> STOP
  N10 -->|"recheck done"| N10B0("AGENT (fact)")
  class N10B0 agent
  N10B0 --> N11
  N11 -->|"sheet assembled"| N11B0("ARTEM (fact)")
  class N11B0 artem
  N11B0 -.-> STOP
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
| 5 | `auto-open` (entry) | Open each finished stage for acceptance automatically? | first time in the task -> ask once; yes = open the new version + path, no = path only | ARTEM (sheet: one-line question in the intake batch) | [D270]: «Ask once per task whether to auto-open each completed stage» | request |
| 6 | `request` (pre) | Did Artem ask for this SINTEZ fix? | no request_ref or no agreed fix list -> do not start the cell | ARTEM (sheet: checker summary with the proposed fix list) | [D365] `docs/agents/SKELETONS-stages.md`: «Без ссылки `request_ref` на явное поручение и согласованного перечня правок не запускать ячейку» | stop |
| 7 | `checker` | Is the baseline pinned? | baseline run -> pin source ZIP, copy hashes and checker version | AGENT | `docs/agents/SKELETONS-stages.md`: «pin source ZIP, copy hashes and checker version» | sintez-classify |
| 8 | `sintez-classify` | Which owner handles each finding? | known code and message -> route by profile + requirement + message, not exit code | AGENT | `docs/agents/SKELETONS-stages.md`: «route by profile + requirement + underlying message, not by exit code» | sintez-recipe |
|  |  |  | unknown, partial or ambiguous -> stop the targeted repair | ARTEM (sheet: the rows with code, message and counts) | `docs/agents/SKELETONS-stages.md`: «Unknown/partial/ambiguous rows stop the targeted repair» | stop |
| 9 | `sintez-recipe` gap: no shared step - manual | How is the finding fixed on the copy? | agreed fix list -> one job hook or the owner (vpm-uv, master-qa, package); no generic auto-fix | AGENT | `docs/agents/SKELETONS-stages.md`: «No unattended generic fix.» | sintez-uv-drift |
| 10 | `sintez-uv-drift` | Did the fix move UV or world registration? | any movement -> report it, never round it away | AGENT | `docs/agents/SKELETONS-stages.md`: «Do not round away movement» | sintez-recheck |
|  |  |  | exceptions -> list them and stop for review | ARTEM (sheet: drift receipt with the exceptions) | `docs/agents/SKELETONS-stages.md`: «List exceptions and stop for explicit review» | stop |
| 11 | `sintez-recheck` | Did the fix clear the targeted findings without new ones? | recheck done -> compare targeted findings, coverage, new regressions | AGENT | `docs/agents/SKELETONS-stages.md`: «compare targeted findings, coverage and new regressions» | sintez-sheet |
| 12 | `sintez-sheet` gap: no shared step - manual | Accept the repaired copy? | sheet assembled -> Artem decides; no delivery or publication by the agent | ARTEM (sheet: before/after: hashes, codes, counts, UV/world movement, changed maps) | `docs/agents/SKELETONS-stages.md`: «No delivery or publication.» | stop |
