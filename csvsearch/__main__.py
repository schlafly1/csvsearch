import argparse
import sys

from . import db as dbm
from .config import load_config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m csvsearch")
    ap.add_argument("-c", "--config", default="config.toml", help="config file (default config.toml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import", help="import CSV files listed in config into SQLite")
    s = sub.add_parser("serve", help="run local web search UI")
    s.add_argument("--port", type=int, default=5000)
    s.add_argument("--debug", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.cmd == "import":
        conn = dbm.connect(cfg["db"])
        for path in cfg["csv_files"]:
            try:
                n = dbm.import_file(conn, path)
                print(f"imported {path}: {n} rows")
            except OSError as e:
                print(f"error {path}: {e}", file=sys.stderr)
        conn.close()
        print(f"database: {cfg['db']}")
    else:
        from .web import create_app
        dbm.connect(cfg["db"]).close()
        create_app(cfg["db"]).run(host="127.0.0.1", port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
