# ruff: noqa: A005
from enum import Enum
from typing import Any

from pydantic import BaseModel


class DocumentBlacklistStatus(str, Enum):
    OK = "ok"
    BLACKLISTED = "blacklisted"


class NonRagDocument(BaseModel):
    url: str
    title: str
    body: str
    status: DocumentBlacklistStatus


class IsNonRagDocumentRelevantTask(BaseModel):
    document: NonRagDocument
    task: Any
