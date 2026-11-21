# R1. Colouring / finish swap

**Default level:** `fast` [D273]. Follow the [check-level policy](TASK_TO_MODEL.md#check-levels)
and [common contract](NODE_RECIPES.md#common-contract): **deviate if you state why in one line**.
A shared tool change or delivery certificate requires `full`, not this small-edit route.

## Steps

1. Read the supplied slide/legend/photo first; record the reference authority and the scope that stays unchanged. [Source: TEC26 colouring O1/O5](../retros/2026-10-22-tec26-colouring-claude.md).
2. Inventory material IDs and map ID → material → colour/texture in one table before assignment. [Source: TEC26 colouring; Silikatny DWG, R1 step 2](../research/agent-step-waste-1273.md#r1-colouring--finish-swap-fast).
3. Apply the finish without unrequested geometry changes; take one machine readback of IDs/UV/count and changed map paths (1–2 calls). [Source: TEC26 / Silikatny, R1 step 3](../research/agent-step-waste-1273.md#r1-colouring--finish-swap-fast).
4. Open the versioned scene and give the absolute path when Artem is online; otherwise show the single result beside its reference under the image policy [D273]. [Source: TEC26 colouring O6/O7](../retros/2026-10-22-tec26-colouring-claude.md).

## Definition of done

The changed IDs, UV and map paths match the mapping; Artem accepts the image or opened
scene. Stop after his acceptance; ask on a second correction of the same point [D273].
No pytest or code review for the fast edit, and no new Gate-1 sheets for colouring an
accepted model. Keep a new preference job-local in LESSONS. This does not waive any
existing mandatory gate or certify a new delivery.
