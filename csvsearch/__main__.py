import argparse
import os
import sys

from . import db as dbm
from .config import load_config

DEFAULT_CONFIG = "config.toml"
ENV_VAR = "CSVSEARCH_CONFIG"


def build_parser():
    # -c/--config is accepted both before and after the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", metavar="PATH", default=argparse.SUPPRESS,
                        help=f"config file (default: ${ENV_VAR} or ./{DEFAULT_CONFIG})")
    ap = argparse.ArgumentParser(prog="python -m csvsearch", parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import", parents=[common], help="import files listed in config into SQLite")
    s = sub.add_parser("serve", parents=[common], help="run local web search UI")
    s.add_argument("--port", type=int, default=5000)
    s.add_argument("--debug", action="store_true")
    return ap


def resolve_config_path(args, environ=os.environ):
    return getattr(args, "config", None) or environ.get(ENV_VAR) or DEFAULT_CONFIG


def main(argv=None):
    args = build_parser().parse_args(argv)
    path = resolve_config_path(args)
    if not os.path.isfile(path):
        sys.exit(f"config file not found: {path} (use -c PATH, set {ENV_VAR}, "
                 f"or copy config.example.toml to config.toml)")
    cfg = load_config(path)
    print(f"config: {os.path.abspath(path)}")
    if args.cmd == "import":
        conn = dbm.connect(cfg["db"])
        for p in cfg["csv_files"]:
            try:
                n = dbm.import_file(conn, p)
                print(f"imported {p}: {n} rows")
            except Exception as e:
                print(f"error {p}: {e}", file=sys.stderr)
        conn.close()
        print(f"database: {cfg['db']}")
    else:
        from .web import create_app
        dbm.connect(cfg["db"]).close()
        create_app(cfg["db"]).run(host="127.0.0.1", port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
