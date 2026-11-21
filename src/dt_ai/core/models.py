from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from dt_ai.core.provenance import Approval, Contract, Finite, Hash, Name, SourceRef

Byte = Annotated[int, Field(ge=0, le=255, strict=True)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class Material(Contract):
    id: Name
    label: str = Field(min_length=1)
    status: Literal["proposed", "approved", "conflict"]
    source: SourceRef
    approval: Approval | None = None
    diffuse_rgb: list[Byte] = Field(min_length=3, max_length=3)
    emissive: Byte
    roughness: Byte
    metallic: Byte
    pattern_delta: Byte = 12
    normal_opengl_rgb: list[Byte] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def approved_has_evidence(self):
        if self.status == "approved" and self.approval is None:
            raise ValueError("approved requires an explicit decision")
        if self.approval and self.source.kind == "synthetic" and self.approval.scope != "synthetic_fixture":
            raise ValueError("Synthetic material cannot carry project approval")
        return self


class MaterialRegistry(Contract):
    materials: list[Material] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({m.id for m in self.materials}) != len(self.materials):
            raise ValueError("Duplicate material IDs")
        return self


class WindowType(Contract):
    id: Name
    width_m: Positive
    height_m: Positive
    source: SourceRef
    status: Literal["proposed", "approved", "conflict"]
    approval: Approval | None = None

    @model_validator(mode="after")
    def approved_has_evidence(self):
        if self.status == "approved" and not self.approval:
            raise ValueError("Window approval is missing")
        return self


class HeightSource(Contract):
    """File plus sheet/cell, level or drawing handle; never infer a vertical CRS from MSK-77."""
    file: str = Field(min_length=1, pattern=r"\S")
    locator: str = Field(min_length=1, pattern=r"\S")


class Placement(Contract):
    model_config = ConfigDict(json_schema_extra={"allOf": [{
        "if": {"required": ["project_zero_m"], "properties": {"project_zero_m": {"type": "number"}}},
        "then": {"required": ["height_system", "height_source"], "properties": {
            "height_system": {"enum": ["BSV-77", "Baltic 1977", "MSK local", "unknown"]},
            "height_source": {"type": "object"}}}}]})
    coordinate_system: Literal["SYNTHETIC_LOCAL", "MSK-77"]
    project_zero_m: Annotated[float, Field(strict=True, allow_inf_nan=False)] | None = None
    height_system: Literal["BSV-77", "Baltic 1977", "MSK local", "unknown"] | None = None
    height_source: HeightSource | None = None
    project_zero_fbx_z_m: Annotated[float, Field(strict=True, allow_inf_nan=False)] | None = None
    project_zero_fbx_source: HeightSource | None = None
    ground_mark_m: Annotated[float, Field(strict=True, allow_inf_nan=False)] | None = None
    ground_mark_source: HeightSource | None = None

    def heights(self, model_max_z_m: float) -> dict[str, float]:
        """D279: GeoJSON h_relief is project zero, not the terrain insertion mark."""
        from dt_ai.core.heights import height_values
        return height_values(self.project_zero_m, self.project_zero_fbx_z_m, model_max_z_m)
    insertion_xy: list[Finite] | None = Field(default=None, min_length=2, max_length=2)
    source: SourceRef
    status: Literal["unknown", "proposed", "approved"]
    approval: Approval | None = None

    @model_validator(mode="after")
    def confirmed_coordinates(self):
        if self.project_zero_m is not None and (self.height_system is None or self.height_source is None):
            raise ValueError("project_zero_m requires height_system and height_source; migrate the named placement job")
        for value, source in ((self.project_zero_fbx_z_m, self.project_zero_fbx_source),
                              (self.ground_mark_m, self.ground_mark_source)):
            if (value is None) != (source is None):
                raise ValueError("height value and its source must be supplied together")
        if self.status == "approved" and (self.project_zero_m is None or self.insertion_xy is None or not self.approval):
            raise ValueError("Approved placement requires coordinates, elevation, and approval")
        return self


class ProjectManifest(Contract):
    project_id: Name
    synthetic: bool
    address_token: Name
    standards_sha256: Hash
    profile_versions: dict[Literal["NPM", "VPM"], str]
    inputs: dict[str, Hash] = Field(min_length=1)
    placement: Placement

    @model_validator(mode="after")
    def profiles_and_placement(self):
        if set(self.profile_versions) != {"NPM", "VPM"}:
            raise ValueError("Both profile versions required")
        if not self.synthetic and self.placement.coordinate_system == "SYNTHETIC_LOCAL":
            raise ValueError("Real project cannot use synthetic coordinates")
        return self


class Surface(Contract):
    id: Name
    material_id: Name
    vertices: list[list[Finite]] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def xyz(self):
        if any(len(v) != 3 for v in self.vertices):
            raise ValueError("Expected XYZ vertices")
        return self


class MasterBuilding(Contract):
    synthetic: bool
    source: SourceRef
    surfaces: list[Surface] = Field(min_length=1)

    @model_validator(mode="after")
    def stable_ids(self):
        if len({s.id for s in self.surfaces}) != len(self.surfaces):
            raise ValueError("Duplicate surface IDs")
        if self.synthetic != (self.source.kind == "synthetic"):
            raise ValueError("Master/source synthetic status mismatch")
        return self


class BuildJob(Contract):
    project: ProjectManifest
    registry: MaterialRegistry
    master: MasterBuilding

    @model_validator(mode="after")
    def references(self):
        known = {m.id for m in self.registry.materials}
        used = {s.material_id for s in self.master.surfaces}
        if known != used:
            raise ValueError("Each material must be used; every surface must reference a known material")
        if self.project.synthetic != self.master.synthetic:
            raise ValueError("Project/master synthetic mismatch")
        if not self.project.synthetic and any(m.source.kind == "synthetic" for m in self.registry.materials):
            raise ValueError("Real project cannot use synthetic provenance")
        return self


class Finding(Contract):
    id: str
    status: Literal["pass", "fail", "review", "not_applicable", "not_run"]
    source_pdf_pages: list[int] = Field(min_length=1)
    observed: str
    expected: str
    evidence: str


class ValidationReport(Contract):
    synthetic: bool
    source_sha256: Hash
    checks: list[Finding]
    development_checks_passed: bool
    # This first slice deliberately cannot certify customer delivery.
    passed: Literal[False] = False
    limitations: list[str] = Field(min_length=1)


SCHEMAS = {c.__name__: c for c in [ProjectManifest, MaterialRegistry, WindowType,
                                   Placement, BuildJob, ValidationReport, MasterBuilding]}


from dt_ai.core.adapter_report import AdapterReport
SCHEMAS["AdapterReport"] = AdapterReport

from dt_ai.spec.model import Spec
SCHEMAS["Spec"] = Spec

from dt_ai.intake.model import SourcesFile, SpecDraft
SCHEMAS["IntakeSources"] = SourcesFile
SCHEMAS["IntakeSpecDraft"] = SpecDraft


from dt_ai.parts.model import PartsList
SCHEMAS["PartsList"] = PartsList
