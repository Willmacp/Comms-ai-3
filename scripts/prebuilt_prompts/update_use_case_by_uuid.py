"""
A script to update a single use case by its UUID.

This script:
1. Takes a use case UUID and new values for title, instruction, user input form and position
2. Finds the theme associated with that use case UUID
3. Updates the use case with the new values

Prerequisites:
- Configure base_url to point to your target API
- Ensure network access to the target API environment (dev/test/prod)
- Set the use case UUID and new values in the script
- Run as: python3 scripts/prebuilt_prompts/update_use_case_by_uuid.py
"""

##########################################################################
### Setup

import logging
import os
from uuid import UUID

import requests
from dotenv import load_dotenv

# Load environment variables from .env file, overwriting if needed
load_dotenv(override=True)

# The base URL for the API. We use this to send requests to the API.
base_url = "http://localhost:5312"

# The UUID of the use case you want to change
use_case_uuid = UUID("f56aec22-f604-457b-b1da-523c2fc97e53")

# The new values for title, instruction, and user_input_form
new_title = "Your new title here"
new_instruction = "Your new instruction here"
new_user_input_form = "Your new user input form here"
new_position = 1

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


##########################################################################
### Function definitions
def create_session_auth(base_url: str, user_uuid: str, auth_token: str = os.getenv("AUTH_SECRET_KEY")):
    """
    Create an authenticated session for API access.

    Creates a session by calling the auth-sessions endpoint with the provided credentials.
    Returns a session authentication token for subsequent API calls.

    Args:
        base_url: Base URL of the API
        user_uuid: UUID of the user to authenticate
        auth_token: Authentication token (defaults to AUTH_SECRET_KEY env var)

    Returns:
        str: Session authentication token

    Raises:
        requests.RequestException: If the authentication request fails
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


def get_theme_uuid_by_use_case(
    use_case_uuid: UUID, session_auth: str, user_uuid: str, auth_token: str = os.getenv("AUTH_SECRET_KEY")
):
    """
    Find the theme UUID that contains a specific use case.

    Fetches all themes and their use cases, searching for the use case UUID
    to determine which theme contains it.

    Args:
        use_case_uuid: UUID of the use case to find
        session_auth: Session authentication token
        user_uuid: UUID of the authenticated user
        auth_token: Authentication token (defaults to AUTH_SECRET_KEY env var)

    Returns:
        str: UUID of the theme containing the use case

    Raises:
        ValueError: If the use case is not found in any theme
        requests.RequestException: If API requests fail
    """
    try:
        themes_url = f"{base_url}/v1/prompts/themes"
        headers = {"Session-Auth": session_auth, "User-Key-UUID": user_uuid, "Auth-Token": auth_token}
        logger.debug(f"Sending GET request to {themes_url} with headers {headers}")
        themes_response = requests.get(themes_url, headers=headers)
        themes_response.raise_for_status()
        themes = themes_response.json()["themes"]

        for theme in themes:
            theme_uuid = theme["uuid"]
            use_cases_url = f"{base_url}/v1/prompts/themes/{theme_uuid}/use-cases"
            logger.debug(f"Sending GET request to {use_cases_url} with headers {headers}")
            use_cases_response = requests.get(use_cases_url, headers=headers)
            use_cases_response.raise_for_status()
            use_cases = use_cases_response.json()["use_cases"]

            for use_case in use_cases:
                if use_case["uuid"] == str(use_case_uuid):
                    logger.debug(f"Found use case {use_case_uuid} in theme {theme_uuid}")
                    return theme_uuid

        raise ValueError(f"Use case with UUID {use_case_uuid} not found in any theme")
    except requests.RequestException as e:
        logger.error(f"Request to get theme UUID by use case failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error while getting theme UUID by use case: {e}")
        raise


def update_use_case(
    theme_uuid: str, use_case_uuid: str, new_data: dict, auth_token: str = os.getenv("AUTH_SECRET_KEY")
):
    """
    Update a use case with new data.

    Makes a PUT request to update the specified use case with new values.

    Args:
        theme_uuid: UUID of the theme containing the use case
        use_case_uuid: UUID of the use case to update
        new_data: Dictionary containing the new values for the use case
        auth_token: Authentication token (defaults to AUTH_SECRET_KEY env var)

    Raises:
        requests.RequestException: If the update request fails
    """
    try:
        url = f"{base_url}/v1/prompts/themes/{theme_uuid}/use-cases/{use_case_uuid}"
        headers = {"Auth-Token": auth_token, "Content-Type": "application/json"}
        logger.debug(f"Sending PUT request to {url} with headers {headers} and data {new_data}")
        response = requests.put(url, headers=headers, json=new_data)
        response.raise_for_status()
        logger.debug(f"Successfully updated use case {use_case_uuid}")
    except requests.RequestException as e:
        logger.error(f"Request to update use case failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error while updating use case: {e}")
        raise


##########################################################################
### Trigger and run

if __name__ == "__main__":
    logger.info("\n\n### === *** STARTING UPDATE OF USE CASE BY UUID *** === ###")

    try:
        user_uuid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        session_auth = create_session_auth(base_url, user_uuid)

        theme_uuid = get_theme_uuid_by_use_case(use_case_uuid, session_auth, user_uuid)
        new_data = {
            "use_case_uuid": str(use_case_uuid),
            "theme_uuid": theme_uuid,
            "title": new_title,
            "instruction": new_instruction,
            "user_input_form": new_user_input_form,
            "position": new_position,
        }
        update_use_case(theme_uuid, str(use_case_uuid), new_data)
        logger.info(f"Successfully updated use case with UUID '{use_case_uuid}'")
    except Exception as e:
        logger.error(f"An error occurred during the use case update process: {e}")
