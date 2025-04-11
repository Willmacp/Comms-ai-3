"""
Written 2024-10-10

This script is designed to retrieve all use cases from the API and save them to a file.

To use this script, you need to:
- Edit the 'base_url' to the base URL of your target API.
- Ensure your machine has network access to the dev / test / production APIs as needed.
- Run the script as a single python script
(e.g `python3 scripts/prompts/get_use_cases_and_save_locally.py`)
"""

##########################################################################
### Setup

import json
import logging
import os
from datetime import datetime

import requests
from dotenv import load_dotenv

# Load environment variables from .env file, overwriting if needed
load_dotenv(override=True)

# The base URL for the API. We use this to send requests to the API.
base_url = "http://localhost:5312"

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

##########################################################################
### Function definitions


def create_session_auth(base_url: str, user_uuid: str, auth_token: str = os.getenv("AUTH_SECRET_KEY")):
    """
    Create an authenticated session for a user.

    This function sends a POST request to the /v1/auth-sessions endpoint to create an authenticated session
    using the provided base URL, authentication token, and user UUID. It returns the session authentication token.

    Args:
        base_url (str): The base URL of the API.
        auth_token (str): The authentication token, defaulting to the value of the AUTH_SECRET_KEY environment variable.
        user_uuid (str): The UUID of the user, defaulting to a newly generated UUID.

    Returns:
        str: The session authentication token.
    """
    try:
        user_key_uuid = user_uuid

        auth_sessions_url = f"{base_url}/v1/auth-sessions"
        auth_sessions_headers = {"User-Key-UUID": user_key_uuid, "Auth-Token": auth_token}
        logger.debug(f"Sending POST request to {auth_sessions_url} with headers {auth_sessions_headers}")
        auth_sessions_response = requests.post(auth_sessions_url, headers=auth_sessions_headers)
        auth_sessions_response.raise_for_status()
        session_auth = auth_sessions_response.json().get("Session-Auth")
        logger.debug(f"Received session_auth: {session_auth}")

        return session_auth
    except requests.RequestException as e:
        logger.error(f"Failed to create session auth: {e}")
        raise


def get_themes(session_auth: str, user_uuid: str, auth_token: str = os.getenv("AUTH_SECRET_KEY")):
    """
    Retrieve all themes from the API using the provided authentication token.

    Args:
        session_auth (str): The session authentication token.
        user_uuid (str): The UUID of the user.
        auth_token (str): The authentication token, defaulting to the value of the AUTH_SECRET_KEY environment variable.

    Returns:
        list: A list of themes retrieved from the API.
    """
    try:
        url = f"{base_url}/v1/prompts/themes"
        headers = {"Session-Auth": session_auth, "User-Key-UUID": user_uuid, "Auth-Token": auth_token}
        logger.debug(f"Sending GET request to {url} with headers {headers}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        themes = response.json()["themes"]
        logger.debug(f"Retrieved {len(themes)} themes")
        return themes
    except requests.RequestException as e:
        logger.error(f"Request to get themes failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error while getting themes: {e}")
        raise


def get_use_cases(session_auth: str, theme_uuid: str, user_uuid: str, auth_token: str = os.getenv("AUTH_SECRET_KEY")):
    """
    Retrieve all use cases for a given theme from the API using the provided authentication token.

    Args:
        session_auth (str): The session authentication token.
        theme_uuid (str): The UUID of the theme.
        user_uuid (str): The UUID of the user.
        auth_token (str): The authentication token, defaulting to the value of the AUTH_SECRET_KEY environment variable.

    Returns:
        list: A list of use cases retrieved from the API for the specified theme.
    """
    try:
        url = f"{base_url}/v1/prompts/themes/{theme_uuid}/use-cases"
        headers = {"Session-Auth": session_auth, "User-Key-UUID": user_uuid, "Auth-Token": auth_token}
        logger.debug(f"Sending GET request to {url} with headers {headers}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        use_cases = response.json()["use_cases"]
        logger.debug(f"Retrieved {len(use_cases)} use cases for theme {theme_uuid}")
        return use_cases
    except requests.RequestException as e:
        logger.error(f"Request to get use cases failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error while getting use cases: {e}")
        raise


def get_use_case_details(
    session_auth: str,
    theme_uuid: str,
    use_case_uuid: str,
    user_uuid: str,
    auth_token: str = os.getenv("AUTH_SECRET_KEY"),
):
    """
    Retrieve detailed information for a specific use case from the API using the provided authentication token.

    Args:
        session_auth (str): The session authentication token.
        use_case_uuid (str): The UUID of the use case.
        theme_uuid (str): The UUID of the theme.
        user_uuid (str): The UUID of the user.
        auth_token (str): The authentication token, defaulting to the value of the AUTH_SECRET_KEY environment variable.

    Returns:
        dict: A dictionary containing detailed information about the use case.
    """
    try:
        url = f"{base_url}/v1/prompts/themes/{theme_uuid}/use-cases/{use_case_uuid}"
        headers = {"Session-Auth": session_auth, "User-Key-UUID": user_uuid, "Auth-Token": auth_token}
        logger.debug(f"Sending GET request to {url} with headers {headers}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        use_case_details = response.json()
        logger.debug(f"Retrieved details for use case {use_case_uuid}")
        return use_case_details
    except requests.RequestException as e:
        logger.error(f"Request to get use case details failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error while getting use case details: {e}")
        raise


def save_use_cases_to_file(themes_with_use_cases):
    """
    Save the list of themes with nested use cases to a file in the data/use_cases/ directory.

    The filename is the ISO datetime followed by '_use_cases.json'.

    Args:
        themes_with_use_cases (list): A list of themes with nested use cases to save.
    """
    try:
        os.makedirs("data/use_cases", exist_ok=True)
        current_time = datetime.now().strftime("%Y%m%dT%H%M%S")
        filename = f"data/use_cases/{current_time}_use_cases.json"
        with open(filename, "w") as f:
            json.dump(themes_with_use_cases, f, indent=4)
        logger.info(f"Themes with use cases saved to {filename}")
    except Exception as e:
        logger.error(f"Error while saving themes with use cases to file: {e}")
        raise


##########################################################################
### Trigger and run

if __name__ == "__main__":
    logger.info("\n\n### === *** STARTING GET OF USE CASES *** === ###")

    try:
        user_uuid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        session_auth = create_session_auth(base_url, user_uuid)

        themes = get_themes(session_auth, user_uuid)
        logger.info(f"Successfully retrieved {len(themes)} themes.")

        themes_with_use_cases = []
        for theme in themes:
            theme_uuid = theme["uuid"]
            use_cases = get_use_cases(session_auth, theme_uuid, user_uuid)
            theme_with_use_cases = {
                "theme.uuid": theme_uuid,
                "theme.title": theme.get("title"),
                "theme.subtitle": theme.get("subtitle"),
                "use_cases": [],
            }
            for use_case in use_cases:
                use_case_uuid = use_case["uuid"]
                use_case_details = get_use_case_details(session_auth, theme_uuid, use_case_uuid, user_uuid)
                theme_with_use_cases["use_cases"].append(
                    {
                        "use_case.uuid": use_case_uuid,
                        "use_case.title": use_case_details.get("title"),
                        "use_case.instruction": use_case_details.get("instruction"),
                        "use_case.user_input_form": use_case_details.get("user_input_form"),
                        "use_case.position": use_case_details.get("position"),
                    }
                )
            themes_with_use_cases.append(theme_with_use_cases)
            logger.info("Successfully retrieved use cases.")

        save_use_cases_to_file(themes_with_use_cases)
    except Exception as e:
        logger.error(f"An error occurred during the use case retrieval process: {e}")
