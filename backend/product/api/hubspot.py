import os
import requests
from dotenv import load_dotenv
from utils import normalize_domain

load_dotenv()

HUBSPOT_API_TOKEN = os.getenv("HUBSPOT_API_TOKEN")
HUBSPOT_BASE_URL = os.getenv("HUBSPOT_BASE_URL")
HUBSPOT_PORTAL_ID = os.getenv("HUBSPOT_PORTAL_ID")

def search_hubspot_company(domain):
    domain = normalize_domain(domain)
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/companies/search"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "domain",
                        "operator": "EQ",
                        "value": domain
                    }
                ]
            }
        ],
        "properties": ["name", "domain"]
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        return None

    results = response.json().get("results", [])
    if not results:
        return None

    company = results[0]
    name = company.get("properties", {}).get("name", "")
    company_id = company.get("id")
    hubspot_url = f"https://app.hubspot.com/contacts/{HUBSPOT_PORTAL_ID}/company/{company_id}"

    return name, hubspot_url
