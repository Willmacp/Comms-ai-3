import logging

from app.database.models import LLM

from .llm_types import LLMResponse, LLMTransaction

logger = logging.getLogger(__name__)


def llm_transaction(llm: LLM, response: LLMResponse) -> LLMTransaction:
    input_cost = response.input_tokens * llm.input_cost_per_token
    output_cost = response.output_tokens * llm.output_cost_per_token

    return LLMTransaction(
        content=response.content,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        input_cost=input_cost,
        output_cost=output_cost,
        completion_cost=input_cost + output_cost,
    )
