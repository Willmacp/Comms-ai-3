import logging
from dataclasses import dataclass

from anthropic.types import TextBlock
from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError

from app.database.models import LLM, LlmInternalResponse, SystemPrompt
from app.database.table import async_db_session
from app.lib.llm import LLMResponse
from app.services.bedrock import BedrockHandler, MessageFunctions, RunMode

logger = logging.getLogger(__name__)


@dataclass
class Claude35SonnetTransaction:
    tokens_in: int
    tokens_out: int
    price_per_token_in_usd: float = 3 / 1e6
    price_per_token_out_usd: float = 15 / 1e6

    def completion_cost(self) -> float:
        return (self.tokens_in * self.price_per_token_in_usd) + (self.tokens_out * self.price_per_token_out_usd)


class RagLlmHandler:
    def __init__(self, llm: LLM, system_prompt: SystemPrompt):
        self.llm = llm
        self.system_prompt = system_prompt
        self.bedrock_handler = BedrockHandler(mode=RunMode.ASYNC)

    async def call_llm(self, prompt: str):
        try:
            formatted_prompt = f"System: {self.system_prompt.content}\n\nHuman: {prompt}\n\nAssistant: "
            response = await self.bedrock_handler.invoke_async_with_call_cost_details(
                MessageFunctions.format_messages(formatted_prompt)
            )
            return response
        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            raise

    def process_response(self, response: LLMResponse):
        try:
            ai_message = response.content
            tokens_in = response.input_tokens
            tokens_out = response.output_tokens
            transaction = Claude35SonnetTransaction(tokens_in, tokens_out)
            return ai_message, transaction
        except Exception as e:
            logger.error(f"Error processing LLM response: {str(e)}")
            raise

    async def save_response(self, ai_message: str | list, transaction: Claude35SonnetTransaction):
        if isinstance(ai_message, list):
            content = "".join([m.text for m in ai_message if isinstance(m, TextBlock)])
        else:
            content = ai_message
        try:
            async with async_db_session() as session:
                stmt = (
                    insert(LlmInternalResponse)
                    .values(
                        llm_id=self.llm.id,
                        system_prompt_id=self.system_prompt.id,
                        content=content,
                        tokens_in=transaction.tokens_in,
                        tokens_out=transaction.tokens_out,
                        completion_cost=transaction.completion_cost(),
                    )
                    .returning(LlmInternalResponse)  # Return the  inserted row
                )
                result = await session.execute(stmt)
                inserted_response = result.scalars().first()
                return inserted_response
        except SQLAlchemyError as e:
            logger.exception(f"Database error while saving response: {str(e)}")
            raise

    async def invoke(self, prompt: str):
        try:
            response = await self.call_llm(prompt)
            ai_message, transaction = self.process_response(response)
            llm_internal_response = await self.save_response(ai_message, transaction)
            return ai_message, llm_internal_response
        except Exception as e:
            logger.error(f"Error in RagLlmHandler.invoke: {str(e)}")
            raise
