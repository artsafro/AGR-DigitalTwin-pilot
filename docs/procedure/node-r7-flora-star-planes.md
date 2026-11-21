# R7. Flora star planes

**Default level:** `standard` [D273]. Follow the [check-level policy](TASK_TO_MODEL.md#check-levels)
and [common contract](NODE_RECIPES.md#common-contract): **deviate if you state why in one line**.

## Steps

1. Generate the species list from the authoritative planting sheet and assert the totals against it. [Source: #1146, R7 step 1](../research/agent-step-waste-1273.md#r7-flora-star-planes-standard).
2. Match maps to exact species, measure colour and crop to the plant; unresolved identity stays a question, not a guessed match. [Source: VATUTINO lessons](../../jobs/VATUTINO-SITE/LESSONS.md).
3. Bleed colour into transparent pixels and inspect the edge-on plane for fringe/alpha defects. [Source: D246, R7 step 3](../research/agent-step-waste-1273.md#r7-flora-star-planes-standard).
4. Measure texel in the final atlas and ask before upscaling; run the applicable Flora cell checks on the exported-file readback. [Source: VATUTINO / #1146, R7 step 4](../research/agent-step-waste-1273.md#r7-flora-star-planes-standard).
5. Present the species sheet and placement under the image/opened-scene policy [D273], keeping missing visual acceptance explicit. [Source: #1178 visual gate, R7 done](../research/agent-step-waste-1273.md#r7-flora-star-planes-standard).

## Definition of done

Species totals and map identities match the source; transparent edges, final-atlas texel
and exported-file checks are measured. Artem accepts the species sheet and placement.
A machine check or successful export is not his approval. Standard committed-job-script
review and one PR per job apply [D273]; package certification remains separate.
