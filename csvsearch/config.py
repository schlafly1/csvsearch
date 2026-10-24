import os
import re
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

TOMLDecodeError = tomllib.TOMLDecodeError

_LOC_RE = re.compile(r"^(.*?)\s*\(at line (\d+)(?:,\s*column (\d+))?\)\s*$")
_EOF_RE = re.compile(r"^(.*?)\s*\(at end of document\)\s*$")
_BACKSLASH_HINT = (
    "Hint: in TOML double-quoted strings, '\\' starts an escape sequence. "
    "For Windows paths, use single quotes ('C:\\foo\\bar.csv') or forward slashes (\"C:/foo/bar.csv\")."
)


class ConfigSyntaxError(ValueError):
    """Raised when the TOML config file has a syntax error."""

    def __init__(self, path, lineno, colno, reason, message):
        super().__init__(message)
        self.path = path
        self.lineno = lineno
        self.colno = colno
        self.reason = reason


def format_toml_error(path, text, exc):
    """Format a TOMLDecodeError into a clear multi-line message with line/caret/hints."""
    lineno = getattr(exc, "lineno", None)
    colno = getattr(exc, "colno", None)
    reason = getattr(exc, "msg", None)
    raw = str(exc)

    if lineno is None:
        m = _LOC_RE.match(raw)
        if m:
            reason = m.group(1)
            lineno = int(m.group(2))
            colno = int(m.group(3)) if m.group(3) else None
        else:
            m_eof = _EOF_RE.match(raw)
            if m_eof:
                reason = m_eof.group(1)

    lines = text.splitlines()
    if lineno is None and lines:
        lineno = len(lines)
    reason = (reason or raw).strip()

    if lineno is not None:
        header = f"Error: file {path} has syntax error on line {lineno}: {reason}"
    else:
        header = f"Error: file {path} has syntax error: {reason}"

    out = [header]
    src_line = lines[lineno - 1] if (lineno is not None and 1 <= lineno <= len(lines)) else None
    if src_line is not None:
        out.append(f"  {src_line}")
        if colno is not None and colno >= 1:
            out.append(f"  {' ' * (colno - 1)}^")

    if _looks_like_windows_backslash(reason, src_line):
        out.append(_BACKSLASH_HINT)

    return lineno, colno, reason, "\n".join(out)


def _looks_like_windows_backslash(reason, src_line):
    r = (reason or "").lower()
    if "unescaped '\\'" in r or 'unescaped "\\"' in r:
        return True
    if src_line and "\\" in src_line and '"' in src_line:
        if "escape" in r or "hex" in r or "unicode" in r or "character" in r or "invalid" in r:
            return True
    return False


def _check_unescaped_path_controls(path, text, values):
    """Catch Windows paths like "C:\\foo\\bar.csv" where \\f or \\b parsed as control chars."""
    if not any(isinstance(v, str) and any(ord(c) < 32 for c in v) for v in values):
        return
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        if '"' in line and "\\" in line:
            col = line.index("\\") + 1
            reason = "Unescaped '\\' in double-quoted path (interpreted as control character)"
            msg = "\n".join([
                f"Error: file {path} has syntax error on line {idx}: {reason}",
                f"  {line}",
                f"  {' ' * (col - 1)}^",
                _BACKSLASH_HINT,
            ])
            raise ConfigSyntaxError(path, idx, col, reason, msg)


def load_config(path):
    """Return dict with absolute 'db' and list 'csv_files'."""
    with open(path, "rb") as f:
        raw_bytes = f.read()
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    try:
        data = tomllib.loads(text)
    except TOMLDecodeError as e:
        lineno, colno, reason, msg = format_toml_error(path, text, e)
        raise ConfigSyntaxError(path, lineno, colno, reason, msg) from None

    base = os.path.dirname(os.path.abspath(path))

    def resolve(p):
        p = os.path.expanduser(p)
        return p if os.path.isabs(p) else os.path.join(base, p)

    if "db" not in data:
        raise ValueError("config missing 'db'")
    if not isinstance(data["db"], str) or not data["db"].strip():
        raise ValueError("'db' must be a non-empty string")

    raw_files = data.get("csv_files", data.get("files", []))
    if not isinstance(raw_files, list) or not all(isinstance(p, str) for p in raw_files):
        raise ValueError("'csv_files' must be a list of file path strings")

    _check_unescaped_path_controls(path, text, [data["db"], *raw_files])

    return {
        "db": resolve(data["db"]),
        "csv_files": [resolve(p) for p in raw_files],
    }
