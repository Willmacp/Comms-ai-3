"""
A script to bulk upload prompts from a local data folder to the API.

This script:
1. Loads prompts from a JSON file in the data folder
2. Uploads them to the API in bulk using the prompts/bulk endpoint

Prerequisites:
- Configure base_url to point to your target API
- Ensure network access to the target API environment (dev/test/prod)
- Set the file_path to your target JSON file containing the prompts
- Run as: python3 scripts/prebuilt_prompts/bulk_upload_prompts_from_folder.py
"""

##########################################################################
### Setup

import json
import logging
import os

import requests
from dotenv import load_dotenv

# Load environment variables from .env file, overwriting if needed
load_dotenv(override=True)

# The base URL for the API. We use this to send requests to the API.
base_url = "http://localhost:5312"

# The name of the file to use for bulk upload
file_path = "data/prompts/2024-10-10_prompts.json"

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

##########################################################################
### Function definitions


def load_prompts_from_data_folder(file_path):
    """
    Load prompts from a JSON file in the data folder.

    Args:
        file_path (str): Path to the JSON file containing prompts

    Returns:
        list: List of prompts loaded from the JSON file

    Raises:
        Exception: If there is an error loading the file
    """
    try:
        with open(file_path, "r") as f:
            prompts = json.load(f)
        logger.debug(f"Loaded {len(prompts)} prompts from {file_path}")
        return prompts
    except Exception as e:
        logger.error(f"Error while loading prompts from data folder: {e}")
        raise


def upload_prompts(prompts: list, auth_token: str = os.getenv("AUTH_SECRET_KEY")):
    """
    Upload prompts in bulk to the API.

    Args:
        prompts (list): List of prompts to upload
        auth_token (str): Authentication token, defaults to AUTH_SECRET_KEY env var

    Raises:
        requests.RequestException: If the API request fails
        Exception: If there is any other error during upload
    """
    try:
        url = f"{base_url}/v1/prompts/bulk"
        headers = {"Auth-Token": auth_token, "Content-Type": "application/json"}
        body = prompts
        logger.debug(f"Sending POST request to {url} with headers {headers} and body {body}")
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        logger.debug("Successfully uploaded prompts")
    except requests.RequestException as e:
        logger.error(f"Request to bulk-upload prompts failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error while bulk-uploading prompts: {e}")
        raise


##########################################################################
### Trigger and run

if __name__ == "__main__":
    logger.info("\n\n### === *** STARTING BULK UPLOAD OF PROMPTS *** === ###")

    try:
        prompts = load_prompts_from_data_folder(file_path)
        upload_prompts(prompts)
        logger.info("\n\n### === *** COMPLETED BULK UPLOAD OF PROMPTS *** === ###")
        logger.info(f"Successfully uploaded {len(prompts)} prompts.")
    except Exception as e:
        logger.error(f"An error occurred during the prompt upload process: {e}")
