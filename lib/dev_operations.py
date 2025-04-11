from app.config import LLM_DEFAULT_MODEL, LLM_DEFAULT_PROVIDER
from app.services.bedrock import BedrockHandler, MessageFunctions


async def request_messages_from_llm(q: str):
    llm = BedrockHandler()
    messages = MessageFunctions.format_messages(q)
    response = llm.invoke_async(messages)
    response["model"] = LLM_DEFAULT_MODEL
    response["provider"] = LLM_DEFAULT_PROVIDER

    return response
