# Exact commands and versions

Run from the issue worktree. Shell is Git Bash; native executable arguments use `C:/...` paths.
No `graphify install`, `uv tool install`, `claude mcp add`, global npm install, or graphify/context7
worker-profile setup was used.
The discarded first attempt's automatic Claude runtime-cache writes and their repair are disclosed in
[PROTOCOL.md](PROTOCOL.md#reportingisolation-repairs-and-excluded-attempt).

## Versions observed

| Component | Version / source |
|---|---|
| Pilot main | `4c863c1a4616f1812595536d0507f53034e9acfe` |
| Claude Code | `2.1.301` (`claude --version`) |
| Answer model | `claude-sonnet-4-6` for A, B and C |
| Independent API judge | `claude-haiku-4-5-20251001` |
| graphifyy | `0.9.96`, latest from `https://pypi.org/pypi/graphifyy/json` at start |
| context7 MCP | `4.4.4`, latest from `npm view @upstash/context7-mcp version` at start |
| Runner Python | `3.14.7` |
| Graphify venv Python | `3.13.3` |
| Node / npm | `v22.17.1` / `10.9.2` |
| uv | `0.8.3 (7e78f54e7 2025-07-24)` |

## Project-local setup actually used

```bash
uv venv C:/x/methods/lookup/t_99d4aef2/venv --python 3.13
uv pip install --python C:/x/methods/lookup/t_99d4aef2/venv/Scripts/python.exe graphifyy==0.9.96
npm install --prefix C:/x/methods/lookup/t_99d4aef2/context7 @upstash/context7-mcp@4.4.4 --no-audit --no-fund
```

Each of `repo` (B), `baseline` (A) and `context7-repo` (C) was created with this template,
substituting the literal directory name. No branch from another card was read:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --no-checkout --local C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_99d4aef2 C:/x/methods/lookup/t_99d4aef2/repo
git -C C:/x/methods/lookup/t_99d4aef2/repo checkout --detach 4c863c1a4616f1812595536d0507f53034e9acfe
C:/x/methods/lookup/t_99d4aef2/venv/Scripts/graphify.exe extract C:/x/methods/lookup/t_99d4aef2/repo --code-only --no-cluster --max-workers 2
```

Graph build produced **17,839 nodes / 48,230 edges** from **1,500 code files**. It skipped
**463 docs / 1 paper / 10 images**, plus **66 unclassified files**; **95 code files yielded no symbols**.
The local AST test does not measure graphify's hosted/semantic documentation extraction.
Graph build/install wall time was not separately measured; they are not included in query medians.
No PDFs or DWGs were uploaded. The graph has not been registered globally or installed as a skill.

## Actual per-variant sessions

`results.jsonl` stores the **exact argv array for every session**, including identical question and
system prompts. `mcp-A.json`, `mcp-B.json`, `mcp-C.json` preserve the exact configuration payloads
at their original paths `C:/x/methods/lookup/t_99d4aef2/{A,B,C}.json`.

Common argv (see arrays for literal prompt text and executable):

```text
claude -p <same question prompt> --model claude-sonnet-4-6
  --no-session-persistence --disable-slash-commands --setting-sources ""
  --settings {"disableAllHooks":true,"autoMemoryEnabled":false}
  --strict-mcp-config --mcp-config C:/x/methods/lookup/t_99d4aef2/<variant>.json
  --tools Read,Grep,Glob
  --allowedTools Read,Grep,Glob,mcp__graphify__query,mcp__graphify__path,mcp__graphify__explain,mcp__context7__resolve-library-id,mcp__context7__query-docs
  --permission-mode dontAsk --system-prompt <identical SYSTEM from runner>
  --output-format stream-json --verbose
```

- A uses an empty MCP config and cwd `.../baseline`; only Read/Grep/Glob are available.
- B uses the stdlib read-only adapter `tools/methods/graphify_mcp.py`, which dispatches
  `graphify query <question> --graph <graph.json> --budget 2000`,
  `graphify path <source> <target> --graph <graph.json>`, or
  `graphify explain <concept> --graph <graph.json>` without a shell. Cwd `.../repo`.
- C launches `node .../context7/node_modules/@upstash/context7-mcp/dist/index.js` for this
  session only; cwd `.../context7-repo`. No API key configured for context7.

`session_environment()` supplies **only to the child**:
`CLAUDE_CONFIG_DIR=C:/x/methods/lookup/t_99d4aef2/claude-state` and the existing access token read
from `~/.claude/.credentials.json` into `CLAUDE_CODE_OAUTH_TOKEN`. It removes
`CLAUDE_CODE_SIMPLE`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_BASE_URL`. The token is never in argv,
committed files or reports; no credential file is copied or written. The session's temporary
runtime directory is not an evidence artifact and must not be uploaded.

## Measurement, grading and reproduction

```bash
python tools/methods/agent_lookup.py run C:/x/methods/lookup/t_99d4aef2
python tools/methods/agent_lookup.py judge C:/x/methods/lookup/t_99d4aef2
python tools/methods/agent_lookup.py validate docs/methods/sources/agent-lookup/results.jsonl
python tools/methods/agent_lookup.py summarize docs/methods/sources/agent-lookup/results.jsonl
uv run pytest -q tools/methods/test_agent_lookup.py -p no:cacheprovider --basetemp=C:/x/t_99d4aef2-controls
```

The first two commands were run once more after excluding the entire non-isolated attempt.
The runner preserves completed raw answers rather than paying for replacement answers after parser errors.
For an independent new experiment, use a new per-card scratch directory and adjust the three config paths;
exclusive writes refuse to overwrite previous data. Do not delete old evidence to make a rerun appear fresh.

Numeric scores require an actual finite JSON number equal to the preregistered answer; a number inside a
string is not silently coerced. All 18 API answers are graded by the independent Haiku model, blinded to
variant names; `judge.json` preserves its prompt, usage, session ID, grades and reasons. Judge/setup tokens
are separate from answer-model per-question totals. Full tokens count cache-read and cache-creation input
as well as uncached input and output. API fees are list-price telemetry, not subscription billing.
