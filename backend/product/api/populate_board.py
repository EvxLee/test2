import os
import csv
from dotenv import load_dotenv
from urllib.parse import urlparse

from switchpitch import search_switchpitch
from hubspot import search_hubspot_company
from mondayboard import add_item_to_board
from utils import normalize_domain

load_dotenv()

csv_path = "data/Dealflow_Cleaned - Sheet1.csv"
domain_col = "Domain Name"

with open(csv_path, mode='r', encoding='utf-8-sig') as file:
    reader = csv.DictReader(file)
    print(f"Using domain column: {domain_col}")

    for row in reader:
        raw_domain = row.get(domain_col, "").strip()
        company_name = row.get("Company Name", "").strip()
        if not raw_domain:
            continue

        domain = normalize_domain(raw_domain)
        print(f"\n→ Processing: {domain}")

        sp_match = search_switchpitch(domain)
        hs_match = search_hubspot_company(domain)

        name = company_name
        switchpitch_url = ""
        hubspot_url = ""

        if sp_match:
            name = sp_match.get("name", name)
            switchpitch_url = f"https://app.switchpitch.com/startups/{sp_match.get('id')}"

        if hs_match:
            hs_name, hubspot_url = hs_match
            name = hs_name or name

        track_label = row.get("Track", "").strip()

        print(f"{(name, domain, switchpitch_url, hubspot_url, track_label)}")

        add_item_to_board(
            name,
            raw_domain,
            switchpitch_url,
            hubspot_url,
            track_label,
        )
