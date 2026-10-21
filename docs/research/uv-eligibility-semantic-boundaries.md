# UV eligibility: semantic boundaries

## Summary

- **No:** the two direct finite-polygon eligibility APIs do not classify every polygon alike.
- With valid tile/size and zero padding, a positive dyadic triangle of area `2^-37` is rejected by engine `validate_uv` but accepted by checker `face_issue` and its boolean wrapper.
- Both reject reversed winding, zero area, malformed point lengths and nonfinite coordinates in the frozen controls; scalar points raise rather than return a verdict.
- A 4 px tile-border clearance with 16 px requested padding fails both booleans; checker distinguishes `margin` from `cross_tile` and `mirrored`.
- The engine boolean is used by synthetic development-bundle C003; checker face eligibility helpers have no current production caller found in `src/` or `tools/`.
- Scene V008 findings consume readback channel/mirroring/tile facts, not either face eligibility API; they do not inherit these area cutoffs or margin diagnostics.
- Evidence: one frozen 15-case standard-library run, independent exact areas/clearances, and pinned read-only source/caller inspection; no package/DCC run or real-model defect is asserted.
- Report only: `delivery_passed=false`; no policy, consolidation, adoption, production, test or standards changes.

## Findings (with sources)

### Evidence provenance and scope

Pinned checkout and fetched `origin/main`: `d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c` (the source revision, not the later report commit).
Verified locally with `git rev-parse HEAD`, `git fetch origin`, source reads, targeted
`git grep`/searches and the standalone reproducer below. The GitHub API independently
returned this same d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c and [commit URL](https://github.com/artsafro/AGR-DigitalTwin-pilot/commit/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c).
These are first-party code observations, not external claims about regulatory compliance.
No unrelated web sources are needed to establish this repository's behavior.

Source index (all links pinned to the same revision):

- **E:** [src/dt_ai/geometry/uv.py:17-27](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c/src/dt_ai/geometry/uv.py#L17-L27).
- **Q:** [src/twinqa/uv.py:39-64](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c/src/twinqa/uv.py#L39-L64).
- **B:** [src/dt_ai/validate/bundle.py:101-129](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c/src/dt_ai/validate/bundle.py#L101-L129).
- **C:** [src/dt_ai/cli/main.py:245-255](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c/src/dt_ai/cli/main.py#L245-L255).
- **S:** [src/twinqa/scene.py:429-455](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c/src/twinqa/scene.py#L429-L455).
- **R:** [tools/blender/fbx_readback.py:95-105](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c/tools/blender/fbx_readback.py#L95-L105).
- **P:** [tools/qa/validate_package.py:145-164](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c/tools/qa/validate_package.py#L145-L164).
- **U:** [docs/domain/areas/uv-atlas.md:32-37](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c/docs/domain/areas/uv-atlas.md#L32-L37).
- **T:** [tests/qa/test_uv.py:10-29](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/d89ea6a2d583bce1c05d59f9e032fd2bd946ce9c/tests/qa/test_uv.py#L10-L29).

### Finite-polygon contracts: a real boolean gap, not just different labels

**Engine (E):** after computing tile origin and `p = padding / size`, require
at least three finite 2-component points, signed UV area **strictly greater than
`1e-10`**, and every point inside the padded rectangle with `1e-6` UV tolerance.
The return type for these well-formed inputs is boolean.

**Checker (Q):** first reject short/malformed/nonfinite input as `invalid`; then
reject `abs(area) <= 1e-12` as `invalid`, negative area as `mirrored`, an out-of-tile
point as `cross_tile`, and insufficient requested padding as `margin`. Otherwise
return `None`. Its `validate_uv` wrapper is exactly `face_issue(...) is None`.
The label precedence is observable: these are first-failure reasons, not all
problems on the polygon. Checker comments explicitly document the diagnostic split.

For otherwise eligible, finite positive-area polygons with valid parameters, the
source predicates leave a disagreement interval **`1e-12 < A <= 1e-10`** in
normalized UV-square units. This interval is a source-derived statement; the corpus
uses one clearly interior witness, not equality/rounding-boundary tests.
For sufficiently large negative area both reject, but checker names `mirrored`;
for very small negative magnitude checker would name `invalid` first (source-only,
not an additional executed control). No independent winding-against-world-geometry
check is provided by these API arguments; the observable operation is UV sign.

**No area-policy decision is established here.** The UV area sheet U records no
mirrored islands, margin and inter-island padding as separate requirements and
coverage gaps; it does not supply either numerical area cutoff. A change from one
cutoff to the other would change eligibility, unlike retaining separate diagnostics.
This report leaves that decision to the user and does not declare either cutoff
regulatorily correct.

### Independent exact controls and observations

Corpus was fixed in this file before the first execution, without outcome-driven
retuning. Execution: Python **3.14.7**, exit **0**; **15 cases, 45 direct calls**
(engine boolean, checker reason, checker boolean), no pytest or full suite.
Triangle sides are `s = 2^-k`, vertices `(0,0), (s,0), (0,s)`; therefore exact
signed area is `s*s/2`. Padding is zero for all three small-area triangles, and
origin-zero coordinates avoid cancellation. The independent oracle computes a
rational fan relative to the first point, not a call to either module's area code.
It computes minimum **signed** scalar distance to `x=0`, `y=0`, `x=1`, `y=1`,
then multiplies by 2048. Negative clearance means a vertex is outside the tile;
it is not a Euclidean outside-distance magnitude. Two-point input has zero fan
area but is not an eligible polygon. Malformed/nonfinite controls have no oracle area.

| Case | Padding px | Exact signed area | Min border clearance px | Engine `validate_uv` | Checker `face_issue` | Checker `validate_uv` |
|---|---:|---:|---:|---|---|---|
| positive_quad | 16 | 1/4 | 512 | `True` | `None` | `True` |
| reversed_quad | 16 | -1/4 | 512 | `False` | `mirrored` | `False` |
| zero_area | 0 | 0 | 0 | `False` | `invalid` | `False` |
| below_1e-12 (`k=21`) | 0 | 1/8796093022208 (`2^-43`) | 0 | `False` | `invalid` | `False` |
| between_thresholds (`k=18`) | 0 | 1/137438953472 (`2^-37`) | 0 | `False` | `None` | `True` |
| above_1e-10 (`k=15`) | 0 | 1/2147483648 (`2^-31`) | 0 | `True` | `None` | `True` |
| inside_margin | 16 | 255/1024 | 4 | `False` | `margin` | `False` |
| same_margin_zero_padding | 0 | 255/1024 | 4 | `True` | `None` | `True` |
| cross_tile | 16 | 1/4 | -512 | `False` | `cross_tile` | `False` |
| too_few_vertices | 0 | 0 | 512 | `False` | `invalid` | `False` |
| wrong_point_length | 0 | n/a | n/a | `False` | `invalid` | `False` |
| nan_coordinate | 16 | n/a | n/a | `False` | `invalid` | `False` |
| positive_inf | 16 | n/a | n/a | `False` | `invalid` | `False` |
| negative_inf | 16 | n/a | n/a | `False` | `invalid` | `False` |
| scalar_point | 0 | n/a | n/a | exception X | exception X | exception X |

`None` above is a successful **return**, not missing evidence. Reason strings are
returns too. X is exactly **`TypeError: object of type 'int' has no len()`** in
all three calls, because a point is the scalar `1`; it must not be recorded as
`False` or `invalid`. Other malformed controls return normally. Every call receives
a deep copy; all **45 supplied inputs** have identical pickle bytes before/after,
including NaN and the exception paths. Frozen source inputs are never passed to a
mutating call. This verifies immutability for this corpus, not arbitrary iterators
or user-defined numeric/container objects.

Computed decimal area cross-checks: `2^-43 = 1.1368683772161603e-13`,
`2^-37 = 7.275957614183426e-12`, `2^-31 = 4.656612873077393e-10`.
The margin case's left edge is `2^-9`, hence exactly 4 px at size 2048;
requested margin is 16 px (`1/128` UV), well beyond the shared `1e-6` UV
slack (`0.002048` px). The cross-tile quad extends to `x=1.25`, well beyond
that slack. These controls do not attempt UDIM addressing tests, density tests,
translated cancellation tests or the numerical `signed_area`/edge-density scope
already owned by PR #407.

### Diagnostics/padding differences are intentional; area equivalence is unresolved

Checker Q explicitly separates `cross_tile` (outside unpadded tile) and `margin`
(inside tile but too close to border). Engine E returns one `False` for both.
For the isolated margin witness, **both** booleans switch from failure to success
when requested padding goes from 16 to 0; this is parameter-dependent behavior,
not a disagreement in the finite point predicate or evidence of an island defect.
The checker docstring says a caller should report margin as review because the
regulation asks for a margin without a size. However, `face_issue` only returns
a string and its boolean wrapper rejects it; **no current production caller
converts this string to a review finding**. Do not infer a live review gate from
the comment. Likewise, per-face tile-border clearance is not a measurement of
distance between two UV islands (U, UV-12/13).

The area gap cannot be explained by diagnostic richness: `between_thresholds`
returns different booleans with padding zero. Unifying the face validators, swapping
imports or treating checker acceptance as engine acceptance would silently move
that boundary. Shared low-level arithmetic would not by itself settle eligibility.
All parameter experiments here use tile 1001, size 2048 and nonnegative padding;
invalid tile/size/padding evaluation-order contracts were not probed.

## How it applies to this repository (file paths)

| Path / route | Current observable contract and limitation |
|---|---|
| `src/dt_ai/geometry/uv.py` -> `src/dt_ai/validate/bundle.py` | B imports engine eligibility and requires it at line 116; failure raises `ValueError("Invalid/mirrored/cross-tile UV: <surface id>")`, caught at lines 128–129 as C003 `fail`. Area and padding failures share this message. The tiny-triangle witness establishes a direct predicate rejection only; bundle parameters come from material layout and undergo additional profile/identity/density checks. |
| `src/dt_ai/cli/main.py` | C invokes bundle validation for build/validate, prints `delivery_passed=False`, returns 1 if any finding fails, and returns 2 for incomplete development validation. This exposes engine rejection in **synthetic development bundles**, not general customer package acceptance. B lines 39–45 require synthetic labels; lines 179–192 retain unimplemented/manual delivery limitations. No bundle was constructed or validated here. |
| `src/twinqa/uv.py` | Q's `face_issue` and boolean wrapper are directly callable and covered by existing QA tests T. Tracked production searches in `src/` and `tools/` found no caller of either checker face eligibility helper except their internal wrapper. This is a bounded static call-site result, not proof that no external library user exists. |
| `tools/qa/validate_package.py` | Imports checker `sequential_tiles`, not its face validator. Lines 104–108 check filename tile sequence and leave scene UV checks `not_run`; lines 198–206 invoke `add_scene` only with scene readback requested. P calls `scene_findings`. That route does not expose the direct checker area-gap witness. |
| `src/twinqa/scene.py` | S gates the V008 scene checks to `kind == "vpm"` and `role != "light"`; it consumes `uv_channels`, `mirrored_uv_triangles` and `udim_tiles` (`*MainGlass` only for glass). No `face_issue` call, no 1e-12/1e-10 face-area test, no margin reason-to-finding translation. |
| `tools/blender/fbx_readback.py` | R counts mirrored loop triangles via determinant `< 0`, without either eligibility cutoff; collects triangle-centroid tile facts. Thus a scene mirrored-island finding uses a third path, not checker face eligibility. This is source inspection only; no Blender run and no address tests. |
| `docs/domain/areas/uv-atlas.md` | U explicitly distinguishes partial scene mirroring/channel/glass coverage from unimplemented margin/inter-island-padding metrics. This report does not extend that coverage or resolve C29 padding variants. |

Caller evidence command: `git grep -n -E '(face_issue|validate_uv)' -- src tools`
returned the engine definition/import/bundle call and checker definitions/internal
wrapper only (plus its explanatory comment). Repository searches including tests
also found direct QA/API controls, not an additional production route. Existing
`test_margin_is_separate_from_cross_tile` already covers the qualitative diagnostic
split; proposing it again as new test work would be duplication.

## Proposed next tasks

1. **Freeze UV eligibility policy compatibility controls (S effort; M value).**
   Add focused direct-API regression controls with independent area expectations,
   retaining separate engine/checker outcomes, without changing policy or production
   imports. Concrete input -> expected observation: tile 1001, size 2048, padding 0,
   `[(0,0),(2^-18,0),(0,2^-18)]` -> engine `False`, checker `None`/`True`;
   `k=21` -> `False` / `invalid`; `k=15` -> `True` / `None`. Include the scalar-point
   control -> the exact TypeError above rather than a fabricated invalid return.
   Value: prevents helper consolidation from silently erasing an observable gap.
   No user threshold choice is needed to preserve today's contract. Exclude #407
   arithmetic/density controls, existing margin tests and queued UDIM address tests.

2. **Decide face-eligibility area policy before consolidation (M effort; M value).**
   First ask the user whether the separate `1e-10` and `1e-12` cutoffs should remain
   intentional contracts or become one policy; do not implement a default answer.
   Concrete decision witness: the `2^-37` triangle with padding 0 currently yields
   engine `False` -> checker `None`/`True`; retaining policy must preserve that pair,
   while an approved unified cutoff must specify explicitly whether both reject or
   both accept it. Also specify whether a future margin caller maps the 4 px / 16 px
   witness's `margin` to review or fail; no such live caller exists today. Value:
   separates code reuse from a user-owned acceptance-policy change. Any subsequent
   implementation/adoption is a separately approved scope, not authorized here.

## Open questions for the user

- Should engine's `A > 1e-10` and checker's `A > 1e-12` eligibility remain distinct,
  or should one documented threshold apply to both? If unified, which value and
  scope (synthetic bundle vs general face diagnostics) are intended?
- Is a future checker margin diagnostic intended to remain review-only as its
  docstring suggests, or should it reject? This is not a request to wire it into
  scene/package gates now, nor to settle C29 inter-island padding here.

Neither question blocks this report-only evidence delivery. No GitHub issue or
follow-up card was created, and no normative interpretation was adopted.

## Frozen standalone corpus and self-contained reproducer

Save the following code as a standalone file if desired and execute from the pinned
repository root with `python -B <file>`. It imports the actual source modules by
path without package dependencies; uses the standard library only. The corpus is
unchanged from the version frozen before execution. Alternatively, execute the
embedded block directly without writing a script:

```bash
python -B -c 'from pathlib import Path; p=Path("docs/research/uv-eligibility-semantic-boundaries.md"); exec(compile(p.read_text(encoding="utf-8").split("```python\n",1)[1].split("```",1)[0],str(p),"exec"))'
```

```python
import copy
import importlib.util
import math
import pickle
import platform
from fractions import Fraction as F
from pathlib import Path

ROOT = Path.cwd()
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

engine = load("engine_uv", "src/dt_ai/geometry/uv.py")
checker = load("checker_uv", "src/twinqa/uv.py")
quad = [[.25, .25], [.75, .25], [.75, .75], [.25, .75]]
def triangle(exponent):
    s = 2.0 ** -exponent
    return [[0., 0.], [s, 0.], [0., s]]
def replaced(value):
    q = copy.deepcopy(quad)
    q[0][0] = value
    return q

# Frozen before execution; all use tile=1001 and size=2048.
CASES = [
    ("positive_quad", quad, 16),
    ("reversed_quad", list(reversed(quad)), 16),
    ("zero_area", [[0., 0.], [.25, 0.], [.5, 0.]], 0),
    ("below_1e-12", triangle(21), 0),
    ("between_thresholds", triangle(18), 0),
    ("above_1e-10", triangle(15), 0),
    ("inside_margin", [[2.0**-9, .25], [.5, .25], [.5, .75], [2.0**-9, .75]], 16),
    ("same_margin_zero_padding", [[2.0**-9, .25], [.5, .25], [.5, .75], [2.0**-9, .75]], 0),
    ("cross_tile", [[.75, .25], [1.25, .25], [1.25, .75], [.75, .75]], 16),
    ("too_few_vertices", [[.25, .25], [.75, .25]], 0),
    ("wrong_point_length", [[0., 0., 1.], [.5, 0.], [0., .5]], 0),
    ("nan_coordinate", replaced(float("nan")), 16),
    ("positive_inf", replaced(float("inf")), 16),
    ("negative_inf", replaced(float("-inf")), 16),
    ("scalar_point", [1, [.5, 0.], [0., .5]], 0),
]

def independent_oracle(q):
    if not all(isinstance(p, list) and len(p) == 2
               and all(isinstance(c, (int, float)) and math.isfinite(c) for c in p)
               for p in q):
        return "n/a", "n/a"
    points = [[F(c) for c in p] for p in q]
    # Exact fan determinants relative to first vertex, not either module's area.
    a = points[0]
    area = sum(((b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])) / 2
               for b, c in zip(points[1:], points[2:]))
    # Signed clearance to the four tile=1001 borders, in pixels.
    clearance = min(d for x,y in points for d in (x, y, 1-x, 1-y)) * 2048
    return str(area), str(clearance)

def observe(fn, original, padding):
    q = copy.deepcopy(original)
    before = pickle.dumps(q)
    try:
        result = "return " + repr(fn(q, 1001, 2048, padding))
    except Exception as exc:
        result = type(exc).__name__ + ": " + str(exc)
    return result, before == pickle.dumps(q)

print("Python", platform.python_version(), "cases", len(CASES))
print("case | padding | exact signed area | min border px | engine validate_uv | checker face_issue | checker validate_uv | unchanged E/F/V")
for name, q, padding in CASES:
    area, distance = independent_oracle(q)
    observations = [observe(fn, q, padding) for fn in
                    (engine.validate_uv, checker.face_issue, checker.validate_uv)]
    print(" | ".join([name, str(padding), area, distance] + [x[0] for x in observations]
                     + ["/".join(str(x[1]) for x in observations)]))
```
