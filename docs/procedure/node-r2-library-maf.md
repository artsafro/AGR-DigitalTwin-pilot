# R2. Library MAF

**Default level:** `standard` [D273]. Follow the [check-level policy](TASK_TO_MODEL.md#check-levels)
and [common contract](NODE_RECIPES.md#common-contract): **deviate if you state why in one line**.

## Steps

1. Resolve the drawing/PDF page, photo and existing library entry for the item; record which source governs each feature. [Source: Verona #790/#1046, Staropetrovsky and bench, R2 step 1](../research/agent-step-waste-1273.md#r2-library-maf-standard).
2. Block out at real size; use geometry only as detailed as the reference requires, with source-backed joints. [Source: bench and gates, R2 step 2](../research/agent-step-waste-1273.md#r2-library-maf-standard).
3. Assign colour zones as material IDs from the library baseline; record explicit project overrides instead of inheriting another job's palette. [Source: #889 and VATUTINO](../../jobs/VATUTINO-SITE/LESSONS.md).
4. Check smoothing and normals in the viewport before exporting; fix the visible defect, not an invented detail. [Source: Butovskaya smoothing groups, R2 step 4](../research/agent-step-waste-1273.md#r2-library-maf-standard).
5. Read the exported file back, run applicable cell validators including UCX/budgets, write the library entry, and present one side-by-side per item plus overview only when Artem is absent; otherwise open the scene [D273]. [Source: Staropetrovsky, MAF overview v003, R2 step 5 and done](../research/agent-step-waste-1273.md#r2-library-maf-standard).

## Definition of done

Real-size dimensions and material zones match the source; smoothing/normals are checked,
exported-file readback and applicable UCX/budgets pass, and the library entry is written.
Artem accepts the sheet or opened scene. Committed job scripts get one dt-reviewer round,
one PR per job at the end [D273]; acceptance of the picture is not code review or a
full delivery certificate.
