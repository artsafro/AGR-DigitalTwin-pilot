# Route split evidence (#1425)

## Scope and provenance

Parent #1424 / PR #1428 at `24eb533525bc54f5859d79063f5462bb5d3f8684` supplies
all duplicate statuses; #1409 is already in main. This change is stacked on that parent.
No export, packaging, validation or DCC core is modified. No runtime build_manifest/control
layer is added. The default reader entry is [README](README.md): six short schemes and six
owners/migration tables, all generated from the existing route/context YAML.

The content revision identifies the parsed architecture YAML snapshot, not a customer source
revision or a delivery receipt. The source-revision requirement is visible on every scheme;
actual per-run revision/hashes remain the existing source/export/package evidence's responsibility.
Manual steps remain manual and conditional; there is no newly asserted successful delivery.

## Regression evidence

- Tests-first commit `9c8b2b14`: `tests/test_route_views_1425.py` failed, 1 failed, because the
  short SVG was absent. Run before implementing the generator additions.
- Initial hostile probes exposed five publication problems: input alias, output alias, hardlink,
  pre-existing `.partial` and input changes during rendering. Preflight/exclusive temporary creation
  now reject them before publication. The symlink fixture hit Windows privilege error 1314 and was
  replaced by a portable exact configured-input/output alias; the real hardlink witness is retained.
- New generated probe removes each of 74 ordered source stages independently; each mutation is
  rejected. Six routes' new schemes and six context maps are checked for arrow endpoints binding
  only nodes, never pink lists, and absence of Python location lists on the canvas.
- Status witness uses synthetic historical, wrapper, own-duty and live-bypass rows and a repeated
  map: only one bypass is counted; the migration issue link is retained. Conflicting status rows
  fail, as do unmapped keys, unsupported stages, repeats, reordered stages, empty/partial input and
  non-finite labels. Seven groups is valid; eight is rejected.
- Stale SVG, Excalidraw and Markdown outputs are each detected by existing `--check` drift checks.
- First broad affected run: 497 passed, 5 failed. One legacy inventory assertion needed the new
  42-file inventory; four native child processes exited `0xC0000142` without stderr (host resource
  failure). After inventory repair, the exact five tests passed through `uv run python -m pytest`
  (5 passed in 73.89s). Original logs remain in the worktree's ignored `tmp/1425-*.log`.
- Final exact-head affected command/counts and eval receipts are in the PR body; full suite is
  deferred to the merge batch (rule 68 / D297). No broad-suite pass is claimed here.

## Review rework r2: pink-box crossings

Reviewer P1-1 on `abd911bb` found seven arrow/list intersections on four context maps;
the endpoint-only regression could not see them. Tests-first commit `925eb04d` reproduces
exactly those four failing maps (4 failed / 8 passed). The old endpoint test is retained.

Context relations now use side ports and deterministic orthogonal free-space routing around
all rectangles. SVG writes every polyline segment rather than silently drawing only the first.
The new independent closed-slab intersection oracle checks every arrow against every unrelated
pink box on all 18 generated boards, including detailed routes, contexts and short schemes.
SVG/Excalidraw point sequences must match. A generated synthetic matrix covers 32 directed
layouts (four row offsets, four list heights, both directions); an obstructed port must raise
before adding an arrow. Existing stage/status/publication probes run together with this fix.

Six supplementary context renders are preserved separately at
`G:/Мой диск/AGR-evidence/1425-route-maps/r2/`, without changing the r1 evidence.
NPM was visually read back: lines go around pink boxes; the detailed context labels are still
dense at overview scale, so the short schemes remain the primary reader entry.

```text
791526eea88b04028f82879c7175e74d6fcc9756181a62baf77ac7ed6c7030c5  contexts.png
c559e251425c186d32b7a6f3a0d9e0048528e6a90c00f340790c3041241d8a00  vpm-oks-contexts.png
e7d4eb762ae98fcaa3f2d328a203ef17dca0d063b05644e4c1b603264f59d426  ground-contexts.png
9d07cdc6e947089bd0e66720a84ecc9e7680a9e4afc5592d3132736a3a3266c2  maf-contexts.png
f84491e57686306066ee985b6d549188fbc7ee1d8f05e1f3915b2885a76dc54d  flora-contexts.png
9534a8c0148de0f5ada437a651974b01b6fa4f7cf422350b6211e617920ed5cb  package-contexts.png
```

## Renders for Artem

ImageMagick 7 renders of generated SVGs, white background, Segoe UI, density 110.
The NPM and package renders were visually read back: Russian text is legible, steps/artifacts
are separated, export owner and acceptance conditions are visible, and no arrow starts at a list.
All six PNG files and the hash manifest are supplied with the review handoff. Binaries are not in git.

External evidence: `G:/Мой диск/AGR-evidence/1425-route-maps/`.

```text
e9a3b8a469340a4cb782ece7b3a6036a857a4b57fd67fc11b414945f1b3b4473  flora-route-scheme.png
2faa9a3f839be6f1577afbfef5f762d0c249f40936e8d60032ed634463afd527  ground-route-scheme.png
a9072564f188e17d70452d8f877384b130a15f310665ff550409e26ab9858b42  maf-route-scheme.png
c2621bd6aaf63068fd8e732fb7454c0e7df384ff5968de82c0aaa9d2aa225683  npm-oks-route-scheme.png
237f701c6aa33e46913a43ffe2463a84ae56c14f05a668ff86135b543f9f2ef7  package-route-scheme.png
2fa50c2c79989d8a3930d6022b1af01502bbb8c916999a61349eb9fc21855dd1  vpm-oks-route-scheme.png
```
