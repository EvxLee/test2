"""
spaces.py — DigitalOcean Spaces (S3-compatible) file service layer.

All DO Spaces I/O goes through this module. Never call boto3 directly outside here.

Environment variables required:
    DO_SPACES_KEY       Access key ID
    DO_SPACES_SECRET    Secret access key
    DO_SPACES_BUCKET    Bucket name (default: example-atlas-storage)
    DO_SPACES_ENDPOINT_URL  Preferred endpoint URL/host
    DO_SPACES_REGION_NAME   Preferred region slug

Legacy aliases still supported:
    DO_SPACES_ENDPOINT
    DO_SPACES_REGION
"""

import mimetypes
import os
import urllib.request
import urllib.error

import boto3
from botocore.exceptions import ClientError

_client = None


def _endpoint_url() -> str:
    endpoint = (
        os.getenv("DO_SPACES_ENDPOINT_URL")
        or os.getenv("DO_SPACES_ENDPOINT")
        or "sfo3.digitaloceanspaces.com"
    )
    return endpoint if endpoint.startswith("http") else f"https://{endpoint}"


def _region_name() -> str:
    return (
        os.getenv("DO_SPACES_REGION_NAME")
        or os.getenv("DO_SPACES_REGION")
        or "sfo3"
    )


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=_endpoint_url(),
            region_name=_region_name(),
            aws_access_key_id=os.getenv("DO_SPACES_KEY"),
            aws_secret_access_key=os.getenv("DO_SPACES_SECRET"),
        )
    return _client


def _bucket() -> str:
    return os.getenv("DO_SPACES_BUCKET", "example-atlas-storage")


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def upload(file_bytes: bytes, key: str, content_type: str | None = None) -> str:
    """Upload *file_bytes* to Spaces under *key*. Returns the key."""
    ct = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
    _get_client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=file_bytes,
        ContentType=ct,
    )
    return key


def download(key: str) -> bytes:
    """Download the object at *key* and return its bytes."""
    resp = _get_client().get_object(Bucket=_bucket(), Key=key)
    return resp["Body"].read()


def list_objects(prefix: str) -> list[dict]:
    """List objects whose key starts with *prefix*. Returns S3-style dicts."""
    resp = _get_client().list_objects_v2(Bucket=_bucket(), Prefix=prefix)
    return resp.get("Contents", [])


def delete(key: str) -> None:
    """Delete the object at *key* from the bucket."""
    _get_client().delete_object(Bucket=_bucket(), Key=key)


def presign(key: str, expires_in: int = 3600) -> str:
    """Return a pre-signed GET URL for *key*, valid for *expires_in* seconds."""
    return _get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=expires_in,
    )


def key_exists(key: str) -> bool:
    """Return True if an object at *key* already exists in the bucket."""
    try:
        _get_client().head_object(Bucket=_bucket(), Key=key)
        return True
    except ClientError:
        return False


# ---------------------------------------------------------------------------
# Monday.com file ingestion helper
# ---------------------------------------------------------------------------

def _download_file(url: str, monday_api_token: str | None = None) -> bytes | None:
    """
    Download bytes from *url*.  If the first attempt fails, retry with a
    Monday API Bearer token (for files on private boards whose public_url
    has expired or requires auth).  Returns None if both attempts fail.
    """
    for use_auth in (False, True):
        if use_auth and not monday_api_token:
            break
        headers = {"User-Agent": "Atlas/1.0"}
        if use_auth:
            headers["Authorization"] = f"Bearer {monday_api_token}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception:
            if not use_auth:
                continue  # try again with auth
    return None


def upload_monday_files(
    cur,
    conn,
    board_id: str,
    files_payload: list[dict],
) -> dict:
    """
    For each file in *files_payload*:
      - Skip if the Spaces key already exists (idempotent).
      - Download bytes from ``public_url``; fall back to ``url`` with the
        Monday API token if the first attempt fails.
      - Upload to Spaces under ``monday/<board_id>/<asset_id>/<file_name>``.
      - UPDATE monday.files SET spaces_key = ... WHERE monday_file_id = ...

    Requires the env var ``MONDAY_API_TOKEN`` for the auth fallback.

    Returns {"uploaded": n, "skipped": n, "failed": n}.
    """
    monday_token = os.getenv("MONDAY_API_TOKEN")
    uploaded = skipped = failed = 0

    for f in files_payload:
        asset_id = f.get("asset_id")
        public_url = f.get("public_url") or f.get("url") or ""
        file_name = f.get("file_name") or "unknown"

        if not asset_id or not public_url:
            continue

        spaces_key = f"monday/{board_id}/{asset_id}/{file_name}"

        if key_exists(spaces_key):
            # File already in Spaces — ensure the DB row reflects it.
            cur.execute(
                """
                UPDATE monday.files
                   SET spaces_key = %s, updated_at = NOW()
                 WHERE monday_file_id = %s
                   AND spaces_key IS NULL
                """,
                (spaces_key, str(asset_id)),
            )
            conn.commit()
            skipped += 1
            continue

        file_bytes = _download_file(public_url, monday_token)
        if file_bytes is None:
            print(
                f"[Spaces] WARNING: could not download {file_name} "
                f"(asset {asset_id}) — skipping",
                flush=True,
            )
            failed += 1
            continue

        try:
            upload(file_bytes, spaces_key)
            cur.execute(
                """
                UPDATE monday.files
                   SET spaces_key = %s, updated_at = NOW()
                 WHERE monday_file_id = %s
                """,
                (spaces_key, str(asset_id)),
            )
            conn.commit()
            uploaded += 1
        except Exception as exc:
            print(
                f"[Spaces] WARNING: could not upload {file_name} "
                f"(asset {asset_id}): {exc}",
                flush=True,
            )
            conn.rollback()
            failed += 1

    print(
        f"[Spaces] board {board_id}: "
        f"uploaded={uploaded}, skipped={skipped}, failed={failed}",
        flush=True,
    )
    return {"uploaded": uploaded, "skipped": skipped, "failed": failed}
