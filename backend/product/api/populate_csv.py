import os
import pandas as pd
import pprint
import re
from dotenv import load_dotenv
from switchpitch import search_switchpitch, get_common_data, get_custom_data_highlights
from hubspot import search_hubspot_company
from utils import normalize_domain

load_dotenv()

csv_path = "data/All_Sample_ExcelList - Sample_ExcelList - Sheet1.csv.csv"
domain_col = "Domain Name"
company_col = "Company Name"
track_col = "Track"
output_dir = "output"

filename = os.path.splitext(os.path.basename(csv_path))[0]
output_filename = f"{filename}_all_consolidated.csv"
output_path = os.path.join(output_dir, output_filename)
os.makedirs(output_dir, exist_ok=True)

df = pd.read_csv(csv_path, encoding='utf-8-sig')
enriched_rows = []

def clean_excel_field(value: str) -> str:
    if not isinstance(value, str):
        return value
    cleaned = value.strip()
    cleaned = re.sub(r'^[=@\-]+', '', cleaned)
    return cleaned

def extract_common_fields(match: dict) -> dict:
    def safe_get(key, default=""):
        return match.get(key, default)

    def join_names(key):
        return ", ".join([item.get("name", "") for item in match.get(key, [])])

    location_raw = match.get("location", {})

    if isinstance(location_raw, list):
        location = location_raw[0] if location_raw else {}
    elif isinstance(location_raw, dict):
        location = location_raw
    else:
        location = {}

    return {
        "Website": safe_get("website"),
        "Short Description": safe_get("short_description"),
        "Description": safe_get("description"),
        "Stage": safe_get("stage"),
        "Total Raised": safe_get("total_raised"),
        "Founded": safe_get("founded"),
        "Revenue Range": safe_get("revenue_range"),
        "Employees": safe_get("employees"),
        "Min Employees": safe_get("num_employees_min"),
        "Max Employees": safe_get("num_employees_max"),
        "City": location.get("city", ""),
        "State/Region": location.get("state", location.get("region", "")),
        "Country": location.get("country", ""),
        "Continent": location.get("continent", ""),
        "Categories": join_names("categories"),
        "LinkedIn": safe_get("linkedin_url"),
        "Twitter": safe_get("twitter_url"),
        "Facebook": safe_get("facebook_url"),
        "Features": clean_excel_field(safe_get("features")),
        "Clients": ", ".join(match.get("clients", [])),
        "Investors": join_names("investors"),
        "Last Funding Date": safe_get("last_funding_date")
    }

for _, row in df.iterrows():
    raw_domain = str(row.get(domain_col, "")).strip()
    company_name = str(row.get(company_col, "")).strip()
    track = str(row.get(track_col, "")).strip()

    if not raw_domain:
        continue

    domain = normalize_domain(raw_domain)
    print(f"\n→ Processing: {domain}")

    # Initialize base row
    row_data = {
        "Company Name": company_name,
        "Domain Name": domain,
        "SwitchPitch Link": "",
        "Hubspot Link": "",
        "Track": track,
        "Website": "",
        "Short Description": "",
        "Description": "",
        "Stage": "",
        "Total Raised": "",
        "Founded": "",
        "Revenue Range": "",
        "Employees": "",
        "Min Employees": "",
        "Max Employees": "",
        "City": "",
        "State/Region": "",
        "Country": "",
        "Continent": "",
        "Categories": "",
        "LinkedIn": "",
        "Twitter": "",
        "Facebook": "",
        "Features": "",
        "Clients": "",
        "Investors": "",
        "Last Funding Date": "",
        "Highlights": ""
    }

    sp_result = search_switchpitch(domain)
    if sp_result:
        row_data["Company Name"] = sp_result.get("name", company_name)
        startup_id = sp_result.get("id")

        if startup_id:
            row_data["SwitchPitch Link"] = f"https://app.switchpitch.com/startups/{startup_id}"
            common_data_response = get_common_data(startup_id)
            custom_highlights = get_custom_data_highlights(startup_id)
            if custom_highlights:
                row_data["Highlights"] = custom_highlights
            if isinstance(common_data_response, dict):
                match = common_data_response
                extracted = extract_common_fields(match)
                row_data.update(extracted)
            pprint.pprint(row_data)

    hs_result = search_hubspot_company(domain)
    if hs_result:
        hs_name, hs_url = hs_result
        if hs_name:
            row_data["Company Name"] = hs_name
        if hs_url:
            row_data["Hubspot Link"] = hs_url

    enriched_rows.append(row_data)

# Final column order
COLUMNS = [
    "Company Name", "Domain Name", "SwitchPitch Link", "Hubspot Link", "Track",
    "Website", "Short Description", "Description", "Stage", "Total Raised",
    "Founded", "Revenue Range", "Employees", "Min Employees", "Max Employees",
    "City", "State/Region", "Country", "Continent", "Categories", "LinkedIn",
    "Twitter", "Facebook", "Features", "Clients", "Investors", "Last Funding Date", "Highlights"
]

# Save to CSV
enriched_df = pd.DataFrame(enriched_rows, columns=COLUMNS)
enriched_df.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"\nOutput saved to: {output_path}")
