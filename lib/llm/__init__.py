from app.config import LLM_DEFAULT_MODEL
from app.database.models import LLM
from app.database.table import LLMTable

from .llm_constants import *
from .llm_transaction import *


def llm_get_default_model() -> LLM:
    """
    Get the LLM model object from the database where model name is specified by LLM_DEFAULT_MODEL config parameter.
    """
    return LLMTable().get_by_model(LLM_DEFAULT_MODEL)
