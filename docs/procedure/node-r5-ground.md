# R5. Ground / paving / lawn / markup

**Default level:** `standard` [D273]. Follow the [check-level policy](TASK_TO_MODEL.md#check-levels)
and [common contract](NODE_RECIPES.md#common-contract): **deviate if you state why in one line**.

## Steps

1. Read contours and covers from the authoritative DWG/PZU and record the cover/colour mapping from its legend or hatch background fill, resolving ambiguity at intake. [Source: Silikatny DWG, R5 step 1](../research/agent-step-waste-1273.md#r5-ground--paving--lawn--markup-standard).
2. Make covers meet without slivers or unwanted triangles at joints; place markup on cover joints only where the source shows it. [Source: Kasatkino, Ground v015 #371 and Silikatny, R5 step 2](../research/agent-step-waste-1273.md#r5-ground--paving--lawn--markup-standard).
3. Assign material ID per cover/texture and run the required xView/overlap postcondition after geometry changes and on the exported mesh. [Source: Ground v015 #371, R5 step 3](../research/agent-step-waste-1273.md#r5-ground--paving--lawn--markup-standard).
4. Read the export back, record Ground cell validator results and compare covers/joints to the source for Artem's acceptance [D273]. [Source: Ground v015 #371, R5 done](../research/agent-step-waste-1273.md#r5-ground--paving--lawn--markup-standard).

## Definition of done

Covers, material mapping and joints match the source; exported-file readback and
applicable Ground validators pass, with deviations and unmeasured checks explicit;
Artem accepts the result. A particular job's projection/handoff arrangement is not a
shared production step. Standard job-script review and one job PR apply [D273]; full
delivery certification still uses all fixed gates.
