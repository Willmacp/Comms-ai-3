"""
A script to update a single theme by its UUID.

This script:
1. Takes a theme UUID and new values for title, subtitle and position
2. Updates the theme with the new values

Prerequisites:
- Configure base_url to point to your target API
- Ensure network access to the target API environment (dev/test/prod)
- Set the theme UUID and new values in the script
- Run as: python3 scripts/prebuilt_prompts/update_theme_by_uuid.py
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

# The UUID of the theme you want to change
theme_uuid = UUID("e9c48461-540a-4631-9b5a-e208f4d2e4fd")

# The new values for title, subtitle and position
new_title = "Your new title here"
new_subtitle = "Your new subtitle here"
new_position = 1

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

##########################################################################
### Function definitions


def update_theme(theme_uuid: UUID, new_data: dict, auth_token: str = os.getenv("AUTH_SECRET_KEY")):
    """
    Update a theme with new data.

    This function sends a PUT request to update an existing theme with new values for title,
    subtitle and position using the provided authentication token.

    Args:
        theme_uuid (UUID): The UUID of the theme to update.
        new_data (dict): Dictionary containing the new values for the theme:
            - theme_uuid (str): UUID of the theme
            - title (str): New title for the theme
            - subtitle (str): New subtitle for the theme
            - position (int): New position for the theme
        auth_token (str): The authentication token, defaulting to AUTH_SECRET_KEY env var.

    Raises:
        requests.RequestException: If the API request fails
        Exception: For any other errors during update
    """
    try:
        url = f"{base_url}/v1/prompts/themes/{theme_uuid}"
        headers = {"Auth-Token": auth_token, "Content-Type": "application/json"}
        logger.debug(f"Sending PUT request to {url} with headers {headers} and data {new_data}")
        response = requests.put(url, headers=headers, json=new_data)
        response.raise_for_status()
        logger.debug(f"Successfully updated theme {theme_uuid}")
    except requests.RequestException as e:
        logger.error(f"Request to update theme failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error while updating theme: {e}")
        raise


##########################################################################
### Trigger and run

if __name__ == "__main__":
    logger.info("\n\n### === *** STARTING UPDATE OF THEME BY UUID *** === ###")

    try:
        new_data = {
            "theme_uuid": str(theme_uuid),
            "title": new_title,
            "subtitle": new_subtitle,
            "position": new_position,
        }
        update_theme(theme_uuid, new_data)
        logger.info(f"Successfully updated theme with UUID '{theme_uuid}'")
    except Exception as e:
        logger.error(f"An error occurred during the theme update process: {e}")
