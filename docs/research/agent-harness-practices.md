# Agent Harness Practices: Cross-Vendor Evidence and Repository Integration

## Summary

Recent industry reports describe harness engineering as bounded execution with mechanical verification [1], [4].
SWE-agent's competitive-run notes, using earlier model examples, describe multi-attempt batches as much more expensive than one attempt; that cost tradeoff is historical and is not a present recommendation or a dollar threshold for this repository [5].
Codex separates sandbox limits (workspace reach, network off by default, setup secrets removed before the agent phase) from the approval policy that decides when the agent must ask [9].
For AGR-DigitalTwin, unbounded loops and automatic merges are not adopted.
Eligibility of bounded workers needs an explicit contract and owner approval (`AGENTS.md`, `docs/agents/WORKFLOW.md`).
Deterministic graders, trace receipts, and rule extensions are proposed targets under approved ticket #118.
The current CLI snapshot has no `dt evals` command.
Shared DCC resources and merge sign-off stay on the local workflow documents.

## Findings

### Multi-Session Continuity and Context Architectures
Long-horizon agent execution across discrete context windows encounters context degradation, amnesia, and premature completion declarations [1]. To structure multi-session workflows, early architectures paired an initializer agent—which configures the environment scaffold, an `init.sh` script, and a `feature_list.json` tracking granular functional assertions—with a coding agent constrained to implement one feature per session and commit progress to git [1]. In these experiments, authors noted an engineering observation that models corrupted structured JSON files less frequently than free-form Markdown, though this was reported as an operational anecdote rather than a statistically validated benchmark [1].
Video analysis addressed multi-session handoffs at 39:13 [15].

The harness-design article reports that Sonnet 4.5 exhibited "context anxiety," so that earlier harness used hard context resets and structured handoffs [2]. Opus 4.5 largely removed that behavior, and the author dropped context resets in favor of one continuous session with automatic compaction [2]. After Opus 4.6, the same article describes removing the sprint construct that Opus 4.5 had needed to decompose work [2].
The workshop video at 43:09–43:46 discusses only the Opus 4.6 generator-evaluator case: a single session was possible, and fresh sessions versus one long run stayed dependent on the use case and the evals [15].

### Evaluator Separation, Self-Evaluation Traps, and Adversarial Verification
When coding models evaluate their own outputs, authors report frequent leniency bias, rubber-stamping broken implementations, non-functional UI elements, or stubbed endpoints [2], at 39:00 [15].
Tuning a standalone evaluator agent to act as a skeptical critic proved more tractable than prompting a generator to be self-critical [2], at 39:00 [15]. In generative workflows, evaluators can leverage browser automation tools (e.g. Playwright) to test dynamic application state against multi-dimensional rubrics [2].

Workshop practitioners recommend having evaluators judge external outputs and runtime behavior rather than inspecting the generator's internal chain-of-thought or reasoning traces, noting that sharing thought streams risks rationalizing implementation flaws at 1:00:23 [15]. However, operational command logs remain useful independent proof during post-hoc debugging. Evaluator harnesses incur notable resource overhead: Anthropic reported an author's anecdotal comparison across differing scopes ($9 in 20 minutes for a non-functional solo run, compared to $200 over 6 hours in an early harness, later refined to $124.70 over 3 hours 50 minutes) [2]. For harness debugging, engineers emphasize inspecting raw execution traces at 39:38 [15].

### Evaluation Taxonomy, Grader Determinism, and Infrastructure Noise
Formal evaluation terminology distinguishes task/problem (the case), trial (attempt), grader (scoring logic), transcript/trace (messages, tool calls), outcome (final environment state), evaluation harness, agent harness, and evaluation suite [3]. Graders fall into three classes: code-based (deterministic, fast, objective), model-based (flexible, non-deterministic), and human review (calibration benchmark) [3]. Sourcing fixtures from historical production failures and bug reports provides strong operational grounding [3].

Suites separate capability evaluations (measuring hill-climbing progress with lower initial baselines) from regression evaluations (designed for high stability) [3]. Anthropic highlights the statistical distinction between pass@k (probability of at least one success across k trials) and pass^k (probability that all k trials succeed) [3]. In `AGR-DigitalTwin`, a regression suite at 100% before every merge is an approved target in `docs/prd/agent-ready-harness.md`, not a universal standard mandated by [3], and the current CLI does not run that suite. Reporting missing evidence as `not measured`, and treating a legitimate security-hook denial as an expected success only when the suite defines that case, are local recommendations consistent with those eval principles.
Empirical scores are also sensitive to infrastructure noise, compute limits, and OS discrepancies, so reproducible grading needs a controlled environment [22].

### Repository Legibility, Knowledge Scaffolding, and Autonomy Boundaries
OpenAI's harness engineering for Codex demonstrates using repository documentation as the authoritative system of record [4]. A compact, map-like `AGENTS.md` (~100 lines) providing progressive disclosure into a structured `docs/` hierarchy prevents context overload from monolithic prompt files [4]. Legibility is reinforced by ephemeral, per-worktree environments and local queryable log stacks [4].

OpenAI's pattern of automated multi-agent PR reviews and continuous auto-merging [4] does not transfer here. Merge to `main` stays on explicit user approval in `AGENTS.md` and `docs/agents/WORKFLOW.md`. An external driver runtime can write and open a pull request when card approval allows it. Unbounded loops and automatic merges are not adopted. Eligibility of bounded workers needs an explicit contract and owner approval. Domain constraints—heavy CAD/BIM assets, strict geometry validation (NPM/VPM), and shared workstation DCC environments—still call for deterministic pre-commit gates and human sign-off.

### Loop Control, Stuck Detection, and Cost Limits: Read-Code Observations
Static inspection of pinned open-source harness code reveals key operational details:
- **OpenHands repetitive-pattern detection**: Inspection of `openhands-sdk/.../stuck_detector.py` [18] reveals that `_is_stuck_context_window_error` is an unimplemented stub returning `False` (openhands/agent-sdk#282). The action-error detector emits a non-blocking warning nudge when the streak equals the threshold (`_action_error_streak == threshold`), and returns `True` for stuck status only when errors exceed the threshold (`> threshold`) [18].
  Inspected code is the implementation at the pinned commit, while the stuck-detector guide describes the documented interface and can drift from that file [6], [18].
- **SWE-Agent Budget and State Tracking**: Inspection of `sweagent/agent/models.py` [16] and `agents.py` [17] shows thread-safe tracking (`GLOBAL_STATS_LOCK`) of `per_instance_cost_limit` and `total_cost_limit`. Trajectory files (`.traj`) are updated incrementally during step loops (`save_trajectory(choose=False)`) [17], reducing data loss upon crash, though without transactional atomic fsync guarantees.
  Checks operate as post-query cost accounting rather than real-time kernel billing caps [16].
- **Aider Architect/Editor Separation**: In `aider/coders/architect_coder.py` [19], an architect model drafts an implementation plan which is delegated to an editor model, with conversation history cleared (`cur_messages = []`, `done_messages = []`) for the editor pass. The architect write-up describes the same plan-then-edit split [23]. That isolation is one product pattern; it is not evidence of a universally optimal task size.
- **Aider Deterministic Lint/Test Integration**: Aider supports configurable linting (`--lint-cmd`) and automated test execution (`--test-cmd`) [7]. Running automated tests after edits requires `--test-cmd <cmd>` combined with `--auto-test`; default auto-linting provides syntax checks but does not execute full test suites after every file edit [7].
- **Security Hooks in Quickstarts**: Anthropic's autonomous coding demo inspects shell commands via `shlex.split` allowlisting (`ALLOWED_COMMANDS`) in `security.py` [20].
  In `agent.py`, `max_iterations` is an optional configurable parameter defaulting to `None`, indicating a reference demo rather than an unchangeable hardcoded loop [21].

### Headless Interfaces, Non-Interactive Execution, and Telemetry
Codex CLI provides a non-interactive mode (`codex exec`) with workspace sandboxing (`--sandbox workspace-write`), schema enforcement (`--output-schema`), and structured JSONL event streaming (`thread.started`, `turn.completed`, `item.*`) [8]. Claude Code CLI provides headless execution via `claude -p` (or `--print`), supporting `--bare` to bypass user configs, `--allowedTools` for auto-approval, and flags `--max-turns` and `--max-budget-usd` [10], [11].
Client-side budget flags rely on approximations that can overshoot during a heavy tool turn or reset across resumed invocations [10].

### Practitioner Accounts and Operational Hazards
Unvalidated community reports illustrate hazards in unattended loops. On r/ClaudeAI, a practitioner described burning ~$6,000 overnight on an unattended `/loop` checking pull requests, recounting that prompt caching expired during 30-minute intervals and re-cached large contexts while billing dashboards lagged [12]; this is the author's unvalidated personal account rather than a verified billing fact. On r/LocalLLaMA, a developer reported frustration with local models becoming trapped in verbose build and terminal outputs, resulting in brittle tool-calling loops [13]. On r/ChatGPTCoding, a developer proposed a multi-agent orchestration architecture using separate git branches and reviewer agents [14]; this remains an architectural proposal rather than a deployed, measured production system.

### Recommendation for This Board
Recommendation for this board: one independently verifiable outcome, checkable acceptance, input versions, expected files, explicit non-goals and verification command; split when review burden/context exceeds one session; no arbitrary LOC threshold. Express prerequisites as dependency edges; sequential required checks before dependent writes, parallelize only disjoint read-only work inside configured 3-agent/DCC caps. These are recommendations, not empirical measured improvements. They refine approved intake in `docs/prd/agent-ready-harness.md`; they are not a claim that the PRD already uses this wording.

## Practice Mapping and Repository Status

| Practice / Topic | Cross-Vendor Evidence | Local Status | Local Reference | Operational Rationale |
|---|---|---|---|---|
| Review Rounds by Risk | Codex review patterns [4], Anthropic eval rigor [3] | Already approved | `docs/agents/REVIEW_CHECKLIST.md` | 2 rounds for code/hooks (round 3 only on P1); 1 round for docs; max 3 ceiling; human merge command. |
| Task Sizing & Bounds | Aider plan/edit split is one product pattern [19] | Recommendation refining intake | `docs/prd/agent-ready-harness.md` (§Process) | One verifiable outcome and checkable acceptance; no universal LOC cap. See the recommendation above. |
| Trace Receipts & Redaction | SWE-agent `.traj` updates [17] | Proposed increment | `src/dt_ai/core/run_record.py`, #124 | Existing record has hashes, atomic JSON, and locks. Exact-head argv/cwd/redaction envelope is proposed. |
| Guardrails & Escalation | Anthropic security hook [20], Codex sandboxing [8] | Proposed extension; guards not fully validated | `tools/git-hooks/pipeline_gate.py`, #127, #128, `docs/PROJECT_STATE.md` | `never` / `ask` stay requirements in `AGENTS.md` and `docs/agents/WORKFLOW.md`. Docs alone do not prove the guards. Stop on 2 of the same cause; escalate on 3 item errors. |
| Budget & Repetitive-Pattern Limits | SWE-agent cost limits [16], OpenHands repetitive-pattern detection [18] | Later proposal | Post-v1 scope, Task 2 | Scheduler-wide wall-clock and attempt ledgers; terminate owned subprocess trees only; never kill shared DCC apps. |
| Unattended / Overnight Runs | Reddit unattended loop risks [12], Claude CLI flags [10] | Unbounded loops and automatic merges: do not adopt | `AGENTS.md`, `docs/agents/WORKFLOW.md` | External runtime may write and open a PR under card approval. Bounded workers need an explicit contract and owner approval. |

*Note: Ticket status as of 2026-10-15. Absence of `dt evals` was verified in the checkout CLI (`src/dt_ai/cli/`); uncommitted sibling branches were not inspected. Ticket #129 inventory is not duplicated.*

## How It Applies to This Repository

Approved targets and proposed extensions, not implementation claims. The current snapshot CLI lacks evals: `src/dt_ai/cli/` has no `dt evals` command. The approved #118 PRD is `docs/prd/agent-ready-harness.md`.

1. **Deterministic Evals and CLI Runner (#122, #123, #125, #132, #133)**:
   - The runner should implement deterministic code graders and should not add LLM judges, in line with the code-based grader class [3].
   - Propose graders for procedural compliance (#123) and PR checklists (#125) that parse local transcripts, grade missing evidence as `not measured`, and allow a legitimate hook denial only when the suite defines that case.
   - Propose synthetic fixtures from historical incidents (#76 merge without command, #117 checker blind spots) as regression baselines once the runner exists.
2. **Trace Receipts and RunRecords (#124)**:
   - Read-code of `src/dt_ai/core/run_record.py` shows the current ledger already has file SHA-256 hashes, atomic JSON writes, and resource locks.
   - The exact-head argv/cwd/redaction envelope is an incremental proposal. Today's record is not a published receipt of git SHA, uncommitted diff identity, redacted argv, cwd, duration, and log pointers together.
   - Incremental `.traj` writes in SWE-agent [17] are a design analogy for that proposal.
3. **Guardrails, Permissions, and Failure Escalation (#127, #128, #144)**:
   - Retain the approved requirement to stop after 2 failures with the same cause and to escalate after 3 failures of an item, with a structured stop record (`stopped=True`, `stop_reason`) before retry.
   - Propose extending PreToolUse checks in `tools/git-hooks/pipeline_gate.py` (#127) after verification. The quickstart allowlist [20] is a reference pattern only.
   - Retain the approved requirement that `never` classes deny automatically and that `ask` classes (`gh pr merge`, `gh repo`, destructive DCC operations) wait for explicit user confirmation in `AGENTS.md` and `docs/agents/WORKFLOW.md`.
   - `docs/PROJECT_STATE.md` still lists guard hooks that are not green (Codex and Antigravity guard hooks; desktop and interactive CLI hooks). Current guards are not fully validated, and the documents alone do not guarantee them.
4. **Harness Inventory and Progressive Disclosure (#129, #130)**:
   - Retain the approved requirement that `AGENTS.md` remain a compact entry point into `docs/domain/`, `docs/decisions.md`, and `docs/cases.md`, consistent with a short repository map [4].
   - Propose that the harness inventory (#129) judge components against recorded failures, and retire scaffolding only after that check.
   - Propose that issue intake (#130) check contract completeness before `ready-for-agent`.
5. **Operational Concurrency and Ownership Scopes**:
   - `docs/agents/KANBAN.md` permits up to 3 concurrent card workers across disjoint DCC applications, while `docs/agents/WORKFLOW.md` keeps one writing agent per worktree and read-only subagents. That scope split is noted for owner clarification.
   - v1 excludes a multi-agent orchestrator. An external driver can write and open a pull request under card approval. Unbounded loops and automatic merges are not adopted.

## Proposed Next Tasks

### Task 1: Standardized Verification Receipts and Redacted Traces in RunRecords and Handover
- **Scope**: Extend `src/dt_ai/core/run_record.py` and the `/handover` generator with a standardized receipt. Read-code shows the module already stores SHA-256 hashes, writes the ledger with atomic JSON, and records owner plus PID in `.<resource>.orchestration.lock`. The incremental envelope should add exact git HEAD and a working-tree identity, because a git SHA alone is insufficient when a later uncommitted diff changes the code under test. Command, cwd, duration, exit code, and raw log paths stay in a private raw log under controlled retention. Published output is redacted identifiers and hashes, not full local paths or secrets. A receipt is evidence. Graders reuse only hash-matching evidence where the workflow explicitly permits; reviewer-required reruns remain. The receipt does not replace the mandatory verifier.
- **Acceptance**: A pytest fixture fails when a subsequent code edit invalidates a prior test while the git SHA is unchanged, when the command exits non-zero, and when evidence is missing or truncated. Those cases never pass. A passing case shows redacted published hashes that match the retained private log.
- **Value / Effort**: Value M / Effort M. Extends approved scope (#124 trace block and #122 eval runner).

### Task 2: Deterministic Budget, Time, and Process Tree Watchdog for Batch Operations
- **Scope**: Propose an external non-LLM supervisor. The budget is scheduler-wide and aggregate, not a separate cap inside each worker. Token and cost figures are estimates; true quota is recorded as unknown when the meter is absent. Concurrency and remaining budget have no silent fallback. Heartbeats and PR polling are deterministic, not an LLM call per tick. USD and quota caps are configurable; the numbers are undecided. On child crash or restart, task and attempt keys are idempotent, leases expire, and ownership is checked. Resume only verified artifacts, and do not open a duplicate PR or submission. Cleanup covers the owned child tree only (Windows `taskkill /PID <child> /T /F` or a POSIX tree kill), never an arbitrary shared session or a shared DCC app. On timeout, write an emergency evidence artifact without promising clean state recovery.
- **Acceptance**: A simulated stuck child tree ends within the timeout, shared applications stay up, and the artifact records timeout. A second worker cannot spend budget the scheduler has already exhausted. A restart of the same attempt key does not submit a second PR.
- **Value / Effort**: Value L / Effort M. Genuinely new post-v1 external orchestrator scope (not approved #128).

### Task 3: Normalized Failure Fingerprinting and Loop-Break Policy in Pipeline Gate
- **Scope**: Extend `tools/git-hooks/pipeline_gate.py` and job state to preserve stop2 and max3: halt after 2 failures with the same cause, and escalate after 3 failures of an item. A normalized same-cause signature can false-positive when inputs change under an identical command; a changing-input retry stays valid. Counts persist across restarts. The current limit of three `agy` calls is a separate runtime limit. Local review risk (2 rounds for code/hooks, 1 round for docs, in `docs/agents/REVIEW_CHECKLIST.md`) is independent of stop2/max3. On the limit, write `stopped=True` and `stop_reason`, and require fixture replay plus an approved reset. Do not replace these limits with OpenHands numeric defaults.
- **Acceptance**: Identical consecutive failures halt at the 2nd and block an unapproved re-run. A changed-input retry is allowed. Counts survive a restart. An approved reset record is what unblocks the gate.
- **Value / Effort**: Value M / Effort S. Extends approved scope (#128 failure limits and #144 state guards).

### Task 4: Workstation Resource Leasing for Configured DCC Endpoints and Export Targets
- **Scope**: Build from the existing lock in `src/dt_ai/core/run_record.py`. The filename is `.<resource>.orchestration.lock`, and the payload stores PID and owner. That mechanism is not a universal lease over every DCC endpoint. Propose extending it to mapped resources (configured MCP endpoints, active DCC scenes, export directories, and token or license identifiers) and record process birth so PID reuse cannot inherit a live owner's lock. Stale locks need a liveness check and owner confirmation. Unconditional lock deletion stays prohibited.
- **Acceptance**: Two processes claiming the same mapped resource fail with `OwnershipConflict`. A recycled PID with a different process birth does not pass the liveness check. An inactive lock still waits for manual confirmation before reclamation.
- **Value / Effort**: Value M / Effort M. Genuinely new proposal for post-v1 multi-agent coordination.

### Task 5: Minimal Cross-Provider Headless Event Adapter Contract
- **Scope**: Specify an intermediate JSON schema for Claude Code transcript blocks (`tool_use`, `user` records) and Codex JSONL (`thread.started`, `turn.completed`, `item.*` [8]). Provider-specific fields stay in a metadata map. Unknown or missing values are explicit. Adapters must never turn unsupported telemetry into a pass. The schema records its own version and the CLI version. Antigravity's transcript format was not inspected. The existing v1 target stays deterministic and Claude-only, with no LLM graders [3].
- **Acceptance**: Fixtures keep provider-specific fields, mark unknowns explicitly, and fail the grade when required telemetry is unsupported. They do not collapse both providers into identical event bodies.
- **Value / Effort**: Value M / Effort L. Genuinely new proposal for post-v1 multi-provider rollout.

### Task 6: Clarify Multi-Card Concurrency and Worktree Ownership Scopes
- **Scope**: Harmonize documentation between `docs/agents/KANBAN.md` (permitting up to 3 concurrent card workers across distinct DCC applications) and `docs/agents/WORKFLOW.md` (restricting execution to one writing agent per worktree with read-only subagents). Delineate worktree-level single-writer isolation from workstation-level DCC resource sharing, submitting the proposed clarification for future owner review without altering approved decisions. Acceptance test: documentation review confirms consistent terminology across KANBAN, WORKFLOW, and ROLES, with zero changes to existing user decisions.
- **Value / Effort**: Value S / Effort S. Genuinely new documentation task.

## Open Questions for the User

1. **Deterministic Ceilings for Batch Operations**: What hard limits should batch runs use (outer wall-clock minutes per stage, maximum attempts, turn limits per agent)? USD and quota caps are configurable and the numbers are undecided; which quotas should the scheduler aggregate?
2. **Eligible Batch Task Classes**: Which task categories, if any, may run as bounded workers under an explicit contract and owner approval, and which stay interactive?
3. **Transcript Retention and Sanitization**: What retention period should apply to private raw logs, and which redaction patterns should published hashes follow for CAD paths, architectural dimensions, and environment variables?
4. **Cross-Provider Rollout Priority**: After Wave 2 Claude Code evals, should the next adapter be Codex headless JSONL [8]? Antigravity's transcript format was not inspected, so it is not ordered here.
5. **Workstation Concurrency Boundaries**: How should mapped workstation locks coordinate when several Kanban cards run on distinct DCC applications?

## Methodology and Evidence Limitations

- **Worktree and Execution Boundaries**: Analysis used worktree `t_7faf3d15` at HEAD `a1052e3d3a3c5ef096028fb68982e1337da4eba4`, with baseline date 2026-10-15. The research driver performed read-only web retrievals, GitHub API queries for pinned files, git fetch origin, and authentication checks. The research agent session (`agy`) executed no git commands, network mutations, or DCC calls. No remote writes were performed during research; publication and commits are handled later by the driver.
- **Pinned Source Code Inspection**: Static analysis inspected SWE-agent `models.py` [16] and `agents.py` [17].
  It also inspected OpenHands `stuck_detector.py` [18] and Aider `architect_coder.py` [19].
  Anthropic quickstart files were `security.py` [20] and `agent.py` [21]. External harness suites were not executed. No runtime quota or model benchmark was run, and no runtime output was fabricated.
- **Test Execution**: This research session did not run the repository test suite. The driver records the test result in the pull request.
- **Video Transcript Analysis**: Selected transcript passages were read successfully from 2,222 segments (1:15:26 total duration) [15]. The full video was not watched, and the workshop demo was not executed.
- **Retrieval Failures and Recovery**: `https://aider.chat/docs/usage/architect.html` returned HTTP 404, and web extraction of the architect blog failed. Canonical curl of `https://aider.chat/2024/09/26/architect.html` returned HTTP 200 and recovered that page [23]. A Reddit plugin post timed out and raw JSON curl returned HTTP 403, so that post was excluded. Those misses did not block the rest of the read.
- **Code vs. Documentation Divergence**: Inspected code is authoritative for the concrete implementation at the pinned commit. Documentation is the documented interface and can drift, including the OpenHands context-window stub [6], [18].
- **Epistemic Classification**: Claims are labeled in place as read-code inspection, vendor engineering write-ups, community accounts, the workshop transcript, or local repository files. Each numbered source is cited on the claim it supports.

## Sources

[1] https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
[2] https://www.anthropic.com/engineering/harness-design-long-running-apps
[3] https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
[4] https://openai.com/index/harness-engineering
[5] https://swe-agent.com/latest/usage/competitive_runs
[6] https://docs.openhands.dev/sdk/guides/agent-stuck-detector
[7] https://aider.chat/docs/usage/lint-test.html
[8] https://learn.chatgpt.com/docs/non-interactive-mode
[9] https://learn.chatgpt.com/docs/agent-approvals-security
[10] https://code.claude.com/docs/en/cli-reference
[11] https://code.claude.com/docs/en/headless
[12] https://www.reddit.com/r/ClaudeAI/comments/1t11mmy/i_accidentally_burned_6000_of_claude_usage
[13] https://www.reddit.com/r/LocalLLaMA/comments/1sxqa2c/im_done_with_using_local_llms_for_coding
[14] https://reddit.com/r/ChatGPTCoding/comments/1mnay5h/ai_orchestrator
[15] https://www.youtube.com/watch?v=mR-WAvEPRwE
[16] https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py
[17] https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py
[18] https://github.com/OpenHands/software-agent-sdk/blob/8efff8d3cf1a5a3fcf7ce5e3b97c7f00684d9547/openhands-sdk/openhands/sdk/conversation/stuck_detector.py
[19] https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/architect_coder.py
[20] https://github.com/anthropics/claude-quickstarts/blob/9ec32b91df50b0d4906cae64b13c6298055ff40d/autonomous-coding/security.py
[21] https://github.com/anthropics/claude-quickstarts/blob/9ec32b91df50b0d4906cae64b13c6298055ff40d/autonomous-coding/agent.py
[22] https://www.anthropic.com/engineering/infrastructure-noise
[23] https://aider.chat/2024/09/26/architect.html
