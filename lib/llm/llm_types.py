# ruff: noqa: A005
from typing import List, Optional

from anthropic.types import TextBlock, ToolUseBlock
from pydantic import BaseModel


class LLMUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class LLMResponse(BaseModel):
    content: str | List[Optional[str | TextBlock | ToolUseBlock]]
    # content: str
    input_tokens: int
    output_tokens: int


class LLMTransaction(LLMResponse):
    input_cost: float
    output_cost: float
    completion_cost: float
    # usage: LLMUsage
