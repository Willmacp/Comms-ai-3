# from app.lib.llm.llm_class import LLMClass
# from app.app_types.message import Messages


# def chat_langchain(
#     q: str,
#     messages: Messages = [],
#     system_message: str = '',
#     parse_data = None,
# ):
#     # if stream:
#     #     llm = LLMStream(parse_data)
#     # else:
#     llm = LLMClass()

#     formatted_messages = llm.format_messages(q, messages, system_message)
#     response = llm.invoke(formatted_messages)

#     return response
