# R3. Fence / railing / gates

**Default level:** `standard`; `fast` for a resize of an accepted model [D273]. Select by the
[check-level policy](TASK_TO_MODEL.md#check-levels), then follow the
[common contract](NODE_RECIPES.md#common-contract): **deviate if you state why in one line**.

## Steps

1. Record dimensions from the current drawing or Artem's explicit numbers, including profiles and rail heights; historical member sizes are not defaults. [Source: retaining walls and gates resize, R3 step 1](../research/agent-step-waste-1273.md#r3-fence--railing--gates-standard-fast-for-a-resize).
2. Build straight members and simple joints first; add a complex node only where the source shows it. [Source: gates, R3 step 2](../research/agent-step-waste-1273.md#r3-fence--railing--gates-standard-fast-for-a-resize).
3. Repeat members by the specified step along the spline/path; read back count, spacing and changed dimensions. [Source: vertical posts and Object009 handrail, R3 step 3](../research/agent-step-waste-1273.md#r3-fence--railing--gates-standard-fast-for-a-resize).
4. For a new node validate the exported file for the cell; present changed items under the current image limits, or open the scene when Artem is online [D273]. The historical per-side image wording does not authorize extra angles. [Source: gates / retaining walls, R3 step 4 and done](../research/agent-step-waste-1273.md#r3-fence--railing--gates-standard-fast-for-a-resize).

## Shared headless builder

```bash
uv run agr railing parapet.json --type glass_posts --profile vpm --out new-railing.blend
```

Supply a metre JSON document with `points` (level XYZ polyline in the model frame),
`closed` (boolean, no repeated closing point), optional `corners` (zero-based hard
point indices for sampled curves), and `dimensions`. Type names: `glass_posts`,
`posts_handrail`, `posts_handrail_infill`. The latter uses a solid infill plate,
not an inferred perforation pattern. Required dimensions (metres):

- All: `height`, `max_step`, `post_width` (along path), `post_depth` (across path).
  Optional `post_bottom` defaults to 0; negative embeds the post below the input Z.
- Glass only: optional `post_top` below or at `height`.
- With top rail: `rail_width`, `rail_height`. Post top meets the rail underside.
- With glass/infill: `panel_bottom`, `panel_top`, `panel_depth`, `clearance`.
  Panels are set back from post axes by the post half-diagonal plus clearance.

The input path is the measured placement axis, not an arbitrary parapet edge;
check signed offset, fastening datum and exterior side in the source section.
Every end and hard corner gets a post. Absent explicit corner indices, bends are
considered hard corners. Between anchors, `ceil(run_length / max_step)` bays are
spaced equally by developed polyline length. Unlike Vertex CL normalization,
this does not move the input points or require CAD vertex positions to coincide
with post axes. Add samples as needed on curved geometry and mark its true corners.
Non-level/ambiguous paths, reversals, thin segments and unusable dimensions fail.

The new native copy is an inset candidate, not a delivery; stdout and scene
property `agr_railing` report the source hash, post centres, spacing and triangle
count. The role IDs (1 post, 2 top rail, 3 glass, 4 infill) are diagnostic slots;
assign approved finishes and production UV before the normal export checks.
The original body is untouched. Keep geometry for both profiles by default;
only for an over-budget NPM per the [budget ladder](../scenarios/vpm-to-npm.md)
select `--profile npm --representation opacity`. It emits one-sided, right-facing
planes with separate packed colour and opacity maps (ID 5); reverse a wrong-facing
path, and check reachable views before accepting a replacement. These per-bay
work maps are not a packaged NPM atlas. Save to a new local `.blend` on a
hardlink-capable filesystem; publication does not replace an existing file.

## Definition of done

Dimensions, count and step of posts match the source, required readback/validators for
the selected level are recorded, and Artem accepts the result. A resize retains the
fast machine readback; a new node uses standard exported-file validation and job-script
review [D273]. No inherited dimensions or blanket delivery pass.
