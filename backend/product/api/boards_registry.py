from monday_pull.boards.gced import cycle4, cycle5
from monday_pull.boards.incubation import startups_ai, startups_cleantech, startups_health
from monday_pull.boards.marketing import new_ventures_projs
from monday_pull.boards import contract_status, new_venture_proposals, korean
from board_config_db import get_all_boards

# Maps mapper_type string → Python ETL module
MAPPER_REGISTRY = {
    "gced":                  cycle4,
    "gced_cycle4":           cycle4,
    "gced_cycle5":           cycle5,
    "incubation_ai":         startups_ai,
    "incubation_cleantech":  startups_cleantech,
    "incubation_health":     startups_health,
    "new_ventures":          new_ventures_projs,
    "contract_status":       contract_status,
    "new_venture_proposals": new_venture_proposals,
    "korean":                korean,
}


def _build_registry() -> dict:
    try:
        boards = get_all_boards()
        return {
            b["board_key"]: (MAPPER_REGISTRY.get(b["mapper_type"]), b["board_id"])
            for b in boards
            if b["board_id"] and b["mapper_type"]
        }
    except Exception as e:
        print(f"WARNING: Failed to load board registry from DB ({e}). Falling back to empty registry.")
        return {}


BOARD_REGISTRY = _build_registry()
