"""
Written 2024-10-10

This script is designed to retrieve all themes from the API and save them to a file.

To use this script, you need to:
- Edit the 'base_url' to the base URL of your target API.
- Ensure your machine has network access to the dev / test / production APIs as needed.
- Run the script as a single python script (e.g `python3 scripts/prompts/get_themes.py`)
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


def save_themes_to_file(themes):
    """
    Save the list of themes to a file in the data/themes/ directory.

    The filename is the ISO datetime followed by '_themes.json'.

    Args:
        themes (list): A list of themes to save.
    """
    try:
        os.makedirs("data/themes", exist_ok=True)
        current_time = datetime.now().strftime("%Y%m%dT%H%M%S")
        filename = f"data/themes/{current_time}_themes.json"
        with open(filename, "w") as f:
            json.dump(themes, f, indent=4)
        logger.info(f"Themes saved to {filename}")
    except Exception as e:
        logger.error(f"Error while saving themes to file: {e}")
        raise


##########################################################################
### Trigger and run

if __name__ == "__main__":
    logger.info("\n\n### === *** STARTING GET OF THEMES *** === ###")

    try:
        user_uuid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        session_auth = create_session_auth(base_url, user_uuid)

        themes = get_themes(session_auth, user_uuid)
        logger.info(f"Successfully retrieved {len(themes)} themes.")
        save_themes_to_file(themes)
    except Exception as e:
        logger.error(f"An error occurred during the theme retrieval process: {e}")
