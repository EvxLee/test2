import os
import requests
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

BASE_URL = os.getenv("SWITCHPITCH_API_URL")
BEARER_TOKEN = os.getenv("SWITCHPITCH_BEARER_TOKEN")

print(f"API Base URL: {BASE_URL}")
print(f"Token Loaded: {'Yes' if BEARER_TOKEN else 'No'}")

# Full URL, to be normalized
domain_name = "https://www.example.com"

# Just the domain name to be used in the keyword search
domain_keyword = "example.com"
# Calling switchpitch endpoint using keywords[] parameter, which tells the API
# to return startups related to teh keywork. Returns at most 25 results
search_url = f"{BASE_URL}/search/get-list?keywords[]={domain_keyword}&limit=25"

print(f"Full request URL: {search_url}")

# Bearer token added to HTTP Authoraization header
headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}"
}
# Send GET request to API using requests.get
response = requests.get(search_url, headers=headers)
print(f"Status Code: {response.status_code}")
# If the API call fails (token is bad, server is down), it exits with an error message
if response.status_code != 200:
    print("Failed to fetch from API")
    print(response.text)
    exit()

# Data is a list of startup objects related to the keyword
data = response.json()
# Parses JSON from the API response and prints it
print(f"Raw response: {data}")

# Takes the URL and extracts the base domain removing any protocal and www.
def normalize_domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "").lower()
    except Exception:
        return url.lower()

# Noramilized version of the input
target_domain = normalize_domain(domain_name)

results = data

# Looping over each result in the API response and checking if their website
# matches target domain after nomalizing both
matched = None
for item in results:
    website = item.get("website", "")
    if normalize_domain(website) == target_domain:
        matched = item
        break

# If no match is found, message is printed, otherwise full raw startup object is printed
if not matched:
    print("No matching startup found for that domain.")
else:
    print("Matched Startup (raw):")
    print(matched)

	# From the matched result, extract startup ID
    startup_id = matched.get("id")
  # Using startup ID, call endpoint to get common data of that startup
    details_url = f"{BASE_URL}/startups/{startup_id}/get-common-data"
    details_response = requests.get(details_url, headers=headers)

    if details_response.status_code == 200:
        print("\nCommon Data:")
        print(details_response.json())
    else:
        print("Failed to retrieve common data.")
        print(details_response.text)
