"""Shared data types for access control management."""

from typing import List

from pydantic import BaseModel, Field


class DocumentAccessUpdate(BaseModel):
    """Describes an update to a document's access groups."""

    access_groups: List[str] = Field(
        default_factory=list,
        description="List of groups that should be allowed to access the document.",
    )
