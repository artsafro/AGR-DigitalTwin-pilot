# R6. OKS body / facade

**Default level:** `standard`; `full` when the delivery claims `passed=true` [D273].
Follow the [check-level policy](TASK_TO_MODEL.md#check-levels) and
[common contract](NODE_RECIPES.md#common-contract): **deviate if you state why in one line**.
Use the accepted [NPM/OKS route](../../routes/npm-oks.md) when applicable.

## Steps

1. Read slides, legend and album before modelling; record source authority and the scope of the change. [Source: TEC26 O1, 4BK and СРЕDА, R6 step 1](../research/agent-step-waste-1273.md#r6-oks-body--facade-standard-full-when-the-delivery-claims-passedtrue).
2. Build body → openings → decor as separate parts using the confirmed decomposition and the cell route. [Source: tow02, R6 step 2](../research/agent-step-waste-1273.md#r6-oks-body--facade-standard-full-when-the-delivery-claims-passedtrue).
3. Derive seams and panel joints from source openings/layout; keep continuous trims one mesh where the source requires continuity. [Source: 4BK, СРЕDА and tow02, R6 step 3](../research/agent-step-waste-1273.md#r6-oks-body--facade-standard-full-when-the-delivery-claims-passedtrue).
4. Roof inside a parapet: build the roof membrane as its own plate, separate from the parapet, before seal or any T-junction repair; never weld it to the parapet foot. A welded roof/parapet seam carries every facade cut across the roof to the opposite facade. The plate sits `plate_gap_m` above the hole, and its border runs `plate_overlap_m` under the parapet inner faces (mitred). The parapet foot stays open as the hole's loop. Take both values from the current spec, read from the source or etalon: the default is 5 / 20 mm, the pattern allows 2–10 / 10–50 mm [D038, D039]. PSU275's 11 mm is that job's value from before the rule (KPP1 v005 embed lesson), not a default. Measured: PSU275 Main 66 282 → 36 556 quads (seal had grown 29k → 60k faces across the seam); K01 KPP1 engine 2 361 → 1 592 quads. [Source: PSU275 v009 mesh clean-up](../../jobs/PSU275/STATE.md), [K01 KPP1 seam evidence #1339](../../jobs/KPP1/seam-1339/README.md), [pattern roof-inset-plane](../domain/patterns/roof-inset-plane.md).
5. Map materials per ID from the drawings; record project-specific subdivisions in the job, not as global geometry rules. [Source: Garibaldi, R6 step 4](../research/agent-step-waste-1273.md#r6-oks-body--facade-standard-full-when-the-delivery-claims-passedtrue).
6. Read the exported file back, run regulation/cell validators and record each blocker as stage, value and limit rather than chasing a pass. [Source: KPP1 lessons](../../jobs/KPP1/LESSONS.md).

## Definition of done

Parts, openings, joints and materials match the sources; validator results are measured
and remaining blockers are explicit. Artem accepts the opened scene or allowed evidence
set. The roof/parapet seam (step 4) is done when the exported file read back shows all of these:
- the job report gives the Main and membrane quads before and after the split, and the membrane carries only the cuts of its own outline;
- T-junctions 0 at the seam;
- a closed shell: non-manifold 0, `slabs_not_inset` 0, and per slab exactly two open loops, both closed (the hole at the parapet foot and the plate outline at level + gap). The only other open loop is the bottom ring.

Standard node completion does not imply package acceptance. Only `full` delivery
work with all applicable fixed gates complete can claim `passed=true`; failed, review
or not-run results stay visible [D273].
