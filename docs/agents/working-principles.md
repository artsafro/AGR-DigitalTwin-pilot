# Working principles (four rules against the usual LLM-agent failures)

Adapted from the public "Karpathy-inspired guidelines" (github.com/forrestchang/andrej-karpathy-skills, four principles)
to this repo. Each rule names the failure it prevents here. They add to `docs/agents/task-intake.md` and the
permission matrix, never override them.

1. **Think before building.** State your assumptions in one list before the first edit or DCC call. Where the task or
   sources allow two readings, name both and ask (task intake); never pick one silently. If a simpler way exists, say
   so and push back. Failure it prevents: TEC26 colouring rebuilt geometry and guessed a 0.6 m joint module from a
   sample texture because nobody stated the assumption.
2. **Simplest thing that meets the ask.** Deliver what was asked and nothing speculative: no extra checks, evidence
   packs, abstractions or options the task did not request. A colour-only production task runs in light mode (build,
   compare picture, publish). If 200 lines could be 50, rewrite. Failure it prevents: full test suites and review rounds
   on a one-hour colouring job.
3. **Surgical changes.** Touch only the files and objects the task needs; match the existing style; do not "improve"
   neighbouring code, docs, scenes or decisions. Remove only what your own change made unused; report other dead code
   instead of deleting it. Every changed line traces to the task. Failure it prevents: unrelated edits that conflict
   with parallel cards and reopen reviews.
4. **Goal-driven: define done, then loop until verified.** Turn the task into checkable criteria before work (numbers,
   a test, a picture next to the reference), write a short plan `step -> verify: check`, and stop only when every check
   is met by a real run, not by a claim. Failure it prevents: "done" reports whose rib counts or colours never matched
   the reference sheet.

These work when diffs get smaller, rework rounds fewer, and questions come before the build instead of after a wrong
render.

## Never bend geometry to pass a validator

Applies to rule 4: a validator is evidence, not the goal. Never alter the geometry only to make a validator or a
check pass: do not cut a continuous element into pieces, add a stand-off, move parts, delete or shrink faces.
When a modelling rule and a validator disagree (a rule-required embed counted as self-intersection, a continuous
strip flagged by a cross-view check), stop and ask the user: name the rule, the validator stage and its numbers, and
the entry in `docs/domain/conflicts.md` (add one if none exists); keep the rule-correct geometry until the user
decides, and report the stage as `review: conflicts #<n>`. Failure it prevents: job elv-tc-vpm v001 failed V004 on
the 10 mm embeds, the agent chose a 6 mm floating stand-off and cut cover strip P44 into 34 pieces to keep V004 and
the cross-view check clean; the user found both after "done" (now [D199], conflicts #44, `.agents/skills/validate-delivery/SKILL.md`
gates G1-G2).
