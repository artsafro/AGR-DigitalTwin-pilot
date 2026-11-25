# 3ds Max adapter

[AGR Tools](agr_tools/README.md) is the existing 3ds Max panel. It is frozen at 1.1.x and off the active production trail: no new features and no rollback to 0.9 ([D393](../../docs/decisions.md)). The code remains in place; see the [changelog](agr_tools/CHANGELOG.md) for the retained capabilities and release status.

For production, start from the [scenario index](../../docs/scenarios/scenarios.json) and follow the route for the task, not the frozen panel documentation. For authorized Max work, start read-only, leave the user's working scene untouched, and read back any versioned export.
