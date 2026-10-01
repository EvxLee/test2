import os, json, time, random, requests
from dotenv import load_dotenv

load_dotenv()
MONDAY_API_URL   = os.getenv("MONDAY_API_URL")
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")

HEADERS = {
    "Authorization": MONDAY_API_TOKEN,
    "API-Version": "2023-04",
    "Content-Type": "application/json",
}

RETRY_STATUSES = {429, 500, 502, 503, 504}

def _backoff(attempt: int) -> float:
    return 0.5 * (2 ** attempt) + random.uniform(0, 0.2)

def _is_transient_graphql(errors: list) -> bool:
    msg = " ".join(e.get("message", "") for e in errors)
    return any(
        key in msg.lower()
        for key in ("rate limit", "complexity budget", "server busy", "temporarily unavailable")
    )

def gql(query: str, variables: dict | None = None) -> dict:
    body = {"query": query, "variables": variables or {}}
    last_resp = None
    for attempt in range(5):
        resp = requests.post(MONDAY_API_URL, headers=HEADERS, json=body, timeout=25)
        last_resp = resp

        # HTTP-layer retryables
        if resp.status_code in RETRY_STATUSES:
            ra = resp.headers.get("Retry-After")
            delay = float(ra) if ra else _backoff(attempt)
            time.sleep(delay)
            continue

        # If non-retryable HTTP error, surface JSON/text for debugging
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            try:
                err_body = resp.json()
            except Exception:
                err_body = resp.text
            raise RuntimeError(f"HTTP {resp.status_code} from Monday: {err_body}") from e

        data = resp.json()
        # GraphQL errors (200 + "errors")
        if "errors" in data:
            errs = data["errors"]
            if attempt < 4 and _is_transient_graphql(errs):
                time.sleep(_backoff(attempt))
                continue
            raise RuntimeError(f"GraphQL error: {json.dumps(errs, ensure_ascii=False)}")

        return data["data"]

    raise RuntimeError(f"GraphQL failed after retries. Last response: {getattr(last_resp,'text',None)}")
