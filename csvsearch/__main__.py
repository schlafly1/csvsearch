import argparse
import os
import socket
import sys

from . import db as dbm
from .config import ConfigSyntaxError, load_config

DEFAULT_CONFIG = "config.toml"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
ENV_VAR = "CSVSEARCH_CONFIG"
LAN_WARNING = "Warning: anyone on the network can view the data with no login."


def build_parser():
    # -c/--config is accepted both before and after the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", metavar="PATH", default=argparse.SUPPRESS,
                        help=f"config file (default: ${ENV_VAR} or ./{DEFAULT_CONFIG})")
    ap = argparse.ArgumentParser(prog="python -m csvsearch", parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import", parents=[common], help="import files listed in config into SQLite")
    s = sub.add_parser("serve", parents=[common], help="run local web search UI")
    s.add_argument("--host", default=None, metavar="HOST",
                   help=f"bind address (default: [server].host in config, or {DEFAULT_HOST})")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--debug", action="store_true")
    return ap


def resolve_config_path(args, environ=os.environ):
    return getattr(args, "config", None) or environ.get(ENV_VAR) or DEFAULT_CONFIG


def is_localhost(host):
    h = (host or "").strip().lower().strip("[]")
    return h in {"127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"}


def resolve_host(args, cfg=None):
    """CLI --host wins over config [server] host, then 127.0.0.1."""
    h = getattr(args, "host", None)
    if h and str(h).strip():
        return str(h).strip()
    if cfg:
        ch = cfg.get("host")
        if ch:
            return ch
    return DEFAULT_HOST


def resolve_debug(debug, host):
    """Flask debug is allowed only when bound to localhost."""
    debug = bool(debug)
    if debug and not is_localhost(host):
        return False, True
    return debug, False


def lan_ipv4_addresses():
    """Best-effort list of this machine's non-loopback IPv4 addresses."""
    addrs = []

    def add(ip):
        if ip and not ip.startswith("127.") and ip not in addrs:
            addrs.append(ip)

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass
    return addrs


def format_url(host, port):
    h = host
    if ":" in h and not h.startswith("["):
        h = f"[{h}]"
    return f"http://{h}:{port}"


def startup_lines(host, port, lan_addrs=None):
    """Lines printed at serve startup (URLs and any LAN warning)."""
    lines = [f"Listening on {format_url(host, port)}"]
    if host in ("0.0.0.0", "::"):
        lines.append(f"On this machine: {format_url('127.0.0.1', port)}")
        addrs = list(lan_addrs) if lan_addrs is not None else lan_ipv4_addresses()
        if addrs:
            for ip in addrs:
                lines.append(f"On your LAN: {format_url(ip, port)}")
        else:
            lines.append("On your LAN: (could not determine this machine's IPv4 address)")
        lines.append(LAN_WARNING)
    else:
        lines.append(f"Open {format_url(host, port)}")
        if not is_localhost(host):
            lines.append(LAN_WARNING)
    return lines


def main(argv=None):
    args = build_parser().parse_args(argv)
    path = resolve_config_path(args)
    if not os.path.isfile(path):
        print(f"Error: config file not found: {path} (use -c PATH, set {ENV_VAR}, "
              f"or copy config.example.toml to config.toml)", file=sys.stderr)
        sys.exit(1)
    try:
        cfg = load_config(path)
    except ConfigSyntaxError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError) as e:
        print(f"Error: in {path}: {e}", file=sys.stderr)
        sys.exit(1)
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
        host = resolve_host(args, cfg)
        debug, suppressed = resolve_debug(args.debug, host)
        if suppressed:
            print("Note: --debug is ignored because the server is not bound to localhost.",
                  file=sys.stderr)
        for line in startup_lines(host, args.port):
            print(line)
        dbm.connect(cfg["db"]).close()
        create_app(cfg["db"]).run(host=host, port=args.port, debug=debug)


if __name__ == "__main__":
    main()
