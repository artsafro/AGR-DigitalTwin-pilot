# Parts schema checker: can unvisited branches hide unsupported vocabulary?

## Summary

- **Yes:** unsupported-vocabulary detection is visited-node checking, not a schema-wide capability check.
- Absent optional properties, empty arrays and unreached definitions can conceal `exclusiveMinimum`.
- An accepting supported `anyOf` branch skips later branches; reversing their order can raise instead.
- The frozen standalone probe produced **14 observations: 5 empty lists, 2 nonempty lists, 7 exceptions**.
- An exception is a checker/schema error, not an instance-validation rejection; `[]` is not a vocabulary audit.
- The current PartsList schema contains no unsupported keywords; these synthetic cases do not establish a production bypass.
- Current converter defaults do leave schema descendants unvisited, so future schema changes need traversal-aware review.
- Only this report changed; no parity-corpus rerun, pytest, DCC, installs, production edits or policy decisions.

## Findings

### Frozen standalone reproduction

Run from the repository root with `python -B`; standard library only. The runner extracts and executes the unchanged checker definitions from the source AST, avoiding package initialization and third-party dependencies. It does not import the converter, run its CLI, or write artifacts. All cases are built before the first checker call. `U` is an intentionally unsupported schema; `S` uses only supported vocabulary. Expected results are deliberately not asserted before observation.

```python
import ast
import copy
import hashlib
import json
import platform
from pathlib import Path
import math
import re

source = Path("src/dt_ai/parts/readers/fbx.py")
raw = source.read_bytes()
print("Python", platform.python_version())
paths = [source, Path("schemas/PartsList.schema.json"),
         Path("docs/research/parts-schema-checker-parity.md"),
         Path("src/dt_ai/parts/model.py")]
for path in paths:
    print("SHA256", path.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())

names = {"_ANNOTATIONS", "_TYPES", "_type_ok", "schema_errors"}
tree = ast.parse(raw, filename=str(source))
nodes = [node for node in tree.body
         if (isinstance(node, ast.FunctionDef) and node.name in names)
         or (isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in names for t in node.targets))]
assert len(nodes) == 4
namespace = {"math": math, "re": re}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
check = namespace["schema_errors"]

U = {"type": "number", "exclusiveMinimum": 0}
S = {"type": "number", "minimum": 0}
P = {"type": "object", "properties": {"x": U}}
I = {"type": "array", "items": U}
D = {"$defs": {"N": U}, "type": "object",
     "properties": {"x": {"$ref": "#/$defs/N"}}}
C = {"type": "object", "properties": {"x": S},
     "required": ["x"], "additionalProperties": False}
cases = copy.deepcopy([
    ("root_zero", 0, U),
    ("root_positive", 1, U),
    ("property_absent", {}, P),
    ("property_present", {"x": 0}, P),
    ("items_empty", [], I),
    ("items_nonempty", [0], I),
    ("definition_unused", {}, D),
    ("definition_reached", {"x": 0}, D),
    ("anyof_supported_first", 0, {"anyOf": [S, U]}),
    ("anyof_unsupported_first", 0, {"anyOf": [U, S]}),
    ("anyof_rejecting_first", -1, {"anyOf": [S, U]}),
    ("empty_items_with_minitems", [], {**I, "minItems": 1}),
    ("supported_control_accept", {"x": 0}, C),
    ("supported_control_reject", {"x": -1}, C),
])
print("FROZEN", json.dumps(cases, sort_keys=True, separators=(",", ":")))
counts = {"empty_list": 0, "nonempty_list": 0, "exception": 0}
for name, instance, schema in cases:
    try:
        result = check(instance, schema)
    except Exception as exc:
        counts["exception"] += 1
        print(name, "exception", type(exc).__name__ + ": " + str(exc))
    else:
        category = "empty_list" if result == [] else "nonempty_list"
        counts[category] += 1
        print(name, category, repr(result))
print("TOTAL", len(cases), counts)
```

### Observed results (not predicted verdicts)

Executed once on **CPython 3.14.7**, using the frozen snippet above. All seven exceptions had the exact same type/message:

`ValueError: schema keywords not supported: ['exclusiveMinimum']`

| Frozen case | Actual return | Actual exception |
|---|---|---|
| `root_zero` | no return | `ValueError` with message above |
| `root_positive` | no return | same |
| `property_absent` | `[]` | none |
| `property_present` | no return | same |
| `items_empty` | `[]` | none |
| `items_nonempty` | no return | same |
| `definition_unused` | `[]` | none |
| `definition_reached` | no return | same |
| `anyof_supported_first` | `[]` | none |
| `anyof_unsupported_first` | no return | same |
| `anyof_rejecting_first` | no return | same |
| `empty_items_with_minitems` | `['$: item count out of range']` | none |
| `supported_control_accept` | `[]` | none |
| `supported_control_reject` | `['$.x: -1 out of range']` | none |

Final output: `TOTAL 14 {'empty_list': 5, 'nonempty_list': 2, 'exception': 7}`.
The supported control differs only in its instance (`x=0` versus `x=-1`); it demonstrates ordinary acceptance and constraint rejection without unsupported vocabulary. The empty-array/minItems case shows that a nonempty error list also does **not** establish a complete vocabulary check. Root zero and root positive both raise: unsupported-keyword detection there precedes numeric validation, rather than deciding whether the instance satisfies a constraint.

The `anyOf` experiment is specifically about **capability detection**, not proof that an instance violating the whole union was accepted. Its supported branch accepts zero, so a union containing that branch can accept zero; the surprising difference is `[]` versus an exception solely from reordering. No reference validator or dialect comparison was run.

### Why traversal produces these results

Personally verified by reading the unchanged source [S1]:

1. `src/dt_ai/parts/readers/fbx.py:308-316` computes unknown keys from the **current schema dictionary only** and raises immediately. It does not recursively inventory schema children. The docstring's “unsupported keyword raises (fail closed)” and the parity report's “when it sees a keyword” [S3, lines 172-184] need that visited-node qualification.
2. `$defs` is in `_ANNOTATIONS` (`fbx.py:296`), so its contents are not scanned simply because the dictionary exists. A reached `$ref` resolves one definition and invokes the checker (`fbx.py:317-321`). The probe uses the same schema for reached and unused cases, changing only presence of `x`.
3. `fbx.py:322-323` uses `all(schema_errors(...) for ... in anyOf)`. A rejected branch returns a nonempty, truthy list, so evaluation continues. An accepting branch returns falsey `[]`, ending `all` immediately; later branches are never called. Exceptions propagate; no branch-level exception recovery converts them to errors or tries a later accepting branch. `anyof_rejecting_first` confirms that a preceding ordinary rejection does not conceal the unsupported branch.
4. A type mismatch returns before instance-child descent (`fbx.py:324-327`), but **after** this node's unknown-key check, `$ref`, and `anyOf`. Thus a keyword directly on a visited node is not hidden by that node's mismatching type. Keywords deeper in its `properties`/`items` can remain unseen. This ordering matters for nullable fields.
5. Array recursion only enumerates actual elements (`fbx.py:340-345`). Empty arrays never evaluate `items`, even after recording a `minItems` error.
6. Object recursion iterates actual instance keys, not every property schema (`fbx.py:346-355`). Missing required keys produce messages but their subschemas are not visited. Optional absent keys produce neither a child visit nor a missing-key error. A schema-valued `additionalProperties` is likewise reached only for actual extra keys.

These are source-derived explanations of the measured cases, not claims of general JSON Schema semantics. An unused definition or absent optional property need not invalidate an instance; the question here is whether the checker certifies that it understands **the whole supplied schema**. It does not.

## How it applies to this repository

### Current schema versus hypothetical future mutations

**Current production file:** `schemas/PartsList.schema.json` [S2]. Read-only inspection finds only the checker allow-list and annotations: `$defs`, `$ref`, `additionalProperties`, `anyOf`, `const`, `default`, `description`, `enum`, `items`, `maxItems`, `maxLength`, `maximum`, `minItems`, `minLength`, `minimum`, `pattern`, `properties`, `required`, `title`, `type`. All `additionalProperties` values are `false`; references are local `#/$defs/...`. All seven definitions have incoming references; there is no currently orphaned definition. This agrees with the merged parity report's schema inventory [S3, lines 15-17], without rerunning its numeric/dialect corpus.

The following is an inventory of **places future unsupported keywords could be hidden**, not a claim those keywords exist now. Paths beginning `/$defs/` denote schema locations, not instance paths.

| Current schema location(s) | Traversal condition / hypothetical mutation |
|---|---|
| Root `properties` (S2:401-481), `required` (482-489) | `gate1`, `joints`, `questions`, `schema_version`, `status` are optional in the schema. Unsupported constraints nested under one can be unseen when it is absent. Required properties also are not descended into when missing, but then the checker already reports a missing key; that is not an accepted-instance example. |
| `/$defs/Approval/properties/schema_version` (S2:21-26); `Joint/.../embed_depth_m` (57-71); `PartEntry/.../{build_as,legend_item,library_ref,mesh}` (107-176); `Question/.../answer` (268-281); `SourceRef/.../{page,region,schema_version,sha256}` (315-369) | These are the nested properties omitted from their definitions' `required` lists. An unsupported keyword under an absent property is not visited. Omitting the containing object/array also hides descendants. |
| Root `{joints,parts,questions,sources}/items` (S2:413-439,456-463); `/$defs/PartEntry/properties/sources/items` (213-220); `/$defs/Joint/properties/parts/items` (78-89); `/$defs/SourceRef/properties/region/anyOf/0/items` (334-350) | Unsupported vocabulary in `items` or below its reference target needs actual elements. Root `joints` and `questions` permit empty arrays. `parts`, `sources` and part sources require at least one; joint parts require two and non-null region four, so empty values there already produce errors rather than accepted valid values. A null region does not descend into the array's items. |
| All ten `anyOf` sites: root `gate1`; Joint `embed_depth_m`; PartEntry `build_as`, `legend_item`, `library_ref`, `mesh`; Question `answer`; SourceRef `page`, `region`, `sha256` (S2:58,108,135,149,163,269,316,335,358,403) | Each current union has the non-null branch first and null branch second. A supported non-null value accepts branch 0 and skips branch 1: vocabulary newly added to branch 1 can stay unseen. Conversely, putting an unsupported keyword directly on branch 0 raises even for null, because unknown-key checking precedes type mismatch. Null is **not** a general way to conceal a new keyword on the numeric/string/object branch root. Descendants within that branch can still be skipped (e.g. region `items`, Approval `properties`). No branch order was changed here. |
| `/$defs/{Approval,Joint,PartEntry,PartSource,Question,SourceRef,TriangleBudget}` and incoming `$ref`s (S2:2-399,405,415,428,436,458,478) | Definitions are checked only when referenced on the visited route. Joint and Question descendants can remain unused for empty lists. With `gate1=null`, Approval is actually entered through branch 0, then returns a type error before its property children; an unsupported keyword at the **Approval root** would raise, while one under `Approval.properties.actor` could be hidden. PartEntry, PartSource, SourceRef and TriangleBudget are reached for structurally valid current lists. A future unreferenced definition would also be unscanned. |
| Root and definition `additionalProperties` (S2:4,46,105,236,266,303,379,400) | No current schema-valued child here: all values are `false`. If a future version changes one to a subschema, unsupported vocabulary in it would need an actual extra property to trigger descent (S1:352-355). This is a new structural mutation, not a current hidden subschema. |

Annotations (`title`, `description`, `default`) are not treated as schema children; arbitrary keys inside a default value are not evidence of unsupported vocabulary. A hypothetical preflight would need schema-position awareness, not an indiscriminate walk over every JSON dictionary.

### Callers and reachability

A read-only Python-source search (`rg -n 'schema_errors|parts.readers.fbx|from dt_ai.parts.readers import fbx'`, excluding docs/data) found the only non-test external call to `schema_errors` in **`fbx.run()`**, plus its own recursive calls [S1:321-355,385]. The module CLI invokes `run()` at `fbx.py:401`; `SCHEMA_PATH` is fixed to the repository PartsList schema (`fbx.py:29`). There is no CLI argument selecting an arbitrary supplied schema. Direct Python callers could supply one; that public-function possibility is what the standalone probe exercises, not an observed deployed input route.

`run()` converts structure facts into a `PartsList`, performs `model_dump_json()` without exclusion options, parses it, and calls `PartsList.model_validate` before `schema_errors` (`fbx.py:382-385`). Only a nonempty error list is wrapped as `StructureError` (`386-387`); checker exceptions propagate out of `run()`. `main()` catches `ValueError` and returns 1 (`402-404`), before `publish` at line 388 can be reached. This source inspection establishes the exception handling route; the probe did **not** run the CLI or publication.

`convert()` explicitly produces `joints=[]`, `gate1=None`, `status="draft"`; questions are conditional and part nullable fields use defaults (`fbx.py:268-291`; `src/dt_ai/parts/model.py:43-51,84-101` [S4]). Source provenance has nullable page/region defaults (`src/dt_ai/core/provenance.py:16-21` [S5]). Thus instance-driven omissions of **descendant visits** are reachable in ordinary converter output: Joint is not reached, Question may not be reached, Approval properties are skipped after the null type mismatch, and null region skips array items. Nullable-field null branches are later than their supported non-null alternatives, so non-null outputs can skip those null branches as well. Optional-key absence in the bare-schema probe is not asserted to be the converter's serialization behavior: its dump includes defaults. These are code-inspected paths, not an end-to-end converter experiment in this study.

`tests/parts/test_fbx_reader.py:271-280` [S6] characterizes ordinary bad instances and a **root** unsupported keyword; it does not establish schema-wide coverage. Existing reader calls also occur at lines 65 and 163. `tests/parts/test_fbx_structure_blender.py:144-147` [S7] exercises CLI output and a direct schema check; no Blender test was executed here. No caller-wide preflight was found. Current production vocabulary is supported, so these paths show **future schema-evolution exposure**, not a demonstrated current production bypass. Model validation is a separate boundary, not proof that this checker has audited its schema vocabulary.

### Source identity and limits

Content **SHA-256** recorded by the actual probe (not a Git commit SHA):

| Source | SHA-256 |
|---|---|
| S1 `src/dt_ai/parts/readers/fbx.py` | `292f132a63bdd4fcf16c90d0bbf2540f4351dde8e6664b52eb1f43719d6b5030` |
| S2 `schemas/PartsList.schema.json` | `6530a652d22b6a857c4a5735529c5685b4471f84368918bbcd994634b3c99f42` |
| S3 `docs/research/parts-schema-checker-parity.md` | `93a59db40042223ea16d55f50d2925c7c9ef6378f5078398af55701d3cfb6ca2` |
| S4 `src/dt_ai/parts/model.py` | `8de0528e88299ace8b1f87688279ac519d00f3b0bd937964b64b8b719c73dc1f` |

S5–S7 are the read-only provenance and two test source files cited above. **Seven primary local sources, zero external sources**; no outside behavioral claims are relied on. S1 and S2 hashes match those in the prior parity report, but S4's hash differs from that report's historical snapshot; current code was inspected rather than assuming historical model results. Commit SHA was not queried: git/gh execution and access outside this worktree are prohibited for this card. Content hashes identify the actual checker/schema bytes without claiming a branch or commit identity.

The frozen probe ran unchanged checker AST definitions, not a reimplementation; it intentionally did not exercise package import initialization, model validation, filesystem output or DCC. The initial report contained the full case list before the run, and the runner printed its frozen JSON before any checker calls. No generated/brute-force invariant claim is made: these are 14 bounded observations, not exhaustive schema-language certification.

## Proposed next tasks

### 1. Evaluate schema-position-aware capability preflight — value M / effort M

Proposal only: in a separately authorized task, prototype an instance-independent walk of schema-bearing positions (`properties`, `items`, each `anyOf` branch, `$defs`, and schema-valued `additionalProperties`) using the existing vocabulary, with schema-location diagnostics and a defined reference/cycle strategy. Input: the exact frozen `P` schema paired with `{}` **or** `{"x":0}` → expected preflight output in both cases: unsupported `exclusiveMinimum` at `/properties/x/exclusiveMinimum`, regardless of whether instance validation would visit it. Input: the same schema with `exclusiveMinimum` replaced by supported `minimum` → no capability diagnostic. Input: both orders of the frozen `[S,U]` union → the same unsupported-keyword finding at the corresponding branch location. Value: separates schema capability from instance acceptance without confusing an exception with rejection. Adoption, placement, failure interface and handling of unused definitions require user agreement; this report does not decide to add a global preflight, dependency, dialect or numeric policy.

## Open questions for the user

- Is the intended guarantee only “raise on unsupported vocabulary at visited nodes,” or should a future API certify the whole supplied schema before evaluating any instance?
- If a preflight is desired, should it inspect every `$defs` entry (including unused definitions) and report all findings with schema paths, or stop at the first unsupported location?
- Should an eventual schema-capability failure remain an exception distinct from instance error lists? The current CLI already turns `ValueError` into a nonzero exit, but direct callers see the exception.

No issues, commits, push or PR were created; those are left to the driver under this run's no-git/gh constraint. Requested PR metadata, if the driver publishes: base `main`, repository `artsafro/AGR-DigitalTwin-pilot`, title **Research: Parts schema checker: can unvisited branches hide unsupported vocabulary?** Use the Summary above and a tool-generated Agent trace per `docs/agents/WORKFLOW.md:272-275`; no trace was fabricated here. Requested branch name is `docs/research-parts-schema-unvisited-vocabulary`; this worker did not rename the harness worktree branch.

Tests: **0 pytest tests**, no RED/GREEN/full-suite run (research-card exemption). Standalone probe: **14/14 cases recorded**, with returns and exceptions separated as above. Only `docs/research/parts-schema-unvisited-vocabulary.md` was edited; production, schemas, tests, guards, procedures, dependencies, CI and data were untouched.
