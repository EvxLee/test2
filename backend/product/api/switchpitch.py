import os
import requests
from dotenv import load_dotenv
from urllib.parse import urlparse
from utils import normalize_domain

load_dotenv()

BASE_URL = os.getenv("SWITCHPITCH_API_URL")
BEARER_TOKEN = os.getenv("SWITCHPITCH_BEARER_TOKEN")
HEADERS = {"Authorization": f"Bearer {BEARER_TOKEN}"}

def get_common_data(startup_id):
    url = f"{BASE_URL}/startups/{startup_id}/get-common-data"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    print(f"Failed to get common data for {startup_id}")
    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")
    return None

def get_startup_details(startup_id):
    url = f"{BASE_URL}/startups/{startup_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    return None

def search_switchpitch(domain):
    """
    Searches for a startup on SwitchPitch by domain.
    If a match is found, retrieves both startup details and enriched common data.
    Returns a dictionary combining both sets of data.
    """
    domain = normalize_domain(domain)
    search_url = f"{BASE_URL}/search/get-list?keywords[]={domain}&limit=25"
    response = requests.get(search_url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Failed search for {domain} | Status: {response.status_code}")
        return None

    results = response.json()
    for item in results:
        api_website = item.get("website", "")
        if normalize_domain(api_website) == domain:
            startup_id = item.get("id")
            if startup_id:
                # Fetch additional info
                details = get_startup_details(startup_id)
                common_data = get_common_data(startup_id)
                custom_data = get_custom_data_highlights(startup_id)
                return {
                    "id": startup_id,
                    "name": item.get("name"),
                    "website": item.get("website"),
                    "details": details,
                    "common_data": {
                        "match": common_data or {}
                    },
                    "custom_highlights": custom_data
                }
    return None

def get_custom_data_highlights(startup_id):
    """
    Fetches the `-2` field (usually marketing or descriptive highlights)
    from the custom-data endpoint.
    """
    url = f"{BASE_URL}/startups/{startup_id}/get-custom-data?type=company_diligence"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        # -2 typically contains a dictionary with 'text' and 'cleared_text'
        highlights = data.get("-2", {})
        return highlights.get("cleared_text", "").strip()
    print(f"Failed to get custom highlights for {startup_id}")
    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")
    return ""
