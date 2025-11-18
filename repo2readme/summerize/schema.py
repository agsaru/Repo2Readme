

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any


class Param(BaseModel):
    """Represents a single function/class parameter."""

    name: str = Field(
        ...,
        description="Name of the parameter (e.g., 'path', 'req', 'user_id')."
    )
    type: Optional[str] = Field(
        default=None,
        description="Optional type of the parameter (e.g., 'string', 'int', 'Object')."
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional short explanation of the parameter."
    )


class FunctionSummary(BaseModel):
    """
    Summary of a function, method, class, component, module,
    or any callable/code entity inside the file.
    """

    name: str = Field(
        ...,
        description="Name of the function/class/component (e.g., 'main', 'predict', 'HomePage')."
    )
    description: str = Field(
        ...,
        description="One-line summary describing what this function/class does."
    )

    params: Optional[List[Param]] = Field(
        default=None,
        description=(
            "List of parameters accepted by the function/class. "
            "Supports flexible input formats: list of strings, list of dicts, or a single dict."
        )
    )

    returns: Optional[Any] = Field(
        default=None,
        description="What the function or class returns. Can be a string, dict, list, or None."
    )

    @field_validator("params", mode="before")
    def normalize_params(cls, value):
        """Normalize messy LLM output into a list of Param objects."""

        if not value:
            return None

        # Already normalized
        if isinstance(value, list) and all(isinstance(x, Param) for x in value):
            return value

        # List of dicts
        if isinstance(value, list) and all(isinstance(x, dict) for x in value):
            return [Param(**x) for x in value]

        # Single dict
        if isinstance(value, dict):
            if "name" in value:
                return [Param(**value)]
            return [Param(name=k, type=str(v)) for k, v in value.items()]

        # List of strings
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            return [Param(name=x) for x in value]

        # Fallback
        return [Param(name=str(value))]


class CodeSummary(BaseModel):
    """
    Summary of a single source file inside the repository.
    Used as the final structured output for LLM parsing.
    """

    file_path: str = Field(
        ...,
        description="Full file path relative to repository root (e.g., 'src/app/main.py')."
    )

    language: str = Field(
        ...,
        description="Programming language used in the file (e.g., 'Python', 'JavaScript')."
    )

    short_description: str = Field(
        ...,
        description="Short, one-sentence explanation of what the entire file does."
    )

    functions: List[FunctionSummary] = Field(
        default_factory=list,
        description="List of detected functions/classes/components inside the file."
    )

    imports: Optional[List[str]] = Field(
        default=None,
        description="List of imported modules/libraries used in the file."
    )

    exports: Optional[List[str]] = Field(
        default=None,
        description="List of exported symbols such as classes, functions, or components."
    )

    @field_validator("imports", "exports", mode="before")
    def normalize_list(cls, value):
        """Normalize import/export lists into consistent list-of-strings."""
        if not value:
            return None
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]

    @field_validator("short_description")
    def validate_short_description(cls, value):
        if not value or not value.strip():
            raise ValueError("short_description must be non-empty.")
        return value


parser = PydanticOutputParser(pydantic_object=CodeSummary)
