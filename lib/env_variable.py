import os

from dotenv import load_dotenv

if os.path.exists("../.env"):
    load_dotenv("../.env")
    # print("Loaded environment variables from .env file.")


def env_variable(env_variable_name: str, default_bool=False):
    variable = os.getenv(env_variable_name, default_bool)

    if variable and variable.lower() == "false":
        return False

    return variable
