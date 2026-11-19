# Accepted geometry: record, freeze, then consume

The workflow freeze rule applies to every user-accepted part, not only the AC08 kernel
freeze [D201]. It does not change technical QA thresholds or make a failed QA result pass.

## Fixed job record

Write `jobs/<ID>/accepted.json` immediately after acceptance. Record the user's date,
quote, scope and answer reference in TASK.md (and optionally `evidence` in the manifest).
Hash the actual versioned source bytes; do not infer acceptance from a QA report.
Keep the prior manifest when explicitly replacing the accepted set after a new acceptance.
Do not replace it merely because a newer QA/export file exists.

Synthetic format example (paths and digest are illustrative, not a real acceptance):

```json
{
  "schema": "accepted-set/1",
  "job": "SYNTHETIC",
  "evidence": "synthetic:user-answer-1, date, quote and scope in TASK.md",
  "accepted": [
    {"part": "body_A", "version": "v004", "path": "geometry/body_A_v004.blend",
     "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
  ]
}
```

One active row per part. `path` is absolute or relative to the manifest directory.
A whole review scene can be the source of several accepted parts; those rows may share
its path/hash, but the consumer must name the part explicitly. No basename, file extension,
"latest", or cross-part hash fallback identifies a part. Hashes are lowercase SHA-256.
Unknown fields, duplicate JSON keys/parts, empty/partial records and nonfinite JSON fail closed.
`evidence` records provenance for people, not authenticated machine approval.

## Later-stage brief and input gate

Before UV, textures, UCX or export, cite `accepted.json` and its complete-file SHA-256,
plus each selected part/version, in the brief. Check the **actual source geometry inputs**:

```bash
uv run python tools/state/accepted_set.py --job JOB --inputs body_A=/absolute/body_A_v004.blend windows_A=/absolute/windows_A_v003.blend
# Equivalent single-part form:
uv run python tools/state/accepted_set.py --job JOB --part body_A --inputs /absolute/body_A_v004.blend
```

Exit 0 means every supplied file's bytes match that part's accepted hash AND the recorded
source still matches it. A byte-identical copy is allowed; a newer geometry with different
bytes is not. Exit 1 means rejected/malformed/missing input, never permission to proceed.
Every well-formed input gets a result row; malformed requests get a named global error,
not a partial pass. CLI usage errors exit 2. The tool writes only JSON to stdout, no report,
output or `.partial` files. Never redirect stdout to any input/manifest/brief or alias.

For a deterministic preflight of incident 1, optionally write a structured brief:

```json
{
  "schema": "accepted-brief/1",
  "job": "SYNTHETIC",
  "accepted_set_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "actions": [{"part": "body_A", "stage": "textures", "version": "v004"}]
}
```

Run `uv run python tools/state/accepted_set.py --job JOB --brief brief.json`
(or combine `--brief` with `--inputs`). Stages are `geometry`, `uv`, `textures`, `ucx`,
`export`, `review`. Each non-geometry action must cite the accepted version. A geometry
write, even a same-version rewrite, is not a read-only review and is refused by default.
A user's explicit permission for a new geometry version is recorded in the **job record**:

```json
"change_decisions": [
  {"part": "body_A", "from_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
   "to_version": "v005", "actor_role": "user", "decision": "approved",
   "ref": "synthetic:user-answer-2"}
]
```

A matching `geometry` action may now start v005. Other versions/parts, stale prior hashes,
agent decisions and refusals do not authorize it. Re-hash the manifest in the brief after
recording the decision. This is permission to create a candidate, **not acceptance of it**:
UV/texture/UCX/export still cannot select v005 until the user accepts it and the frozen set
is explicitly updated. A necessary UV cut or a new mapped scene similarly does not inherit
the old file hash. Preserve the accepted source and get explicit scoped permission/acceptance.

This structured preflight is a pytest regression rather than a transcript grader: the current
eval runner consumes Claude transcripts, while this guard has a deterministic job-record/brief
seam and Hermes supplies no Claude transcript. It does not claim to understand free prose,
authenticate the user's reference, intercept every DCC read, or lock the filesystem. Producers
must invoke it on all selected geometry immediately before reading and keep those bytes immutable.
Re-hashing catches observed input/source/manifest mutation during the check; restored-between-read
changes and later mutations are outside this point-in-time contract. No stale success is persisted.

## Findings after acceptance

Keep diagnostics and delivery gates truthful, but do not repair frozen geometry autonomously.
Send one consolidated list, each finding with a stable ID, part/version/hash, description,
helper name and point/location in a **separate versioned review copy**. Record its scene path/hash,
sent-list reference/date and the user's response in TASK.md. Reuse that reference on restart;
do not send the same list again or launch successive fix/QA repair rounds. A genuinely new finding
is appended to the pending helper list, not silently fixed. The user decides whether/when to reopen
geometry and which parts/versions to change. This is a human workflow rule, not a notification service
or an automated exactly-once delivery guarantee. Helpers must not change the accepted source bytes.

## 4bk-k3 evidence

Source: [TASK.md at 6aa786d9](https://github.com/artsafro/AGR-DigitalTwin/blob/6aa786d9/jobs/4bk-k3/TASK.md),
sections `Tower floor 1 (A) geometry accepted`, `Checks v006–v009`, and
`A geometry for UV and textures = accepted v004 set`.
The issue also cites retro `docs/retros/2026-11-15-4bk-k3-gf-stylobate.md`, incidents 1/4,
and memory `accepted-geometry-freeze`; those are not present on the pilot base.

Artem accepted floor 1 on 2026-11-14 17:31: «принимаю первый этаж, все норм по геометрии».
The accepted source set was body A v004, windows A v003, roof A v003 in
`K3_GF_full_review_v004.blend`. Five subsequent QA rounds v005–v009 led to texture work
on body v008e. On 2026-11-15 11:55: «надо было мне отдельно указать, я бы их посмотрел,
хелперы поставить мне»; at 12:54: «нужно использовать геометрию, которую я вчера утвердил»
(quoted in #1445). Later sections of the same TASK.md describe explicitly requested UV loops
and Artem's hand-finished finals: this historical regression must **not** overwrite those finals.

[Historical manifest](evidence/1445/accepted-2026-11-14.json) records the three original
versioned files rehashed during this card, not proof of their bytes at the historical acceptance
instant and not a new current production approval. No `jobs/4bk-k3/accepted.json` is manufactured
from history: the current job owner must record the current accepted finals at the next handoff.
[Dry-run evidence](evidence/1445/dry-run.md) checks real v004 and rejects real v008e with those hashes.
