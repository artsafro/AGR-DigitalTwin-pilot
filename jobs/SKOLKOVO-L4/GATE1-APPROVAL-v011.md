# Revised Skolkovo Gate 1 — actual approval, v011 execution

Artem's task comment at **2026-10-21 16:58** relays «принимаю» and explicitly
confirms revised PartsList SHA256
`fca5b23b4e4939ad44f01abde68d8b510b0daad18c5e7bf3072a22e05fcd0d2a`
(`GATE1-PROPOSAL-v010.md`): source-profile recipe of five primary masts,
bidirectional exterior surface deviation <=0.002 m, 49 parts / 147000 triangle
allocation / 291 candidate-conditioned joints. Execution may continue.

The immutable proposed JSON and embedded recipe remain byte-identical. The
separate `tmp/skolkovo-l4-v011/parts-confirmed-v011.json` execution copy changes
**only** `status`, `gate1`, and question0's answer. No source memberships, budgets,
material bindings, joints or embedded design are changed. Approval regression
rejects changed design and wrong actor/date/scope/hash. The recipe's embedded
`approval.exact_hash_gate1: null` is historical proposal data, not an unresolved
permission: this approval is attached to the enclosing, exact proposal hash.

This is permission to execute the approved plan, **not** model acceptance,
reconstruction certification, budget attainment, a whole-building kernel pass,
export/readback, visual approval or final SINTEZ. All failed v009 candidates
remain rejected; build starts from the original hash-pinned source buffers.
