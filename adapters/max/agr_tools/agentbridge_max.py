"""new-case: AGR Tools 1.0 (#1024) agent request (K4) / agent accept gate (K4), 3ds Max side. Stub of branch 0; owned by branch U (improve/issue-1024-agent-bridge).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `agent_request` (agent.request), `agent_accept` (agent.accept);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (agentbridge_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.
"""
