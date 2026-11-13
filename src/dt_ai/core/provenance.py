"""Shared provenance contracts; independent of parts, spec and intake models."""
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Finite = Annotated[float, Field(allow_inf_nan=False)]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Name = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$", max_length=120)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)
    schema_version: Literal["1.0.0"] = "1.0.0"


# A `drawing` reference names a .dwg/.dxf file (any case), optionally followed by a note [#1206].
# Cross-field kind rules stay model-only, like the pdf rule: the committed schema carries the
# structural contract only (tests/parts/test_schema_model_boundary.py; fbx reader's schema subset).
DRAWING_REFERENCE = r"\.([dD][wW][gG]|[dD][xX][fF])([^A-Za-z0-9]|$)"


class SourceRef(Contract):
    # `drawing` = DWG/DXF source: optional `sheet` (layout / sheet name), never `page` [#1206].
    kind: Literal["synthetic", "pdf", "model", "user", "drawing"]
    reference: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1, le=100000)
    sha256: Hash | None = None
    region: list[Finite] | None = Field(default=None, min_length=4, max_length=4)
    sheet: str | None = Field(default=None, min_length=1, max_length=255, pattern=r"\S")

    @model_validator(mode="after")
    def pdf_has_page(self):
        if self.kind == "pdf" and (self.page is None or self.sha256 is None):
            raise ValueError("PDF provenance requires page and sha256")
        if self.kind == "drawing":
            if self.page is not None:
                raise ValueError("drawing provenance has no page; name the layout in sheet")
            if not re.search(DRAWING_REFERENCE, self.reference):
                raise ValueError("drawing provenance reference must name a .dwg or .dxf file")
        elif self.sheet is not None:
            raise ValueError(f"sheet is only allowed for kind 'drawing', not {self.kind!r}")
        return self


class Approval(Contract):
    parts_sha256: Hash | None = Field(
        default=None, description="Gate 1: PartsList.approval_sha256(), excluding gate1/status; not file bytes")
    actor: str = Field(min_length=1)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    scope: Literal["synthetic_fixture", "project"]
    note: str = Field(min_length=1)
    # Proof of the user's answer [#1205]: https issue/comment URL, kanban card id or D<n> decision id.
    # `not \s` keeps JSON Schema validators whose `$` matches before a final newline as strict as the model.
    ref: str | None = Field(default=None, pattern=r"^(https://\S+|t_[0-9a-f]+|D[1-9][0-9]*)$",
                            json_schema_extra={"not": {"type": "string", "pattern": r"\s"}})
