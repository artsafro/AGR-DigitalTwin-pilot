"""The parts list (`parts.json`): the model taken apart before any build, shown at gate 1 [D111, D124, D125].

One entry per part: where it comes from, what it is, which album legend item it matches, which operation of the
menu builds it [D108], its triangle budget, and one decision per joint with a neighbour - weld into one mesh or
embed 10-20 mm - with the reason and the extra edges welding would insert [D124]. The agent proposes the list, the
user confirms it (`gate1`); `status="confirmed"` without that approval does not validate.
Pattern: `primitive-first` (docs/domain/patterns/primitive-first.md), grilling log Q8, Q12, Q19, Q29a, Q30.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dt_ai.core.provenance import Approval, Name, SourceRef

Embed = Annotated[float, Field(ge=0.010, le=0.020, allow_inf_nan=False, description="embed depth, metres [D115]")]

# Part classes: building parts of primitive-first section 0, plus the types D109 marks as NPM opacity candidates.
PartClass = Literal["wall", "slab", "parapet", "band", "pilaster", "frame", "glazing", "balcony", "superstructure",
                    "decor", "window", "door", "railing", "rod_ladder", "grille", "ac_screen", "fence", "other"]
# The menu of the operation library [D108] (Q8 table).
Operation = Literal["keep", "primitive", "contour_rebuild", "from_face", "library_replace", "detail_per_profile",
                    "to_texture"]
BuildAs = Literal["box", "plane", "frame", "shell", "profile_extrude", "instance"]
SourceTier = Literal["A", "B", "C"]  # A Revit + album; B structured FBX / SKP + album; C mesh soup + album [Q29a]
SourceKind = Literal["object", "material_id", "layer", "component", "revit_element", "region"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


class PartSource(Strict):
    """Where a part is read from in the source file."""
    kind: SourceKind
    reference: str = Field(min_length=1, description="object / layer / component name, material id or Revit id")


class TriangleBudget(Strict):
    npm: int = Field(ge=0)
    vpm: int = Field(ge=0)


class PartEntry(Strict):
    id: Name
    part_class: PartClass
    sources: list[PartSource] = Field(min_length=1)
    legend_item: str | None = Field(default=None, min_length=1, description="album legend item; null = not found, ask")
    operation: Operation
    build_as: BuildAs | None = Field(default=None, description="primitive only")
    library_ref: str | None = Field(default=None, min_length=1, description="library_replace only")
    mesh: str | None = Field(default=None, min_length=1, description="relative path of the part's mesh")
    triangle_budget: TriangleBudget

    @model_validator(mode="after")
    def operation_fields(self):
        if (self.operation == "primitive") != (self.build_as is not None):
            raise ValueError(f"{self.id}: build_as is required by the primitive operation and only by it")
        if (self.operation == "library_replace") != (self.library_ref is not None):
            raise ValueError(f"{self.id}: library_ref is required by library_replace and only by it")
        if self.operation == "to_texture" and (self.triangle_budget.npm or self.triangle_budget.vpm):
            raise ValueError(f"{self.id}: a part turned into texture has no triangles")
        if self.mesh is not None and (self.mesh.startswith(("/", "\\")) or ".." in self.mesh.replace("\\", "/").split("/")):
            raise ValueError(f"{self.id}: mesh must be a relative path inside the job")
        return self


class Joint(Strict):
    """One decision per pair of neighbouring parts: weld (one mesh) or embed [D124]."""
    parts: list[Name] = Field(min_length=2, max_length=2)
    decision: Literal["weld", "embed"]
    reason: str = Field(min_length=1)
    extra_edges: int = Field(ge=0, description="edges that welding would insert into either mesh to match the other")
    embed_depth_m: Embed | None = None

    @model_validator(mode="after")
    def decision_fields(self):
        if self.parts[0] == self.parts[1]:
            raise ValueError("a joint joins two different parts")
        if (self.decision == "embed") != (self.embed_depth_m is not None):
            raise ValueError(f"{self.parts}: embed_depth_m (0.010-0.020 m) is required by embed and only by it")
        return self


class Question(Strict):
    audience: Literal["user", "architect"]
    text: str = Field(min_length=1)
    answer: str | None = Field(default=None, min_length=1)


class PartsList(Strict):
    schema_version: Literal["1.0.0"] = "1.0.0"
    synthetic: bool
    object_id: Name
    source_tier: SourceTier
    sources: list[SourceRef] = Field(min_length=1)
    triangle_budget: TriangleBudget = Field(description="whole delivery; the parts' budgets must fit")
    parts: list[PartEntry] = Field(min_length=1)
    joints: list[Joint] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    status: Literal["draft", "confirmed"] = "draft"
    gate1: Approval | None = None

    @model_validator(mode="after")
    def consistent(self):
        ids = [p.id for p in self.parts]
        if len(set(ids)) != len(ids):
            raise ValueError("part ids must be unique")
        pairs = set()
        for j in self.joints:
            missing = [p for p in j.parts if p not in ids]
            if missing:
                raise ValueError(f"joint {j.parts}: unknown part {missing}")
            pair = frozenset(j.parts)
            if pair in pairs:
                raise ValueError(f"joint {j.parts}: decided twice")
            pairs.add(pair)
        for profile in ("npm", "vpm"):
            total = sum(getattr(p.triangle_budget, profile) for p in self.parts)
            if total > getattr(self.triangle_budget, profile):
                raise ValueError(f"{profile}: part budgets add up to {total}, over the total "
                                 f"{getattr(self.triangle_budget, profile)}")
        if self.status == "confirmed" and self.gate1 is None:
            raise ValueError("confirmed needs the gate 1 approval of the user")
        if self.gate1 and self.synthetic and self.gate1.scope != "synthetic_fixture":
            raise ValueError("a synthetic parts list cannot carry a project approval")
        return self
