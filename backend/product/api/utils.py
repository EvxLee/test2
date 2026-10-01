from urllib.parse import urlparse
import re
import requests

# def normalize_domain(url):
#     if not url:
#         return ""
#     if not url.startswith("http"):
#         url = "http://" + url
#     parsed = urlparse(url)
#     domain = parsed.netloc or parsed.path
#     return domain.lower().replace("www.", "")

def normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    if domain.startswith("http://") or domain.startswith("https://"):
        domain = urlparse(domain).netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.split('/')[0]

def resolve_redirected_domain(domain: str) -> str:
    """
    Try to resolve a redirected domain via HEAD request.
    Returns the final domain after redirects.
    """
    try:
        url = f"https://{domain}"
        resp = requests.head(url, allow_redirects=True, timeout=5)
        final_url = resp.url
        match = re.search(r"https?://([^/]+)", final_url)
        if match:
            resolved_domain = match.group(1)
            print(f"Resolved redirect: {domain} → {resolved_domain}")
            return resolved_domain
    except requests.RequestException as e:
        print(f"Redirect resolution failed for {domain}: {e}")
    return domain  # Fallback to original if resolution fails
