import sys, importlib.util, importlib, traceback, os, pathlib

# Ensure /app is first on sys.path
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

print("sys.path (first 5):", sys.path[:5])

# Try product top-level
try:
    import product
    print("product __file__:", getattr(product, "__file__", None))
except Exception:
    print("Could not import product; traceback:")
    traceback.print_exc()

# Locate product.db.core_mapping
spec = importlib.util.find_spec("product.db.core_mapping")
print("find_spec origin:", None if spec is None else spec.origin)

# Scan all .py under /app/product: look for NULs and compile errors
bad_nuls = []
bad_compile = []
root = pathlib.Path("/app/product")
if root.exists():
    for p in root.rglob("*.py"):
        try:
            b = p.read_bytes()
            if b.find(b"\x00") != -1:
                bad_nuls.append(str(p))
            s = b.decode("utf-8")
            compile(s, str(p), "exec")
        except UnicodeDecodeError as e:
            bad_compile.append((str(p), f"decode error: {e!r}"))
        except SyntaxError as e:
            bad_compile.append((str(p), f"syntax error: {e.msg} at {e.filename}:{e.lineno}"))
        except Exception as e:
            bad_compile.append((str(p), f"other error: {e!r}"))
else:
    print("/app/product does not exist.")

print("\nFiles containing NULs:", *bad_nuls, sep="\n- " if bad_nuls else "\n(none)")
print("\nFiles failing decode/compile:", *[f"{p} -> {err}" for p, err in bad_compile], sep="\n- " if bad_compile else "\n(none)")
