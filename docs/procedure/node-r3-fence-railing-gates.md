# R3. Fence / railing / gates

**Default level:** `standard`; `fast` for a resize of an accepted model [D273]. Select by the
[check-level policy](TASK_TO_MODEL.md#check-levels), then follow the
[common contract](NODE_RECIPES.md#common-contract): **deviate if you state why in one line**.

## Steps

1. Record dimensions from the current drawing or Artem's explicit numbers, including profiles and rail heights; historical member sizes are not defaults. [Source: retaining walls and gates resize, R3 step 1](../research/agent-step-waste-1273.md#r3-fence--railing--gates-standard-fast-for-a-resize).
2. Build straight members and simple joints first; add a complex node only where the source shows it. [Source: gates, R3 step 2](../research/agent-step-waste-1273.md#r3-fence--railing--gates-standard-fast-for-a-resize).
3. Repeat members by the specified step along the spline/path; read back count, spacing and changed dimensions. [Source: vertical posts and Object009 handrail, R3 step 3](../research/agent-step-waste-1273.md#r3-fence--railing--gates-standard-fast-for-a-resize).
4. For a new node validate the exported file for the cell; present changed items under the current image limits, or open the scene when Artem is online [D273]. The historical per-side image wording does not authorize extra angles. [Source: gates / retaining walls, R3 step 4 and done](../research/agent-step-waste-1273.md#r3-fence--railing--gates-standard-fast-for-a-resize).

## Definition of done

Dimensions, count and step of posts match the source, required readback/validators for
the selected level are recorded, and Artem accepts the result. A resize retains the
fast machine readback; a new node uses standard exported-file validation and job-script
review [D273]. No inherited dimensions or blanket delivery pass.
