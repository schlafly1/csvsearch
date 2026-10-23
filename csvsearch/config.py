import os
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


def load_config(path):
    """Return dict with absolute 'db' and list 'csv_files'."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    base = os.path.dirname(os.path.abspath(path))

    def resolve(p):
        p = os.path.expanduser(p)
        return p if os.path.isabs(p) else os.path.join(base, p)

    if "db" not in data:
        raise ValueError("config missing 'db'")
    return {
        "db": resolve(data["db"]),
        "csv_files": [resolve(p) for p in data.get("csv_files", [])],
    }
