# Default node recipes R1–R7

Use the matching recipe before changing a node. These are default procedures adopted
under [D273] from [#1273 section 5](../research/agent-step-waste-1273.md#5-draft-node-recipes),
not new regulation or delivery certificates. The historical report remains the audit source.

| Node | Default level | Procedure |
|---|---|---|
| R1 Colouring / finish swap | `fast` | [Colouring](node-r1-colouring.md) |
| R2 Library MAF | `standard` | [Library MAF](node-r2-library-maf.md) |
| R3 Fence / railing / gates | `standard`; `fast` for a resize | [Fence / railing / gates](node-r3-fence-railing-gates.md) |
| R4 Window / glazing | `standard` | [Window / glazing](node-r4-window-glazing.md) |
| R5 Ground / paving / lawn / markup | `standard` | [Ground](node-r5-ground.md) |
| R6 OKS body / facade | `standard`; `full` for delivery certification | [OKS body / facade](node-r6-oks-body-facade.md) |
| R7 Flora star planes | `standard` | [Flora star planes](node-r7-flora-star-planes.md) |

## Common contract

- At intake select the highest applicable [check level](TASK_TO_MODEL.md#check-levels),
  including `full` for shared tooling or a delivery claiming `passed=true`. Artem may
  override; the agent may escalate with a reason, never downgrade alone [D273].
- **deviate if you state why in one line** in the job report before continuing.
  This selects a different implementation, not a waiver of source authority, permissions,
  invariants or [fixed gates](TASK_TO_MODEL.md#gates-same-for-every-path).
  When the gate route changes, also keep the structured [deviation log](TASK_TO_MODEL.md#free-path-and-deviation-log).
- Read the sources named by the current job; historical job references explain a step,
  not authorization to reuse that job's dimensions, palette or exceptions. Individual
  preferences stay in its TASK/LESSONS, not in these defaults.
- For presentation follow [visual evidence](TASK_TO_MODEL.md#check-levels): open the scene
  in Artem's DCC version and give its absolute path when he is online. Render only for
  board cards without him: `fast` 1 image, `standard` 1 per item + 1 overview, extra angles
  only for a defect he named [D273]. These are limits, not a render quota.
- `fast` retains one machine readback (IDs/UV/count, 1–2 calls); `standard` adds exported-file
  cell validators, one dt-reviewer round on committed job scripts and one PR per job,
  not per node [D273]. Technical checks, human acceptance and publication stay separate.
- A node's done criteria do not certify a package. Full delivery still needs every
  applicable gate; incomplete, failed or unmeasured checks are not passes.

Canopy waits for the first canopy job [D273]; no canopy recipe is supplied.
