# test2 (temporary snapshot)

Snapshot of two repositories (Atlas frontend and backend), copied from a local checkout with git history squashed to a single commit. Hostnames, bucket names, Monday.com board ids, and organisation/person names in this copy have been replaced with placeholders.

- `frontend/` - tracked files of the frontend repo at commit 7f87806 (branch develop, 2026-04-28)
- `backend/`  - tracked files of the backend repo at commit 8fc4c89 (branch develop, 2026-04-28)
- `my-commits/` - the three backend commits authored by Evan Lee (EvxLee), exported with git format-patch

Only git-tracked files are included; ignored files such as .env are not. This repository is temporary.

Deviations from a byte-for-byte copy: the hardcoded bearer token on line 3 of backend/test_backend.sh was replaced with an environment-variable placeholder, and internal hostnames, bucket and board identifiers, document titles, and personal names were replaced with neutral placeholders before publishing. Internal planning documents, CI and deployment configs, logs, evaluation fixtures, and an unrelated sample database were removed.
