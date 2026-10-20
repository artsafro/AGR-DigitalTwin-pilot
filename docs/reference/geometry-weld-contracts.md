# Geometry weld contracts

## Scope and source snapshot

Factual implementation reference, not a new requirement, recommendation, shared
kernel specification or delivery acceptance gate. All coordinates below are
synthetic metres. Source base: `6e9f3faa22d0e05889c01e46ce15805ed9168a99`
(`HEAD` and `origin/main` at inspection). Implementations are unchanged.

The [repository-health report][health], pinned internally to
`a1052e3d3a3c5ef096028fb68982e1337da4eba4`, describes the **historical**
single-grid rounding checker in section 4.A.2 and proposed Task 3.
Issue #101 replaced that checker. Its old boundary-split and diagonal-inflation
examples are not descriptions of the checker at this reference's base.
The extractor still uses shifted grids; it is not the replacement checker.

The [domain geometry rules][domain] separately record the regulatory **0.002 m**
distance tolerance for duplicates/self-intersections (reg p.8 §3.7 and p.29
§3.11). That value is not the extractor's `WELD_M`, the building's `weld_m`,
a rounding precision, or a universal implementation displacement limit.

## Comparison

| Property | Checker: `twinqa.geometry.mesh.weld` | Extractor: `dt_ai.spec.mesh._weld` | Engine: `dt_ai.geometry.from_spec._Weld` |
|---|---|---|---|
| Source | [weld, WELD_EPS_M and _pairs_within][checker] | [WELD_M][extractor-constant], [_Sets and _weld][extractor] | [_Weld and _weld_plan][engine], [_r][rounding] |
| Input / distance | `(n,3)` positions; Euclidean distance from a group's first position, reach `weld_m + 1e-9` | `(n,3)` NumPy positions; eight floor grids with cell side `WELD_M = 1e-4`, shifts `{0,0.5}^3`; not a Euclidean-radius predicate | Scalar coordinates along one axis, `w = spec.weld_m`; absolute difference, threshold `w + FEATURE_TOL` ([`1e-9`][engine-constant]); values rounded to 9 decimals by `_r` |
| Ordering / representative | Deduplicate and sort positions lexicographically; each untaken position takes the still-free positions within reach. Representative is the group's first position, not a centroid | Union first input indices in each cell across successive grids. Union-find root is an original vertex index, not necessarily the smallest coordinate or globally earliest input index | Fixed values rounded, deduplicated and sorted. Remaining values rounded, deduplicated and sorted; each free group snaps to its smallest value |
| Transitivity | Not connected-component closure: an already taken point does not extend its group | Union-find is transitive initially; wide-component fallback can split the result again | Free grouping is measured from the group's smallest value, not its latest member; no chain extension beyond that threshold |
| Inclusivity | Norm `<= weld_m + 1e-9`, including nominal equality; numeric guard means a slightly larger distance can also join | Cell equality, no added epsilon. Separation strictly below `WELD_M/2` on each axis suffices to share a shifted cell before fallback; this does not guarantee final membership after fallback. Half-cell boundaries depend on `floor`; fallback uses component extent `> WELD_M`, so extent equality does not trigger fallback | Fixed proximity and free group span use `<= w + 1e-9`; queries are rounded first. A nominal threshold is included, not rejected |
| Bound / displacement | Members lie within reach of the representative; two members can be up to twice reach apart. Function labels positions; it does not move them | After fallback, each coordinate differs from its representative by at most `WELD_M` (floating-point arithmetic applies). This is **per-axis**, not a Euclidean `WELD_M` bound; a diagonal can approach `sqrt(3) * WELD_M` | Scalar snap bound applies to constructor coordinates after rounding. Independent X/Y bounds alone allow a diagonal exceeding `w`. The current `_weld_plan` separately rejects a full 2D move `> wx.w + FEATURE_TOL` with `BuildError` |
| Fixed anchors | None | None | Fixed anchors preserved even when closer to each other than `w`. Nearest eligible fixed anchor takes priority over free groups; exact distance ties choose the lower anchor |
| Return | Integer array `(n,)`: compact group labels `0..k-1` in original input order; **not vertex indices** | Integer array `(n,)`: original representative vertex indices, potentially noncompact; positions are `v[rep]`. [_mesh][extractor-consumer] compacts these and remaps triangles | Callable object: `weld(v)` returns one scalar coordinate. `values()` returns sorted fixed anchors followed by free-group minima, **not necessarily globally sorted** |

`_Weld.__call__` is a lookup over constructed groups, not an insertion operation:
a new coordinate outside a group's stored range and all fixed neighborhoods stays
unchanged. None of these helpers returns an acceptance status or a dropped-element
report. Both array maps retain one entry per input vertex; `_Weld` returns one
coordinate per call. No file paths or material mappings are arguments to these
three helpers.

Empty, malformed and nonfinite inputs are not covered by a common fail-closed
contract: for example the checker explicitly returns an empty integer array for
empty input. These are low-level grouping helpers, not validators. This reference
does not assert rejection of NaN/inf, partial models or unsupported delivery
inputs. Exactly-at-threshold welding is intentionally inclusive where stated;
calling that a validation failure would contradict the unchanged implementation.

## Worked examples

1. **Checker, no transitive chain.** X coordinates `[0, .002, .004]`, Y=Z=0,
   `weld_m=.003` give labels `[0,0,1]`: groups `{0,1}` / `{2}`.
   The middle point cannot extend the first group to `.004`. Permuting input
   permutes labels back to input order without changing these memberships.
2. **Extractor, shifted grids.** X `[.000099,.000101]`, Y=Z=0 straddles the
   plain floor grid but shares a shifted cell and yields representatives `[0,0]`.
   The example in the existing test uses `[.000049,.000051,.5]` and yields
   `[0,0,2]`.
3. **Extractor, wide component.** X `[0,.00004,.00008,.00012]` initially chains
   across grids. Extent `.00012 > WELD_M` causes the entire component to use
   the **plain** grid's first input indices: `[0,0,0,3]`. Translating X by
   `.00003` yields `[0,0,2,2]`. There is no translation-invariant partition
   guarantee. The fallback is not a Euclidean distance weld.
4. **Engine, priority and preservation.** With `w=.003`, fixed `[0,.004]` stay
   separate, although their capture neighborhoods overlap. `.0028` maps to
   `.004`, the nearest anchor, rather than the lowest anchor; `.002` ties and
   maps to `0`. With free values `[.006,.008]` and fixed `[.010]`, `.006` stays
   a free minimum while `.008` maps to `.010`, not to the equally distant free minimum. Fixed anchors are considered first. With free `[.004]` and fixed
   `[.010]`, `values()` is `[.010,.004]`.
5. **Axis versus plan.** Independent X/Y snaps from `(.0029,.0029)` to `(0,0)`
   each fit `.003`, but move about `.004101219 m` in 2D. At this base
   `_weld_plan` raises `BuildError`. A move `(.003,0)` is included.

## Evidence on the chosen base

These links point only to tests present at the source base:

- [Checker tests][checker-tests]: nominal equality, diagonal separation, chain,
  compact IDs, shifted open-edge count and engine `_hold` integration.
  The chain test's pairwise `2*W` assertion is not a strict `W` group-diameter
  contract, despite the module's broad introductory wording.
- [Extractor shifted-grid test][extractor-shift-test] and
  [extractor chain test][extractor-chain-test]. The latter checks
  `abs(chain-chain[rep]).max()`, a coordinate-wise maximum, on an axis-aligned
  chain; its name does not establish a Euclidean bound for arbitrary 3D data.
- [Engine plan tests][engine-tests]: diagonal rejection, generated fixed-line
  rejection, opening-end rejection and inclusive in-bound build controls.

Pending evidence, **not run or counted here**: unmerged PR branches
`improve/checker-weld-greedy-oracle` (`54ac6f9`,
`tests/qa/test_weld_greedy_oracle.py`),
`improve/extractor-weld-grid-fallback-controls` (`541c921`,
`tests/test_spec_weld_grid_contract.py`), and
`improve/engine-axis-weld-fixed-controls` (`1273d71`,
`tests/test_engine_axis_weld_contract.py`). Those test paths are absent on this
base and are intentionally not linked as available evidence.

Optional weld/tolerance experiment report: no matching tracked report under
`docs/research/` or `docs/experiments/` in `origin/main`, then in `HEAD`, at
inspection. No experimental acceptance claim is made.

## Execution receipt

Only this reference file changed. Documentation existence regression (no new
pytest file):

```bash
uv run python -c "from pathlib import Path; p=Path('docs/reference/geometry-weld-contracts.md'); assert p.is_file(), f'missing reference: {p}'; print('reference-exists 1/1')"
```

Before creation: exit 1, `AssertionError: missing reference` (RED, 1/1 failed).
After creation: exit 0, `reference-exists 1/1` (GREEN). This is not a failing
geometry regression: unchanged affected tests already passed on the baseline.

Affected tests, executed before and after documentation creation:

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_3fb22c09 tests/qa/test_mesh_weld.py tests/test_spec_extract.py tests/qa/test_from_spec.py
```

- Before: `199 passed, 6 deselected in 13.20s`.
- After: `199 passed, 6 deselected in 10.61s`.

Full suite, executed once with a 400-second tool timeout:

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_3fb22c09
```

Result: **timed out after 400 seconds**, progress last reported at 45%,
six skip markers visible, no failures printed before timeout. There is no final
pytest summary or trustworthy total pass count; full-suite verification is
incomplete. It was not rerun.

Standalone output (all 298/298 synthetic cases completed):

```text
checker-chain-order 6/6
checker-map-representative-bound 64/64
checker-threshold 2/2
extractor-shifts-fallback 4/4
extractor-map-axis-bound 64/64
extractor-not-euclidean 1/1
extractor-half-cell-pairs 64/64
engine-fixed-nearest-free-bound 64/64
engine-tie-priority-values-chain 4/4
engine-plan-inclusive-or-error 25/25
```

## Bounded standalone verification

This is an inline synthetic characterization probe, not a new pytest fixture or
kernel change. It checks the worked examples and generated finite cases against
the unchanged implementations. Bounds refer to the finite probes, not exhaustive
floating-point proofs. Source links below pin line anchors as well as commits.
Run from the repository root; the command writes no report or input files:

```bash
uv run python - <<'PY'
from itertools import permutations, product
import numpy as np
from twinqa.geometry.mesh import weld
from dt_ai.spec.mesh import _weld, WELD_M
from dt_ai.geometry.from_spec import _Weld, _weld_plan, BuildError


def xyz(xs):
    return np.column_stack((xs, np.zeros((len(xs), 2))))


v = xyz([0, .002, .004])
for order in permutations(range(3)):
    ids = weld(v[list(order)], .003)
    expected = np.array([0, 0, 1])[list(order)]
    assert np.array_equal(ids[:, None] == ids, expected[:, None] == expected)
print('checker-chain-order 6/6')
for k in range(64):
    p = np.random.default_rng(k).uniform(-.008, .008, (12, 3))
    p = np.vstack((p, p[0]))
    ids = weld(p, .003)
    assert ids.shape == (len(p),) and ids[0] == ids[-1]
    assert np.array_equal(np.unique(ids), np.arange(len(np.unique(ids))))
    for group in np.unique(ids):
        pts = p[ids == group]
        rep = np.unique(pts, axis=0)[0]
        assert np.all(np.linalg.norm(pts - rep, axis=1) <= .003 + 1e-9)
print('checker-map-representative-bound 64/64')
assert weld(xyz([0, .003]), .003).tolist() == [0, 0]
assert weld(xyz([0, .003000002]), .003).tolist() == [0, 1]
print('checker-threshold 2/2')
for xs, expected in [([.000099, .000101], [0, 0]),
                     ([.000049, .000051, .5], [0, 0, 2]),
                     ([0, .00004, .00008, .00012], [0, 0, 0, 3]),
                     ([.00003, .00007, .00011, .00015], [0, 0, 2, 2])]:
    assert _weld(xyz(xs)).tolist() == expected
print('extractor-shifts-fallback 4/4')
for k in range(64):
    p = np.random.default_rng(k).uniform(-2, 2, (24, 3)) * WELD_M
    rep = _weld(p)
    assert rep.shape == (len(p),) and np.all((0 <= rep) & (rep < len(p)))
    assert np.all(np.abs(p - p[rep]) <= WELD_M + 1e-18)
print('extractor-map-axis-bound 64/64')
p = np.array([[0, 0, 0], [.00009, .00009, .00009]])
assert _weld(p).tolist() == [0, 0]
assert np.linalg.norm(p[1] - p[0]) > WELD_M
print('extractor-not-euclidean 1/1')
for k in range(64):
    rng = np.random.default_rng(k)
    p = rng.uniform(-2, 2, (1, 3)) * WELD_M
    q = p + rng.uniform(-.49, .49, (1, 3)) * WELD_M
    assert _weld(np.vstack((p, q))).tolist() == [0, 0]
print('extractor-half-cell-pairs 64/64')
for k in range(64):
    offset = k * .01
    fixed = [offset, offset + .004]
    a = _Weld([offset + .0028], .003, fixed=fixed)
    assert all(a(f) == round(f, 9) for f in fixed)
    close = [offset, offset + .001]
    c = _Weld([], .003, fixed=close)
    assert all(c(f) == round(f, 9) for f in close)
    assert a(offset + .0028) == round(offset + .004, 9)
    free = offset + np.arange(8) * .002
    b = _Weld(free, .003)
    assert all(abs(b(x) - round(float(x), 9)) <= .003 + 1e-9 for x in free)
print('engine-fixed-nearest-free-bound 64/64')
a = _Weld([], .003, fixed=[0, .004])
assert a(.002) == 0
b = _Weld([.006, .008], .003, fixed=[.010])
assert b(.006) == .006 and b(.008) == .010
assert _Weld([.004], .003, fixed=[.010]).values() == [.010, .004]
assert _Weld([0, .002, .004], .003)(.004) == .004
print('engine-tie-priority-values-chain 4/4')
a = _Weld([], .003, fixed=[0])
for x, y in product([0, .001, .002, .0029, .003], repeat=2):
    expected_error = np.hypot(x, y) > .003 + 1e-9
    try:
        out = _weld_plan([[x, y]], a, a)
    except BuildError:
        assert expected_error
    else:
        assert not expected_error and np.array_equal(out, [[0, 0]])
print('engine-plan-inclusive-or-error 25/25')
PY
```

[health]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/docs/research/repo-health.md#4-geometry-implementations-welds-distance-metrics-and-independent-checker-risks
[domain]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/docs/domain/geometry.md#regulation-geometry-rules-both-profiles-unless-noted
[checker]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/twinqa/geometry/mesh.py#L63-L128
[extractor-constant]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/spec/mesh.py#L35
[extractor]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/spec/mesh.py#L140-L178
[extractor-consumer]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/spec/mesh.py#L200-L235
[engine]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/geometry/from_spec.py#L149-L199
[engine-constant]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/geometry/from_spec.py#L65
[rounding]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/geometry/from_spec.py#L863-L864
[checker-tests]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/tests/qa/test_mesh_weld.py#L16-L60
[extractor-shift-test]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/tests/test_spec_extract.py#L235-L238
[extractor-chain-test]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/tests/test_spec_extract.py#L372-L378
[engine-tests]: https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/tests/qa/test_from_spec.py#L619-L670
