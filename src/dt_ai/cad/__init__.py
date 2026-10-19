"""CAD plan proxies and straight-entity serialization.

Pattern: none — straight-entity CAD serialization proxy (REVIEW_CHECKLIST Q1: new-case).
This is not an approved architectural pattern and provides no architectural or delivery
certification. The supported entity subset and boundary are defined in plan_dxf.
"""

from dt_ai.cad.plan_dxf import (
    IDENTITY,
    TOL_MM,
    PlanTransform,
    audit_plan_dxf,
    build_plan_features,
    census,
    compare_plan,
    read_plan_dxf,
    spec_from_mapping,
    write_plan_dxf,
)

__all__ = [
    "IDENTITY",
    "TOL_MM",
    "PlanTransform",
    "audit_plan_dxf",
    "build_plan_features",
    "census",
    "compare_plan",
    "read_plan_dxf",
    "spec_from_mapping",
    "write_plan_dxf",
]
