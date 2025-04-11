"""
Written 2024-10-09

This script is designed to perform a bulk retrieval of prompts from the API and save them to a local data folder.
It is useful for backing up or processing prompts in bulk.

To use this script, you need to:
- Edit the 'base_url' to the base URL of your target API.
- Ensure your machine has network access to the dev / test / production APIs as needed.
- Run the script as a single python script
(e.g `python3 scripts/prompts/bulk_get_prompts.py`)
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


def get_prompts(auth_token: str = os.getenv("AUTH_SECRET_KEY")):
    """
    Retrieve prompts from the API using the provided authentication token.

    Args:
        auth_token (str): The authentication token, defaulting to the value of the AUTH_SECRET_KEY environment variable.

    Returns:
        list: A list of prompts retrieved from the API.
    """
    try:
        url = f"{base_url}/v1/prompts/bulk"
        headers = {"Auth-Token": auth_token}
        logger.debug(f"Sending GET request to {url} with headers {headers}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        prompts = response.json()["prompts"]
        logger.debug(f"Retrieved {len(prompts)} prompts")
        return prompts
    except requests.RequestException as e:
        logger.error(f"Request to bulk-get prompts failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error while bulk-getting prompts: {e}")
        raise


def save_prompts_to_data_folder(prompts: list):
    """
    Save the list of prompts to the data folder as a single JSON file.

    Args:
        prompts (list): A list of prompts to save.
    """
    folder = "data/prompts"
    os.makedirs(folder, exist_ok=True)
    current_time = datetime.now().strftime("%Y%m%dT%H%M%S")
    file_name = f"{current_time}_prompts.json"
    file_path = os.path.join(folder, file_name)
    try:
        with open(file_path, "w") as f:
            json.dump(prompts, f, indent=4)
        logger.debug(f"Saved all prompts to {file_path}")
    except Exception as e:
        logger.error(f"Error while saving prompts to data folder: {e}")
        raise


##########################################################################
### Trigger and run

if __name__ == "__main__":
    logger.info("\n\n### === *** STARTING BULK GET OF PROMPTS *** === ###")

    try:
        prompts = get_prompts()
        save_prompts_to_data_folder(prompts)
        logger.info("\n\n### === *** COMPLETED BULK GET OF PROMPTS *** === ###")
        logger.info(f"Successfully saved {len(prompts)} prompts.")
    except Exception as e:
        logger.error(f"An error occurred during the prompt retrieval process: {e}")
