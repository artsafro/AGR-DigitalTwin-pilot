# Flora texture route (#190)

Scope: approved per-species 2048 diffuse + separate binary opacity library assets.
Atlas construction is deferred to #217, after library #216 and scene placement.
Sources: issue #190 (Artem, 2026-10-15, grilling rounds 1–2),
[UV rules](domain/uv-textures.md#npm-textures-app1), [workflow](agents/WORKFLOW.md).
No modelling, VPM shells, or delivery acceptance. Generation uses the authorized
Codex CLI built-in image_generation tool, not a procedural/synthetic substitute.
Pillow/numpy dependencies are declared in `pyproject.toml`.

## 1. Species and generation request

Use a JSON list of objects with `species` and optional `reference` (URL or source
picture identity/path). Retain any reference from the specification; attach its
actual picture to the image model, not just its name. Resolve relative input paths
from the command's working directory. Run from the repository root:

```bash
uv run python -m dt_ai.materials.flora plan \
  --species jobs/flora-textures/species.json \
  --out jobs/flora-textures/generation-plan.json
```

The checked-in plan is already produced; a rerun needs a new filename. This test
list is NOT asserted to be the GROUND-PROJECTION schedule.
Send each `prompt` and supplied reference to the enabled image-generation tool
on a dt-* profile. Request a single complete plant, **2048x2048, front view,
white background, no shadows**. Save the actual output outside the repository.
Record the actual model and generation ID when exposed. Codex's built-in tool
does not expose these: explicitly record that absence and its actual trace session,
never invent IDs or a model name. It has no size control and produced 1254x1254.
Artem explicitly accepted these three sources and authorized technical upscaling
on 2026-10-15 (card comment at 20:44; COORDINATION_RULES 27). This narrow exception
does not claim native 2K detail or approval of the later cut-outs:

```bash
uv run python -m dt_ai.materials.flora upscale \
  --source C:/x/flora-textures/betula-pendula/rejected-non2k-v001.png \
  --out C:/x/flora-textures/betula-pendula/upscale-v001 \
  --authorization 'Artem, card t_4005c4b2, 2026-10-15 20:44: 1254 sources accepted; authorize 2048 LANCZOS'
```

Repeat for the other species using their own paths. This command accepts only RGB
1254 square sources, keeps the source unchanged and emits `source-2048.png` plus
`upscale.json` with hashes, actual sizes, method and authorization. Pass the receipt
as `upscale_record` in incoming.json. `prepare` validates its output hash, binds the
receipt into the candidate ID and displays it on the review sheet. No new image
generation or alternative resampling is needed.

The following examples use `$ARTIFACTS` as an **absolute external directory chosen
by the operator** (not `data/`, not a path inside any checkout). No binaries belong
in the repo, including ignored directories. The implementation checks resolved
binary destinations against this checkout. It does not authorize writes outside
the implementing agent's worktree; this card explicitly authorizes
`C:/x/flora-textures/`. The mandated pytest temporary directory is used for tests only.

## 2. Cut-out and review (not atlas insertion)

Create an external `incoming.json`, keyed by exact species names:

```json
{
  "Betula pendula": {
    "image": "C:/operator-artifacts/generated/betula.png",
    "model": "actual image model name",
    "generation_id": "actual tool result ID",
    "reference_image": "C:/operator-artifacts/references/betula.png",
    "upscale_record": "C:/operator-artifacts/generated/upscale.json"
  }
}
```

Supply every planned species. Omit `reference_image` only when no picture is
available; omit `upscale_record` for native 2048 sources. A supplied URL remains in the plan and review. Download/reference
acquisition is manual, with source permissions checked by the operator.

```bash
uv run python -m dt_ai.materials.flora prepare \
  --plan jobs/flora-textures/generation-plan.json \
  --incoming "$ARTIFACTS/incoming.json" --out "$ARTIFACTS/review-v001"
```

Inputs must be RGB, exactly 2048 square. Each pixel with **all** RGB channels >=245
becomes opacity 0, others 255 (`--threshold` can explicitly change this setting).
White gaps inside foliage are removed too. Diffuse stays RGB, opacity is L; neither
has alpha. RGB PNG color-key transparency (`tRNS`) is removed from the diffuse
copy so serialized output cannot retain hidden transparency; RGB pixels and the
source image remain unchanged. Pure white and entirely non-white inputs are rejected. This simple
white-key method can erase white flowers/pale leaves and retain gray shadows;
review must reject such results, adjust threshold in a new run, or regenerate.
It is not a learned segmentation or botanical correctness check.

`review.html` compares the reference (picture when supplied, otherwise URL or
explicit absence), original 2K diffuse/result, opacity, prompt, and candidate ID.
Inspect edges/holes, halos, missing pale foliage, identity, proportions and shadows.
No atlas is emitted by `prepare`. Candidate PNGs and HTML get SHA-256 hashes.
Open `review.html` locally; all images are local, no network request is made.

## 3. Explicit user gate

Every new texture requires Artem's explicit OK, including the first 10–20 species.
There is no auto-approval command. After Artem reviews the exact sheet and files,
the operator transcribes the decision to an external JSON document:

```json
{
  "approvals": [{
    "candidate_id": "COPY FROM candidates.json",
    "review_sha256": "COPY FROM candidates.json",
    "decision": "approved",
    "reviewed_by": "Artem",
    "reviewed_at": "2026-10-15T12:00:00+03:00",
    "evidence": "Exact user approval quote and conversation/message reference"
  }]
}
```

One record per candidate; an absent, rejected, pending, duplicate, stale or
unattributed decision blocks the whole library batch before any output write.
Changed species/prompt/parameters/reference/diffuse/opacity or sheet invalidate
previous approval. Approval JSON is a human attestation, not a signature or proof
of identity: agents must not manufacture it. Test fixtures are explicitly synthetic.

## 4. Approved per-species library assets (current scope)

Artem's scope change, 2026-10-15 via orchestrator: **no atlas in #190**.
First consolidate the library (#216), then place plants, then build one atlas from
that placed scene (#217, reusing/extending #184). This command does not pack an
atlas, resize maps, assign UVs or consolidate a .max library:

```bash
uv run python -m dt_ai.materials.flora library \
  --review C:/x/flora-textures/review-v001 \
  --approvals C:/x/flora-textures/approvals-v001.json \
  --out C:/x/flora-textures
```

After validating every approval, copy the exact approved map bytes into one
species folder: `betula-pendula/diffuse-v001.png`, `betula-pendula/opacity-v001.png`,
and similarly for `pinus-sylvestris` and `spiraea-japonica`. Both maps remain
2048 square: RGB diffuse and L binary opacity (0 transparent, 255 opaque), without
alpha per [D020]. The separate opacity PNG supplies transparency to the material;
it is not an RGBA diffuse. `library-v001.json` records candidate IDs, paths, hashes
and approvals. Existing species folders may contain original source images; none
are overwritten. All target files are checked before writes; existing destination
files or manifest fail rather than replacing an approved version. For another
publication run use a new external root/version.

The output root is explicitly supplied with `--out` for each command; there is no
`AGR_FLORA_OUT` implicit default. Resolve paths before running. All generated and
review binaries stay outside git, including ignored repository directories.

No atlas command is exposed. An atlas made earlier, before the scope change, is
an external scratch artefact only, not part of this issue's deliverable, PR evidence
or acceptance. No atlas binary or implementation is in the final PR diff.

## Checks and evidence

`tests/test_flora_textures.py` uses synthetic white-background rectangles with a
foliage hole, not generated plants. It covers all 255 cut-out thresholds against
256 gray levels, missing/invalid approvals at each of three positions, changed
review artifacts, repository-output rejection, byte-identical library publication, exact
input dimensions, separate no-alpha maps and binary opacity. Tests write binaries
only to pytest's harness-assigned external temporary directory. A generated probe
also checks all 256 grayscale PNG transparency keys through cut-out and PNG
readback, plus a 2K `prepare` regression with a transparent RGB PNG source.
Verified RED/GREEN and full-suite counts are recorded in the task state below.

See [task state](../jobs/flora-textures/STATE.md) and
[three-species pending review](../jobs/flora-textures/review-pending.md).
