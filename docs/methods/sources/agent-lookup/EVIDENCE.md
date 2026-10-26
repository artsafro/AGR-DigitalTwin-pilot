# Raw evidence

Archive: `G:/Мой диск/AGR-evidence/712-agent-lookup/t_99d4aef2-lookup-evidence.zip`

SHA256: `70f6d7e9d419869322af17b49c3572b385491140bed4cc8fa25320c0b650ce71`

Size: **2,612,563 bytes**. ZIP readback: **370 entries**, CRC verification clean.
`SHA256SUMS.txt` is stored beside the archive. No binary is committed and no Git LFS is used.

Contents: final 60 stream-json transcripts and per-session rows, independent judge transcript,
frozen local graph, manifests, the entire excluded attempt's transcripts/answers/grades,
and the one same-session tool-result overflow read in Q06-B. The final authoritative 60 scored rows
are committed in `results.jsonl`; the excluded attempt is not merged into them.

Excluded from archive: OAuth credentials, environment token values, runtime configuration/cache
files, node_modules, virtualenv, private PDF/DWG files and source binaries. Global-config receipts
contain hashes and paths, not contents. A secret-value scan of all **370** ZIP entries found
no current OAuth token. Drive's immediate read-after-close was transiently unavailable; an independent
terminal readback and a subsequent full CRC readback both succeeded.

Reproduce the receipt with:

```bash
python tools/methods/agent_lookup.py validate docs/methods/sources/agent-lookup/results.jsonl
python tools/methods/agent_lookup.py summarize docs/methods/sources/agent-lookup/results.jsonl
```

The `audit` action produced `isolation.json`: 60 raw answers/usage/wall/session IDs agree;
20 same-prompt triplets; 3 clean source clones without the key; 2 non-graph clones without graph output.
It refuses to overwrite an existing receipt; rechecks must use a fresh receipt output, never clobber
inputs. The before/after receipt covers the **final isolated run plus independent judge**; the initial
attempt's automatic global CLI-cache writes are explicitly disclosed in PROTOCOL.md.
