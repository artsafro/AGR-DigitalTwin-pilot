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
