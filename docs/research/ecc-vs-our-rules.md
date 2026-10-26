# ECC practices vs our agent rules

Date: 2026-10-26.

ECC main: `25278e7d7b6cf6e6a4e7a6c8e10f14ff22f0eb5b` (read-only clone `C:/x/ecc`, cited below as `ecc/…`).
Pilot main: `4c863c1a4616f1812595536d0507f53034e9acfe` (this worktree).

Related note, not repeated here: [`docs/research/agent-harness-practices.md`](agent-harness-practices.md) (pass@k, budgets, stuck detection, why unbounded loops and auto-merge stay out).

## Method

Top-level practices are the ones ECC states as the system, not the skill catalog: the loop and the six contrasts in `ecc/README.md:135` and `ecc/README.md:1223`, the five principles in `ecc/AGENTS.md:9`, every file in `ecc/rules/common/`, the three guides (`ecc/the-shortform-guide.md`, `ecc/the-longform-guide.md`, `ecc/the-security-guide.md`), the three contexts, and the verification / eval / instinct skills those guides name.

Mapped against `AGENTS.md`, `docs/agents/WORKFLOW.md`, `docs/agents/REVIEW_CHECKLIST.md`. `docs/agents/task-intake.md` is not in this worktree. A search for `Karpathy` and `working principles` hits only the task card, so PR #711's principles are not in this tree.

`MISSING` means no line in those files states the same practice. A nearby line is named in the note and is not an equivalent. `different` means a real line covers the same job with other wording or a tighter bound. An extra clause our files do not state does not make the broader practice `MISSING`. A line about a different job is not an equivalent.

A local refinement is a narrower rule we do not have. It is not an ECC requirement and it is not a row in the gap column. Review round 1 (2026-10-26) re-checked every row on that standard.

Colouring failures used for drafts and local refinements are only `docs/retros/2026-10-22-tec26-colouring-claude.md` and `docs/retros/2026-10-22-tec26-colouring-codex.md`. A `MISSING` row with no such failure is not drafted.

## Table

| # | Practice | ECC file | Our equivalent | Note |
|---|---|---|---|---|
| 1 | Plan before code | `ecc/rules/common/development-workflow.md:17` | `docs/agents/WORKFLOW.md:24` | different: the plan follows the contract |
| 2 | Keep the plan as an artifact | `ecc/README.md:1223` | MISSING | nearest `docs/agents/WORKFLOW.md:190-191` keeps the requirement and appends a later decision. The plan step is not a saved artifact. Not a cited colouring failure |
| 3 | Search and reuse before new code | `ecc/rules/common/development-workflow.md:9` | MISSING | nearest `docs/agents/WORKFLOW.md:262` extracts a reusable thing after the second repeat. It is not a search-before-write gate. Not a cited colouring failure |
| 4 | Read the source before writing | `ecc/contexts/research.md:10` | `docs/agents/WORKFLOW.md:14-16` | different: read the real inputs before writing. An extracted facade table is local refinement 1, not this line |
| 5 | Ask while researching | `ecc/contexts/research.md:8` | `docs/agents/WORKFLOW.md:113` | different: ask only unresolved questions that change the result |
| 6 | TDD: RED, then GREEN, with evidence | `ecc/README.md:1224` | `docs/agents/WORKFLOW.md:468` | different: RED replay of a regression, not a gate on every change |
| 7 | 80% coverage and unit, integration, and e2e | `ecc/rules/common/testing.md:3` | MISSING | our measured-check bar is `docs/agents/WORKFLOW.md:69`. Not adopted |
| 8 | A wrong check is fixed, not kept green | `ecc/rules/common/testing.md:25` | `docs/agents/WORKFLOW.md:30-32` | different: classify the cause, fix it, and do not reword a failure into a pass. The required-set denominator is local refinement 5 |
| 9 | A fresh context reviews the code | `ecc/README.md:1225` | `docs/agents/REVIEW_CHECKLIST.md:3` | the reviewer is not the author |
| 10 | Critical findings block the merge | `ecc/rules/common/code-review.md:55` | `docs/agents/REVIEW_CHECKLIST.md:39` | different label (P1). The merge still waits for the user: `docs/agents/REVIEW_CHECKLIST.md:38` |
| 11 | The result is evidence, not the claim | `ecc/README.md:1243` | `AGENTS.md:59` | exit 0 is not a finished model |
| 12 | Verify again after the change | `ecc/skills/verification-loop/SKILL.md:16` | `docs/agents/WORKFLOW.md:29-32` | different: read the files back, fix the cause, rerun the affected checks. Rebuilding the named delivery package is local refinement 2 |
| 13 | Record what worked with evidence | `ecc/the-longform-guide.md:46` | `docs/agents/WORKFLOW.md:355-361` | different: on acceptance, record scope, hashes, checks run, failures and fixes. ECC's bullet does not require a colour-picture compare. That compare is local refinement 3 |
| 14 | The confirmed plan is what runs next | `ecc/README.md:1234` | `docs/agents/WORKFLOW.md:24-26` | different: execute follows the plan; an open decision blocks the stages that depend on it. Dropping superseded checks in a run already started is local refinement 4 |
| 15 | Distil the session and resume from that | `ecc/the-longform-guide.md:40` | `docs/agents/WORKFLOW.md:271` | handover, then a new context in the same worktree |
| 16 | Turn a repeated lesson into a skill | `ecc/the-longform-guide.md:91` | `docs/agents/WORKFLOW.md:357-361` | different: only after the user accepts; a skill waits for a second object (`docs/agents/WORKFLOW.md:263`) |
| 17 | Instincts with confidence scores | `ecc/README.md:1255` | MISSING | store is `ecc/skills/continuous-learning-v2/SKILL.md:3`. Not adopted |
| 18 | Hooks enforce checks outside the prompt | `ecc/README.md:1227` | `docs/agents/WORKFLOW.md:251` | skill gate and usage log |
| 19 | Scan the agent config as an attack surface | `ecc/README.md:1228` | MISSING | nearest `docs/agents/WORKFLOW.md:322` is an inventory, not a scanner. Not adopted |
| 20 | The safety boundary sits between the model and the action | `ecc/the-security-guide.md:261` | `docs/agents/WORKFLOW.md:363` | permission matrix |
| 21 | Do not skip permission checks | `ecc/rules/common/hooks.md:14` | `docs/agents/WORKFLOW.md:368` | `never` is not a prompt the model may override |
| 22 | Treat untrusted text as untrusted | `ecc/CLAUDE.md:15` | MISSING | no line in the mapped files. Not a cited colouring failure |
| 23 | Run untrusted work in a sandbox | `ecc/the-security-guide.md:128` | MISSING | nearest `docs/agents/WORKFLOW.md:392` says the guard asks and is not a sandbox. Not adopted |
| 24 | Log tool name, input, and approval | `ecc/the-security-guide.md:290` | MISSING | nearest `docs/agents/WORKFLOW.md:252` logs subagent, skill and command; `docs/agents/WORKFLOW.md:291` lists hook denials. Neither requires tool input and approval. Not a cited colouring failure |
| 25 | Kill the process group when the heartbeat stalls | `ecc/the-security-guide.md:318` | MISSING | already proposed in `docs/research/agent-harness-practices.md:107`. Not drafted |
| 26 | Keep persistent memory narrow | `ecc/the-security-guide.md:345` | MISSING | nearest `docs/agents/WORKFLOW.md:303` puts each kind of fact in one file. It does not forbid secrets in memory or a reset after untrusted runs. Not a cited colouring failure |
| 27 | Immutability | `ecc/rules/common/coding-style.md:5` | MISSING | `AGENTS.md:58` and `docs/agents/WORKFLOW.md:384` forbid overwriting sources. They do not say to create new objects instead of mutating existing ones. Not a cited colouring failure |
| 28 | KISS, DRY, YAGNI | `ecc/rules/common/coding-style.md:17` | MISSING | our order is `AGENTS.md:14`. Slogans not adopted |
| 29 | Prefer small files | `ecc/rules/common/coding-style.md:37` | MISSING | no line cap in the mapped files |
| 30 | Do not swallow errors | `ecc/rules/common/coding-style.md:50` | `docs/agents/REVIEW_CHECKLIST.md:12` | different: a silent fallback that hides a failure is a finding |
| 31 | Validate data at the boundary | `ecc/rules/common/coding-style.md:54` | MISSING | no line requires validating external input before use. `docs/agents/REVIEW_CHECKLIST.md:12` is the silent-fallback finding, a different practice. Not a cited colouring failure |
| 32 | Leave the tail of the context window | `ecc/rules/common/performance.md:22` | `docs/agents/WORKFLOW.md:275` | different threshold: about 40–50% |
| 33 | Route the model by task size | `ecc/rules/common/performance.md:3` | MISSING | not adopted. Named agents: `AGENTS.md:3` |
| 34 | Delegate to a specialist | `ecc/rules/common/agents.md:30` | `docs/agents/WORKFLOW.md:215` | named read-only subagents |
| 35 | Parallelise independent work | `ecc/rules/common/agents.md:39` | MISSING | `AGENTS.md:50` is one writer per worktree, which is ownership, not a parallel-execution policy. Not drafted: the colouring failure is a split before the scope existed (row 37) |
| 36 | The parent's last message includes the children's results | `ecc/rules/common/agents.md:55` | MISSING | nearest `docs/agents/WORKFLOW.md:229` calls one checker before "done". It does not require the parent's last message to carry every child, or forbid ending the turn while children run. Not a cited colouring failure |
| 37 | Define the scope before a parallel split | `ecc/the-longform-guide.md:176` | MISSING | nearest `AGENTS.md:50` is one task per worktree. It does not say to write the scope before the split. Draft 1 |
| 38 | One git worktree per parallel stream | `ecc/the-longform-guide.md:191` | `AGENTS.md:50` | one task, one branch, one worktree |
| 39 | Conventional commit types | `ecc/rules/common/git-workflow.md:10` | MISSING | nearest `docs/agents/WORKFLOW.md:467` asks for an honest status message, not a conventional type. Not a cited colouring failure |
| 40 | PR text from the whole branch | `ecc/rules/common/git-workflow.md:17` | MISSING | nearest `docs/agents/WORKFLOW.md:88` requires author receipts. It does not say to draft the PR from the full branch diff. Not a cited colouring failure |
| 41 | Skills are the workflow surface | `ecc/AGENTS.md:177` | `AGENTS.md:41` | load the matching skill |
| 42 | Install few always-on rules | `ecc/README.md:1253` | `AGENTS.md:7` | this file, the area file, and the card |
| 43 | Keep the window small; persist the rest | `ecc/README.md:140` | `docs/agents/WORKFLOW.md:271` | rotate, write the handoff, then clear. The memory map is `docs/agents/WORKFLOW.md:303` |
| 44 | Cap enabled MCP tools | `ecc/the-shortform-guide.md:146` | MISSING | no numeric tool cap. Shared DCC owner: `AGENTS.md:56` |
| 45 | Checkpoint and regression evals | `ecc/the-longform-guide.md:157` | `docs/agents/WORKFLOW.md:51` | regression evals before review; not a timer |
| 46 | pass@k and pass^k | `ecc/the-longform-guide.md:163` | MISSING | already in `docs/research/agent-harness-practices.md:32`. Not adopted (`docs/research/agent-harness-practices.md:8`) |
| 47 | Start from a skeleton project | `ecc/rules/common/patterns.md:5` | MISSING | nearest `docs/agents/WORKFLOW.md:262` waits for a second repeat. It does not say to clone a skeleton first. Not a cited colouring failure |
| 48 | Fix a broken build in small steps and re-check | `ecc/rules/common/performance.md:56` | `docs/agents/WORKFLOW.md:30-31` | classify, fix the cause, rerun |
| 49 | Web security checklist before every commit | `ecc/rules/common/security.md:5` | MISSING | SQL, XSS, CSRF, rate limits. Not this delivery. Action policy: `docs/agents/WORKFLOW.md:363` |
| 50 | Agent-first: the specialist works, the parent decides | `ecc/AGENTS.md:9` | `docs/agents/WORKFLOW.md:227` | specialists read (`docs/agents/WORKFLOW.md:215`); only the main agent writes and decides |

## Drafted rules

One gap. A `MISSING` row whose practice is the colouring failure. Wording is ours. Nothing here is copied into a rule file.

### 1. Define the scope before a parallel split

Row 37. Failure: fan-out was declared before a usable recipe was published, and build permission and technical dependencies were not one contract (`docs/retros/2026-10-22-tec26-colouring-codex.md:62`). Other buildings waited because the pilot recipe was not on their cards (`docs/retros/2026-10-22-tec26-colouring-claude.md:70`).

Rule:
Before a parallel split, write each stream's scope so the edits do not overlap.
Sibling cards start from that written scope, including the shared recipe and the permission to build.
A review comment or a chat status is not the scope.

## Local refinements

Narrower rules our files do not state. They are not ECC requirements, and the rows above are not `MISSING` because of them. Each one is a colouring failure. Nothing here is copied into a rule file.

### 1. Extract the authority before the first card

Row 4 is already met by reading the real inputs (`docs/agents/WORKFLOW.md:14-16`). `ecc/contexts/research.md:10` does not require a facade table. Failure: the orchestrator did not open the presentation before assigning work (`docs/retros/2026-10-22-tec26-colouring-claude.md:56`) and handed out paths instead of an extracted facade and legend (`docs/retros/2026-10-22-tec26-colouring-codex.md:57`).

Rule:
Before the first card of a visual job, open the named authority and write a table of id, material, colour, texture, and the counts taken from that source.
A card starts from that table.
A guess, a crop of a texture, or "as the etalon" is not the table.

### 2. A fix rebuilds the named delivery

Row 12 is already met by reading the result back and rerunning the affected checks (`docs/agents/WORKFLOW.md:29-32`). Failure: after the generator was fixed, the exporter still used the old textures, and the archive did not match the contract (`docs/retros/2026-10-22-tec26-colouring-codex.md:73`).

Rule:
A fix to a generator, exporter, or map is unfinished until the delivery named in the contract is rebuilt from that fix and read back.
The previous archive, a previous texture version, or a passing generator test does not carry over.

### 3. The published picture is the evidence

Row 13 is already met by recording what worked with the checks and hashes (`docs/agents/WORKFLOW.md:355-361`). `ecc/the-longform-guide.md:46` does not require comparing colour pictures. Failure: the published yellow sample did not match the recorded RGB while the material JSON was correct (`docs/retros/2026-10-22-tec26-colouring-codex.md:76`).

Rule:
For a colour or facade result, compare the picture that was actually published with the named source slide.
A correct material record, a face count, or a local audit does not replace that picture.

### 4. The latest decision is the next action

Row 14 already runs the plan that was just written (`docs/agents/WORKFLOW.md:24-26`). It does not say to drop superseded checks in a run that has already started. Failure: after the light instruction was published, the card still ran the full suite and the reviewer (`docs/retros/2026-10-22-tec26-colouring-codex.md:79`). Rules also changed under running cards, and those cards were not restarted (`docs/retros/2026-10-22-tec26-colouring-claude.md:81`).

Rule:
When a later decision narrows the job, the next action follows that decision.
A run already in progress does not finish the superseded checks and then claim the new mode.

### 5. The check's denominator is the required set

Row 8 already forbids turning a failed check into a pass (`docs/agents/WORKFLOW.md:30-32`). Failure: a 33/33 QA result allowed every ribbed surface to be replaced by a smooth one, because only the patterned faces the tool found were checked (`docs/retros/2026-10-22-tec26-colouring-codex.md:74`). A compare wrote match while an independent result was false (`docs/retros/2026-10-22-tec26-colouring-codex.md:75`).

Rule:
A count of faces the checker happened to find is not proof that every required surface was checked.
If an independent comparison says fail, the report stays fail.
Fix the checker or list the miss.

## Not adopted

- Row 7, the 80% line-coverage gate and mandatory e2e. Our bar is every measured regression check (`docs/agents/WORKFLOW.md:69`). On the colouring day the full suite was the waste (`docs/retros/2026-10-22-tec26-colouring-claude.md:62`, `docs/retros/2026-10-22-tec26-colouring-codex.md:90`).
- Row 17, instincts. They need the ECC install and a Stop hook (`ecc/skills/continuous-learning-v2/SKILL.md:3`). Accepted work already goes to cases (`docs/agents/WORKFLOW.md:355`). An automatic instinct would store the guesses this retro is about.
- Row 19, AgentShield. It is an installed scanner (`ecc/README.md:1228`), not a sentence in our rules.
- Row 23, a container or VM for untrusted work (`ecc/the-security-guide.md:128`). The guard asks and says it is not a sandbox (`docs/agents/WORKFLOW.md:392`).
- Row 25, process-group kill and heartbeat. The proposal is already in `docs/research/agent-harness-practices.md:107`. The colouring timeout did fire (`docs/retros/2026-10-22-tec26-colouring-claude.md:72`).
- Row 27, create new objects and never mutate existing ones (`ecc/rules/common/coding-style.md:5`). The colouring notes are about source files and pictures, not in-code mutation.
- Row 33, Haiku / Sonnet / Opus routing. This repo names Claude Code, Codex, and Antigravity (`AGENTS.md:3`).
- Row 35, always running independent operations in parallel (`ecc/rules/common/agents.md:39`). The colouring failure is the opposite: a split before the scope was written (draft 1).
- Row 46, pass@k as a target. Already recorded (`docs/research/agent-harness-practices.md:32`), and unbounded repeats stay out (`docs/research/agent-harness-practices.md:8`).
- Row 49, the web checklist (SQL, XSS, CSRF, rate limits) in `ecc/rules/common/security.md:5`.
- Row 28 and row 29, KISS/DRY/YAGNI and the 800-line file cap. Coding-style slogans, not a failure in these retros.
- Row 44, a numeric MCP cap. We are one trusted DCC workstation; one owner holds each DCC scene (`AGENTS.md:56`).

## Out of scope

- Language and framework packs under `ecc/rules/` other than `common/`, the 71 agents, and the 311 skills, except the three skills cited above.
- Install, marketplace, dashboard, tmux, mgrep, and hosted ECC Pro.
- Our rules that ECC does not state as a top-level practice: recitation (`docs/agents/WORKFLOW.md:173`), stop after two failures of the same cause (`docs/agents/WORKFLOW.md:32`), synthetic data (`AGENTS.md:63`), `passed=true` while a gate is open (`AGENTS.md:61`).
- Editing `AGENTS.md` or any other rule file. `docs/agents/task-intake.md` is absent here; its text is not invented from an unmerged PR.

## Content checks

Input to expected classification:

1. Input: row 4, "Read the source before writing". Expected: the equivalent cites `docs/agents/WORKFLOW.md:14-16` and is not MISSING.
2. Input: row 12, "Verify again after the change". Expected: the equivalent cites `docs/agents/WORKFLOW.md:29-32` and is not MISSING.
3. Input: row 13, "Record what worked with evidence". Expected: the equivalent cites `docs/agents/WORKFLOW.md:355-361` and is not MISSING.
4. Input: row 27, "Immutability". Expected: MISSING, unless the cited lines state code-data immutability. A ban on overwriting source files does not count.
5. Input: row 35, "Parallelise independent work". Expected: MISSING, unless the cited lines state a parallel-execution policy. One writer per worktree does not count.

```python
import re
from pathlib import Path

root = Path(r"C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_3f0a85f6")
ecc = Path(r"C:\x\ecc")
doc_path = root / "docs" / "research" / "ecc-vs-our-rules.md"
text = doc_path.read_text(encoding="utf-8")

rows = {}
for line in text.splitlines():
    m = re.match(r"\| (\d+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", line)
    if not m:
        continue
    rows[int(m.group(1))] = {
        "practice": m.group(2).strip(),
        "ours": m.group(4).strip().strip("`"),
    }

assert set(rows) == set(range(1, 51)), sorted(set(range(1, 51)) - set(rows))

def expect_range(n, practice, citation):
    row = rows[n]
    assert row["practice"] == practice, row["practice"]
    assert row["ours"] == citation, row["ours"]
    assert "MISSING" not in row["ours"]

expect_range(4, "Read the source before writing", "docs/agents/WORKFLOW.md:14-16")
expect_range(12, "Verify again after the change", "docs/agents/WORKFLOW.md:29-32")
expect_range(13, "Record what worked with evidence", "docs/agents/WORKFLOW.md:355-361")

def resolve(path):
    if path.startswith("ecc/"):
        return ecc / path[4:]
    return root / path

def cited_text(cell):
    refs = re.findall(r"([^`\s]+\.md):(\d+)(?:-(\d+))?", cell)
    if not refs:
        return None
    chunks = []
    for path, start, end in refs:
        lines = resolve(path).read_text(encoding="utf-8").splitlines()
        a = int(start)
        b = int(end) if end else a
        chunks.append("\n".join(lines[a - 1:b]))
    return "\n".join(chunks)

def row27_ok(cell):
    if cell == "MISSING":
        return True
    body = cited_text(cell)
    if not body:
        return False
    low = body.lower()
    return any(s in low for s in (
        "never mutate",
        "do not mutate",
        "immutable data",
        "new object",
        "without mutating",
    ))

def row35_ok(cell):
    if cell == "MISSING":
        return True
    body = cited_text(cell)
    if not body:
        return False
    low = body.lower()
    if "parallel" not in low:
        return False
    return ("independent" in low) or ("in parallel" in low)

assert rows[27]["practice"] == "Immutability"
assert row27_ok(rows[27]["ours"]), rows[27]["ours"]
assert rows[35]["practice"] == "Parallelise independent work"
assert row35_ok(rows[35]["ours"]), rows[35]["ours"]

def section(heading):
    marker = "## " + heading + "\n"
    start = text.find(marker)
    if start < 0:
        raise SystemExit("missing section " + heading)
    rest = text[start + len(marker):]
    nxt = rest.find("\n## ")
    return rest if nxt < 0 else rest[:nxt]

def rule_lines(body):
    found = []
    for block in re.split(r"\n### ", body)[1:]:
        if "\nRule:\n" not in block:
            raise SystemExit("draft has no Rule block")
        rule = block.split("\nRule:\n", 1)[1]
        lines = [ln for ln in rule.splitlines() if ln.strip()]
        found.append(lines)
    return found

drafts = rule_lines(section("Drafted rules")) + rule_lines(section("Local refinements"))
assert len(drafts) <= 6, len(drafts)
for lines in drafts:
    assert 1 <= len(lines) <= 3, lines

cite_re = re.compile(r"`([^`\s]+\.md):(\d+)(?:-(\d+))?`")
checked = 0
for path, start, end in cite_re.findall(text):
    file_path = resolve(path)
    if not file_path.is_file():
        raise SystemExit("missing file " + path)
    n = len(file_path.read_text(encoding="utf-8").splitlines())
    a = int(start)
    b = int(end) if end else a
    if not (1 <= a <= b <= n):
        raise SystemExit(f"out of range {path}:{start}-{end or start} has {n} lines")
    checked += 1

assert checked > 0
print(f"PASS rows={len(rows)} drafts={len(drafts)} citations={checked}")
```
