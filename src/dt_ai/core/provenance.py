"""Shared provenance contracts; independent of parts, spec and intake models."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Finite = Annotated[float, Field(allow_inf_nan=False)]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Name = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$", max_length=120)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)
    schema_version: Literal["1.0.0"] = "1.0.0"


class SourceRef(Contract):
    kind: Literal["synthetic", "pdf", "model", "user"]
    reference: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1, le=100000)
    sha256: Hash | None = None
    region: list[Finite] | None = Field(default=None, min_length=4, max_length=4)

    @model_validator(mode="after")
    def pdf_has_page(self):
        if self.kind == "pdf" and (self.page is None or self.sha256 is None):
            raise ValueError("PDF provenance requires page and sha256")
        return self


class Approval(Contract):
    actor: str = Field(min_length=1)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    scope: Literal["synthetic_fixture", "project"]
    note: str = Field(min_length=1)
    # Proof of the user's answer [#1205]: https issue/comment URL, kanban card id or D<n> decision id.
    # `not \s` keeps JSON Schema validators whose `$` matches before a final newline as strict as the model.
    ref: str | None = Field(default=None, pattern=r"^(https://\S+|t_[0-9a-f]+|D[1-9][0-9]*)$",
                            json_schema_extra={"not": {"type": "string", "pattern": r"\s"}})
