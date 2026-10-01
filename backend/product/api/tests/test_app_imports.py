"""
Static-source checks for app.py to catch regressions in module-level imports.
Notably: the top-level `from cycles.routes import bp as cycles_bp` was duplicated
with the in-function import inside create_app(). This test guards against the
top-level duplicate being reintroduced.
"""

import os


APP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app.py",
)


def _read_app_source() -> str:
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_cycles_bp_imported_only_inside_create_app():
    """
    `from cycles.routes import bp as cycles_bp` must appear exactly once,
    and only inside create_app() (i.e. not as a module-level import).
    """
    source = _read_app_source()
    lines = source.splitlines()

    import_occurrences = [
        (idx, line) for idx, line in enumerate(lines, start=1)
        if "from cycles.routes import bp as cycles_bp" in line
    ]

    assert len(import_occurrences) == 1, (
        f"Expected exactly 1 occurrence of cycles_bp import, found "
        f"{len(import_occurrences)}: {import_occurrences}"
    )

    # Ensure the single occurrence is indented (i.e. inside a function),
    # not a top-level statement.
    _, line = import_occurrences[0]
    assert line.startswith((" ", "\t")), (
        "cycles_bp import must be inside create_app() (indented), not at module level."
    )
