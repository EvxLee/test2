import os
import csv
import pandas as pd
from dotenv import load_dotenv
from switchpitch import search_switchpitch
from hubspot import search_hubspot_company
from mondayboard import (
    add_item_to_board,
    create_board_from_template,
    find_existing_board_id,
    get_column_id_map,
    create_group,
    get_workspace_id_by_name
)
from utils import normalize_domain, resolve_redirected_domain

load_dotenv()
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")

def populate_board_from_csv(csv_path: str, board_name: str, workspace_name: str):
    domain_col = "Domain Name"

    # Load CSV into DataFrame
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    if "Track" not in df.columns:
        raise ValueError("The CSV file must contain a 'Track' column.")

    # Check if board already exists
    existing_board_id = find_existing_board_id(board_name)
    if existing_board_id:
        raise ValueError(f"Board Name: '{board_name}' already exists. Please choose a different name.")

    # Get workspace ID from name
    workspace_id = get_workspace_id_by_name(workspace_name)

    # Create the new board in the workspace
    MONDAY_BOARD_ID = create_board_from_template(board_name, template_id="30000001", workspace_id=workspace_id)
    column_id_map = get_column_id_map(MONDAY_BOARD_ID)

    # Create groups by Track
    track_to_group_id = {}
    for track in df["Track"].dropna().unique():
        try:
            group_id = create_group(board_id=MONDAY_BOARD_ID, group_name=track[:20])
            track_to_group_id[track] = group_id
        except Exception as e:
            print(f"Could not create group for track '{track}': {e}")

    # Process each row
    for _, row in df.iterrows():
        raw_domain = str(row.get(domain_col, "")).strip()
        company_name = str(row.get("Company Name", "")).strip()
        if not raw_domain:
            continue

        domain = normalize_domain(raw_domain)
        print(f"\n→ Processing: {domain}")

        sp_result = search_switchpitch(domain)
        hs_match = search_hubspot_company(domain)

        print(sp_result)
        print(hs_match)

        name = company_name
        switchpitch_url = ""
        hubspot_url = ""

        if not sp_result and domain:
            resolved_domain = resolve_redirected_domain(domain)
            if resolved_domain != domain:
                fallback_result = search_switchpitch(resolved_domain)
                print(f"Redirected using resolved domain: {resolved_domain}")
                if fallback_result:
                    sp_result = fallback_result
                    domain = resolved_domain

        if sp_result:
            switchpitch_url = f"https://app.switchpitch.com/startups/{sp_result['id']}"
            name = sp_result.get("name", name)

        if hs_match:
            hs_name, hubspot_url = hs_match
            name = hs_name or name

        track_label = row.get("Track", "").strip()
        group_id = track_to_group_id.get(track_label)


        # Flag companies with no links found
        if not switchpitch_url and not hubspot_url:
            print(f"WARNING: No SwitchPitch or HubSpot data found for '{name}' ({domain}).")
            print(f"Please double-check if the domain name is correct.")

        print((name, domain, switchpitch_url, hubspot_url, track_label))

        add_item_to_board(
            MONDAY_BOARD_ID,
            column_id_map,
            name,
            raw_domain,
            switchpitch_url,
            hubspot_url,
            track_label,
            group_id=group_id
        )
