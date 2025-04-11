from app.config import LLM_DEFAULT_MODEL


class LLMConstants:
    DEFAULT_LLM_MESSAGE = (
        f"This is a generic message returned from the LLM endpoint and does not access the "
        f"'{LLM_DEFAULT_MODEL}' LLM. to disable this message, set the 'USE_DEFAULT_LLM_RESPONSE' "
        f"environment variable to empty (USE_DEFAULT_LLM_RESPONSE=) in your .env file."
    )
