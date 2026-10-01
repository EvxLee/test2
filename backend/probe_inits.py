import os, sys

def probe(path):
    try:
        with open(path, "rb") as f:
            b = f.read()
        nul_idx = b.find(b"\x00")
        print(path, "exists:", True, "size:", len(b), "nul_idx:", nul_idx)
    except Exception as e:
        print(path, "ERROR:", repr(e))

for p in ("/app/product/__init__.py", "/app/product/db/__init__.py"):
    probe(p)
