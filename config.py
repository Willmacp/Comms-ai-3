import os
from typing import Union

from dotenv import load_dotenv


def load_environment_variables():
    if os.path.exists("../.env"):
        load_dotenv("../.env")
        # print("Loaded environment variables from .env file.")


def env_variable(name: str, default=None) -> Union[str, bool]:
    value = os.getenv(name, default)
    if value and str(value).lower() == "false":
        return False
    if value and str(value).lower() == "true":
        return True
    return value


IS_DEV = env_variable("IS_DEV")
URL_HOSTNAME = os.getenv("URL_HOSTNAME", "http://localhost:" + os.getenv("PORT", "5312"))
DATA_DIR = "data"

BYPASS_SESSION_VALIDATOR = env_variable("BYPASS_SESSION_VALIDATOR")
BYPASS_AUTH_VALIDATOR = env_variable("BYPASS_AUTH_VALIDATOR")

LLM_DEFAULT_PROVIDER = "bedrock"
AWS_BEDROCK_REGION1 = "us-west-2"
AWS_BEDROCK_REGION2 = "us-east-1"

LLM_DEFAULT_MODEL = "anthropic.claude-3-7-sonnet-20250219-v1:0"
LLM_DOCUMENT_RELEVANCY_MODEL = "anthropic.claude-3-5-haiku-20241022-v1:0"

if env_variable("LLM_DEFAULT_MODEL"):
    LLM_DEFAULT_MODEL = env_variable("LLM_DEFAULT_MODEL")

WHITELISTED_URLS = ["https://www.gov.uk"]
BLACKLISTED_URLS = ["https://www.gov.uk/publications"]
WEB_BROWSING_TIMEOUT = 300
GOV_UK_BASE_URL = "https://www.gov.uk"
GOV_UK_SEARCH_MAX_COUNT = 5
