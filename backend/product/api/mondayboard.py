import os
import json
import requests
from dotenv import load_dotenv
from board_config_db import get_board_id
from utils import normalize_domain

load_dotenv()

MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")
MONDAY_BASE_URL  = os.getenv("MONDAY_API_URL")

HEADERS = {
    "Authorization": MONDAY_API_TOKEN,
    "API-Version": "2023-04",
    "Content-Type": "application/json"
}

def get_board_items_by_domain(board_id: str):
    domain_map = {}
    cursor = None

    while True:
        query = """
        query ($board_id: [ID!], $cursor: String) {
          boards(ids: $board_id) {
            items_page(limit: 100, cursor: $cursor) {
              items {
                id
                column_values {
                  id
                  text
                }
              }
              cursor
            }
          }
        }
        """

        variables = {
            "board_id": [str(board_id)],
            "cursor": cursor
        }

        resp = requests.post(MONDAY_BASE_URL, headers=HEADERS, json={"query": query, "variables": variables})
        resp.raise_for_status()
        page = resp.json()["data"]["boards"][0]["items_page"]

        for item in page["items"]:
            item_id = item["id"]
            for col in item["column_values"]:
                if col["id"] == "text_mksx168g":
                    raw = col["text"].strip()
                    norm = normalize_domain(raw)
                    domain_map[raw.lower()] = item_id
                    domain_map[norm]       = item_id
                    break

        cursor = page.get("cursor")
        if not cursor:
            break

    return domain_map

def get_track_mapping() -> dict[str, int]:
    """
    Queries Monday.com board to extract Track column label mapping.
    Returns:
        A dictionary like {'CleanTech': 105, 'HealthTech': 3, ...}
    """

    board_id = get_board_id("default")
    if not board_id:
        raise ValueError("Missing board id. Configure default in board_config.")

    query = {
        "query": f"""
        query {{
          boards(ids: {board_id}) {{
            columns {{
              id
              settings_str
            }}
          }}
        }}
        """
    }

    response = requests.post(MONDAY_BASE_URL, headers=HEADERS, json=query)
    response.raise_for_status()
    columns = response.json()["data"]["boards"][0]["columns"]

    for column in columns:
        if column["id"] == "color_mksyck4z":
            settings = json.loads(column.get("settings_str", "{}"))
            labels = settings.get("labels", {})
            return {label: int(idx) for idx, label in labels.items()}

    return {}

def find_existing_board_id(board_name: str) -> str | None:
    """
    Return the board ID if a board with the given name exists.
    """
    query = {
        "query": """
        query {
          boards {
            id
            name
          }
        }
        """
    }

    response = requests.post(MONDAY_BASE_URL, headers=HEADERS, json=query)
    response.raise_for_status()
    boards = response.json()["data"]["boards"]

    for board in boards:
        if board["name"].strip().lower() == board_name.strip().lower():
            return board["id"]
    return None

def get_workspace_id_by_name(name: str) -> str:
    query = {
        "query": """
        query {
          workspaces {
            id
            name
          }
        }
        """
    }

    response = requests.post(MONDAY_BASE_URL, headers=HEADERS, json=query)
    response.raise_for_status()

    workspaces = response.json()["data"]["workspaces"]
    for ws in workspaces:
        if ws["name"].strip().lower() == name.strip().lower():
            return ws["id"]

    raise ValueError(f"Workspace with name '{name}' not found.")

def create_board_from_template(board_name: str, template_id: str, workspace_id: str) -> str:
    mutation = {
        "query": """
        mutation ($board_name: String!, $template_id: ID!, $board_kind: BoardKind!, $workspace_id: ID) {
          create_board (board_name: $board_name, template_id: $template_id, board_kind: $board_kind, workspace_id: $workspace_id) {
            id
          }
        }
        """,
        "variables": {
            "board_name": board_name,
            "template_id": str(template_id),
            "board_kind": "private",
            "workspace_id": str(workspace_id)
        }
    }

    response = requests.post(MONDAY_BASE_URL, headers=HEADERS, json=mutation)
    print("Create board response:", response.text)
    response.raise_for_status()
    return response.json()["data"]["create_board"]["id"]


def get_column_id_map(board_id: str) -> dict[str, str]:
    query = {
        "query": f"""
        query {{
          boards(ids: {board_id}) {{
            columns {{
              id
              title
            }}
          }}
        }}
        """
    }

    response = requests.post(MONDAY_BASE_URL, headers=HEADERS, json=query)
    response.raise_for_status()
    columns = response.json()["data"]["boards"][0]["columns"]
    return {col["title"]: col["id"] for col in columns}

def delete_all_items_from_board(board_id: str):
    """
    Fetch all item IDs on the board (paginated) and delete each one.
    """
    cursor = None

    while True:
        query = """
        query ($board_id: [ID!], $cursor: String) {
          boards(ids: $board_id) {
            items_page(limit: 100, cursor: $cursor) {
              items {
                id
              }
              cursor
            }
          }
        }
        """
        variables = {
            "board_id": [str(board_id)],
            "cursor": cursor
        }

        response = requests.post(MONDAY_BASE_URL, headers=HEADERS, json={"query": query, "variables": variables})
        print("Fetch items response:", response.text)
        response.raise_for_status()

        data = response.json()["data"]["boards"][0]["items_page"]
        items = data["items"]
        cursor = data.get("cursor")

        for item in items:
            item_id = item["id"]
            mutation = """
            mutation ($item_id: ID!) {
              delete_item(item_id: $item_id) {
                id
              }
            }
            """
            del_resp = requests.post(
                MONDAY_BASE_URL,
                headers=HEADERS,
                json={"query": mutation, "variables": {"item_id": item_id}}
            )
            print(f"Delete response for {item_id}:", del_resp.text)
            del_resp.raise_for_status()
            print(f"Deleted item ID: {item_id}")

        if not cursor:
            break

def create_group(board_id: str, group_name: str, headers=HEADERS) -> str:
    query = """
    mutation ($board_id: ID!, $group_name: String!) {
      create_group (board_id: $board_id, group_name: $group_name) {
        id
      }
    }
    """
    variables = {
        "board_id": str(board_id),
        "group_name": group_name
    }

    response = requests.post(
        "https://api.monday.com/v2",
        json={"query": query, "variables": variables},
        headers=headers
    )

    data = response.json()
    if "errors" in data:
        error_msg = json.dumps(data["errors"], indent=2)
        raise Exception(f"Failed to create group:\n{error_msg}")

    return data["data"]["create_group"]["id"]

def add_item_to_board(board_id, column_id_map, name, domain, switchpitch_url, hubspot_url, track_label, group_id=None):
    existing_items = get_board_items_by_domain(board_id)
    domain_key = normalize_domain(domain)


    track_mapping = get_track_mapping()
    track_index = track_mapping.get(track_label)

    if track_label and track_index is None:
        print(f"Warning: Track label '{track_label}' not found in board mapping.")

    column_values_dict = {
        column_id_map["Domain Name"]: normalize_domain(domain),
        column_id_map["SwitchPitch Link"]: {
            "url": switchpitch_url,
            "text": switchpitch_url
        },
        column_id_map["HubSpot Link"]: {
            "url": hubspot_url,
            "text": hubspot_url
        },
    }


    if track_index is not None:
        column_values_dict["color_mksyck4z"] = {"index": track_index}

    column_values = json.dumps(column_values_dict)

    if domain_key in existing_items:
      item_id = existing_items[domain_key]
      mutation = """
      mutation ($board_id: ID!, $item_id: ID!, $column_values: JSON!) {
          change_multiple_column_values(board_id: $board_id, item_id: $item_id, column_values: $column_values) {
              id
          }
      }
      """
      variables = {
          "board_id": str(board_id),
          "item_id": item_id,
          "column_values": column_values
      }
      action = "Updated"

    else:
      mutation = """
      mutation ($board_id: ID!, $item_name: String!, $column_values: JSON!""" + (", $group_id: String!" if group_id else "") + """) {
          create_item(board_id: $board_id, item_name: $item_name,""" + (f" group_id: $group_id," if group_id else "") + """ column_values: $column_values) {
              id
          }
      }
      """
      variables = {
          "board_id": str(board_id),
          "item_name": name,
          "column_values": column_values
      }
      if group_id:
          variables["group_id"] = group_id

      action = "Added"

    response = requests.post(MONDAY_BASE_URL, headers=HEADERS, json={"query": mutation, "variables": variables})
    if response.status_code == 200:
        print(f"{action}: {name}")
    else:
        print(f"Failed to {action.lower()} {name}: {response.text}")
