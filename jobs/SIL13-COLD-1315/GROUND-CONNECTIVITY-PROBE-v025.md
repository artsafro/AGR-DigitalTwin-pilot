# #1315 — late Ground connectivity diagnostics, v025 (NOT ADOPTED)

**Current NPM/VPM files are byte-unchanged from the main v025 checkpoint.**
No model decision, geometry repair, skirt waiver or readiness gain is claimed here.
This late experiment is separate from the immutable163file main seal and its
30driver/696line inventory. No shared production/checker code changed.

## Actual source-derived Ground, not synthetic

Using actual native NPM Ground26378triangles and its preserved material assignments:
- The base plus existing plot skirt alone measures **1.0009999275m** perimeter drop.
- The layered-cake base hidden beneath other coverings occupies **6304.132731m2**.
  That is measured artificial underlay coverage, not permission to remove it.
- Route1 crops the hidden underlay and constructs small vertical coating-to-base
  step bands, retaining all other surface/skirt triangles. It REFUSES a degenerate
  CDT cut cell before producing a mesh; strict failure log retained.
- Distinct numerical route2 explicitly lists collapsed near-zero cut cells instead
  of emitting them. It creates an actual Ground-only candidate of **33276tris**,
  **3185step bands**,0unattached overlay edges; projected whole NPM is **180888**,
  over180000. One face-edge component, consistent winding, but not watertight;
  public xView **16faces/885vertices/321bowties/13pairsFAIL** and skirt drop **0m**.

Both routes are REJECTED, not adopted or whole-site exported. UV lineage, original
visible-source/domain fidelity and authority for a changed underlay mask have NOT
been certified. Do not apply these meshes to the site or manufacture a source-mask
approval. Current real Ground still has the1848unskirted coating-ring edges.

## Independent minimal SYNTHETIC checker counterexample

The real candidate's failures do not establish a checker bug on their own. A
separate minimal analytic witness removes those confounders:

- one closed, positive-volume, winding-consistent, face-edge-connected solid;
- plot perimeter1.001m, connected interior raised island6mm;
- public xView0faces/0vertices/0pairs/0bowties;
- public `_skirt_perimeter_drop` returns `('ok',0.006)`, not the1.001m plot perimeter.

Tight actual-function test: `uv run pytest -q test_skirt_connected_oracle.py`
from a copied evidence directory → **1failed**, specifically `0.006 >=1.0`.
The test reads the analytic vertex/face fixture and re-executes production code;
it does not assert against a stored verdict. The code inventories/connectivity
and skirt-function AST parity are sealed. The five skirt-related functions are
identical on `origin/main` **a98bc8918440ddbcc0826c4d9b58fd8aa6741284**.

This is a **synthetic counterexample**, NOT a pass or exemption for the real site.
It requires independent checker/domain triage before a production fix. Do not
exclude arbitrary nested rings, change source heights, or add invisible metre-deep
internal partitions merely to satisfy the checker.

## Follow-up and evidence

Independent read-only triage card **t_66104c70**, assignee `dt-worker`, status`triage`;
created and read back. No dependency edge strands it behind completion of #1315.
No new GitHub issue or PR created. Duplicate search found historical#1133/#1224/
#1108, no connected-step issue/open PR/active skirt card. The follow-up must bind
implementation/issue/branch approval before writing shared code; it cannot waive
#1315's current failures or reopen D340/old model gates.

Immutable evidence root:
`G:/Мой диск/AGR-evidence/1315-cold-silikatny/v025/late-diagnostics/`

-18files,3656396bytes;
-`manifest.json` SHA256`711d24942025f097faa33293fb3bba741e220dee1009a375a04f97a15cfb8ba5`;
-`SHA256SUMS.txt` SHA256`8c44c084ed20a8fe0645cab761366e2107b523c4b8eaa58e56c43b8bbe792177`.

Copy `test_skirt_connected_oracle.py` and `late-skirt-oracle/input.npz` together
before reproducing in another worktree. Generating the optional trimesh connectivity
receipt requires isolated `uv run --with scipy --with trimesh`; the first missing
optional graph-engine error was self-repaired without shared dependency changes.

All main-phase current-site hashes,22originals and seals remain unchanged.
After the late documentation/deviation update, affected receipt checks:
`env -u UCX_PROGRESS_REPORT PYTEST_ADDOPTS='' uv run pytest -q tests/test_decisions.py tests/test_area_requirement_sheet.py tests/test_ground_surface_requirement_sheet.py tests/test_maf_requirement_sheet.py tmp/cold-v025/test_omission.py tmp/cold-v025/test_ucx_progress.py tmp/cold-v025/test_checkpoint_v025.py tmp/cold-v025/test_late_isolation.py -p no:cacheprovider --basetemp=C:/x/t_d9ae7dc0/v025-postlate`
→ **135passed (6.24s)**. These guard rejection/isolation/integrity, not a checker
fix; the independent synthetic expected-perimeter test remains1RED. The final
procedure walk remains`passed=false/errors=[]/waits:user0`.
**Full suite: deferred to merge batch (rule68).**
