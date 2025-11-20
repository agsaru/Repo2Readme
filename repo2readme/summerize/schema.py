from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator
from langchain_core.output_parsers import PydanticOutputParser


class Param(BaseModel):
    """Represents one parameter in a function, method, or class."""

    name: str = Field(
        ...,
        description="Name of the parameter (e.g. 'path', 'req', 'user_id')."
    )
    type: Optional[str] = Field(
        None,
        description="Data type of the parameter (e.g. 'str', 'int', 'User')."
    )
    description: Optional[str] = Field(
        None,
        description="Short explanation of what the parameter represents."
    )


class FunctionSummary(BaseModel):
    """Structured summary of a single function, method, class, or component."""

    name: str = Field(
        ...,
        description="Name of the function/class/component."
    )
    description: str = Field(
        ...,
        description="One-sentence summary of what this entity does."
    )

    params: Optional[List[Param]] = Field(
        None,
        description=(
            "Parameters accepted by the function. Supports flexible input: "
            "list of strings, list of dicts, a single dict, or a normalized list."
        )
    )

    returns: Optional[Any] = Field(
        None,
        description="Return value of the function — can be any data type."
    )

    @field_validator("params", mode="before")
    def normalize_params(cls, value):
        """
        Converts various messy LLM outputs into a proper list of Param objects.
        Accepts dicts, lists of dicts, raw strings, or already-parsed Param instances.
        """

        if not value:
            return None

        if isinstance(value, list) and all(isinstance(x, Param) for x in value):
            return value

        if isinstance(value, list) and all(isinstance(x, dict) for x in value):
            return [Param(**x) for x in value]

        if isinstance(value, dict):
            if "name" in value:
                return [Param(**value)]
            return [Param(name=k, type=str(v)) for k, v in value.items()]

        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            return [Param(name=x) for x in value]

        return [Param(name=str(value))]


class CodeSummary(BaseModel):
    """Summary of a single source file inside a repository."""

    file_path: str = Field(
        ...,
        description="File path relative to the repository root."
    )

    language: str = Field(
        ...,
        description="Programming language used in this file."
    )

    short_description: str = Field(
        ...,
        description="One-sentence overview of what the file does."
    )

    functions: List[FunctionSummary] = Field(
        default_factory=list,
        description="All functions/classes/components detected in the file."
    )

    imports: Optional[List[str]] = Field(
        None,
        description="List of modules or libraries imported by the file."
    )

    exports: Optional[List[str]] = Field(
        None,
        description="Identifiers exported by the file (e.g., classes or functions)."
    )

    @field_validator("imports", "exports", mode="before")
    def normalize_list(cls, value):
        """
        Ensures imports/exports are returned as lists of strings,
        even if the LLM returns a string or a single item.
        """
        if not value:
            return None
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]

    @field_validator("short_description")
    def validate_short_description(cls, value):
        """The short description must not be empty."""
        if not value or not value.strip():
            raise ValueError("short_description must be non-empty.")
        return value

parser = PydanticOutputParser(pydantic_object=CodeSummary)
