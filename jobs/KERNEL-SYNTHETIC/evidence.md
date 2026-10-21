# Synthetic kernel capability walk (#351)

All sources in this walk are SYNTHETIC tests, not real building geometry.

Executed on implementation base `eed5074` plus issue-351 changes:
`uv run pytest -q -p no:cacheprovider -o addopts='' --basetemp=C:/x/t_8e0361be-kernel tests/ops tests/contracts/test_parts_list.py`
-> **220 passed in 165.61 s**.

This exercises actual numpy kernel invariants/operations and the PartsList contract.
It is capability evidence only: no job-specific confirmed parts list, exported
model/readback, budgets, review-tool user decision or complete SINTEZ run exists.
No visual approval is inferred from pytest.
