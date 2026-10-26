# Raw evidence

## Final four-arm evidence

Archive: `G:/Мой диск/AGR-evidence/712-agent-lookup/t_99d4aef2-lookup-evidence-80.zip`

SHA256: `8a2a0d23c9923b8d2da290f65088ca9a0918c8bd7fa0a271e80265e7f384909b`

Size: **2,948,551 bytes**. ZIP readback: **453 entries**, CRC verification clean.
A scan of all entries found no current OAuth token. `SHA256SUMS.txt` beside the archive preserves
both this checksum and the earlier A-C-only archive checksum. No binary is committed; no Git LFS.

Contents: all **80** final stream-json transcripts and source rows, both independent judge
transcripts, final deliverables, the immutable local graph, manifests, xerj setup receipts,
the entire excluded attempt's transcripts/answers/grades, and the same-session tool-overflow Read.
The final authoritative scored matrix is `results.jsonl`; the first **60** lines retain the exact
SHA256 in `extension-D.json`, with only **20** D rows appended. The excluded attempt is separate.

Excluded: OAuth credentials/token values, runtime caches, node_modules, virtualenv, xerj binary
and data/journal storage, private PDF/DWG files and source binaries. Global receipts contain only
hashes/paths, not global-file contents. The native xerj node was stopped after the measurements;
process/port readback confirmed no owned xerj process and connection refusal on 127.0.0.1:19270.

## Preserved earlier evidence

The A-C-only archive remains at `G:/Мой диск/AGR-evidence/712-agent-lookup/t_99d4aef2-lookup-evidence.zip` (**2,612,563 bytes**, **370 entries**).
It is not the final matrix. Its excluded attempt/raw grading and the original 60-row receipt remain
available; the new archive includes those too, without mixing their metrics into the 80 final rows.

## Reproduce checks

```bash
python tools/methods/agent_lookup.py validate docs/methods/sources/agent-lookup/results.jsonl
python tools/methods/agent_lookup.py summarize docs/methods/sources/agent-lookup/results.jsonl
```

`isolation-80.json`: **80/80** raw answers/usage/wall/session IDs agree; **20/20** identical-prompt
quadruplets; **4/4** clean source clones without the key; **3/3** non-graph clones without graph
output. All **20/20** D initializations exposed exactly seven allowed read-only native MCP tools;
no feedback/mutation/hub call occurred. Both actual judge model/session IDs were checked.
`isolation.json` preserves the original 60-row audit. Audits refuse receipt overwrite; rechecking
must use a fresh receipt output. Initial non-isolated automatic CLI-cache writes are disclosed in
PROTOCOL.md; all final 80 answer sessions plus both judges preserved the monitored global hashes.

Verification: one full suite through the two-slot wrapper — **15,170 passed / 21 skipped /
179 deselected**, **1507.39 s**. After the additive D extension: affected controls **36 passed**;
no shared production/configuration/fixture files changed, so the full suite was not repeated.
