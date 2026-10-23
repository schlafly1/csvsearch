import csv
import io
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    file TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    columns TEXT NOT NULL,
    rows INTEGER NOT NULL,
    encoding TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS cells (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    "column" TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE(file, line, "column")
);
CREATE INDEX IF NOT EXISTS idx_cells_column ON cells("column");
"""


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot decode {path}")  # latin-1 never fails


def parse_csv(text):
    """Yield (line_number, row) where line_number is the physical file line
    on which the record starts (header = 1)."""
    reader = csv.reader(io.StringIO(text, newline=""))
    start = 1
    for row in reader:
        yield start, row
        start = reader.line_num + 1


def unique_names(header):
    seen = {}
    out = []
    for i, name in enumerate(header):
        name = name.strip() or f"col{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        out.append(name)
    return out


def import_file(conn, path):
    """Import one CSV or spreadsheet, replacing earlier rows for the same table(s).
    CSV table name = base file name; each spreadsheet sheet = "book.xlsx:Sheet".
    Returns number of data rows."""
    from .sheets import is_spreadsheet, read_sheets
    base = os.path.basename(path)
    if is_spreadsheet(path):
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        tables = [(f"{base}:{sheet}", rows, ext) for sheet, rows in read_sheets(path)]
        prefix = base + ":"
    else:
        text, enc = read_text(path)
        tables = [(base, parse_csv(text), enc)]
        prefix = None
    total = 0
    with conn:
        if prefix:  # drop sheets from a previous import of this workbook
            n = len(prefix)
            conn.execute("DELETE FROM cells WHERE substr(file, 1, ?) = ?", (n, prefix))
            conn.execute("DELETE FROM files WHERE substr(file, 1, ?) = ?", (n, prefix))
        for name, records, enc in tables:
            total += _load_table(conn, name, path, records, enc)
    return total


def _load_table(conn, name, path, records, enc):
    records = iter(records)
    try:
        _, header = next(records)
    except StopIteration:
        header = []
    cols = unique_names(header)
    nrows = 0
    conn.execute("DELETE FROM cells WHERE file = ?", (name,))
    conn.execute("DELETE FROM files WHERE file = ?", (name,))
    batch = []
    for line, row in records:
        if not any(c.strip() for c in row):
            continue
        nrows += 1
        for i, val in enumerate(row):
            col = cols[i] if i < len(cols) else f"extra{i - len(cols) + 1}"
            batch.append((name, line, col, val))
    conn.executemany(
        'INSERT OR REPLACE INTO cells(file, line, "column", value) VALUES (?,?,?,?)',
        batch,
    )
    conn.execute(
        "INSERT INTO files(file, path, columns, rows, encoding) VALUES (?,?,?,?,?)",
        (name, os.path.abspath(path), ",".join(cols), nrows, enc),
    )
    return nrows


def list_files(conn):
    return [r["file"] for r in conn.execute("SELECT file FROM files ORDER BY file")]


def _where(value, column, file, case_sensitive):
    clauses, params = [], []
    if value:
        if case_sensitive:
            clauses.append("instr(value, ?) > 0")
            params.append(value)
        else:
            clauses.append("lower(value) LIKE ? ESCAPE '\\'")
            params.append("%" + _esc(value.lower()) + "%")
    if column:
        if case_sensitive:
            clauses.append('instr("column", ?) > 0')
            params.append(column)
        else:
            clauses.append("lower(\"column\") LIKE ? ESCAPE '\\'")
            params.append("%" + _esc(column.lower()) + "%")
    if file:
        clauses.append("file = ?")
        params.append(file)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _esc(s):
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(conn, value="", column="", file="", case_sensitive=False, limit=50, offset=0):
    """Return (total_matching_lines, [ {file, line, cells:[(col,val),...]} ])."""
    where, params = _where(value, column, file, case_sensitive)
    sub = f"SELECT DISTINCT file, line FROM cells{where}"
    total = conn.execute(f"SELECT COUNT(*) FROM ({sub})", params).fetchone()[0]
    hits = conn.execute(
        f"{sub} ORDER BY file, line LIMIT ? OFFSET ?", params + [int(limit), int(offset)]
    ).fetchall()
    return total, [
        {"file": h["file"], "line": h["line"], "cells": get_line(conn, h["file"], h["line"])}
        for h in hits
    ]


def get_line(conn, file, line):
    return [
        (r["column"], r["value"])
        for r in conn.execute(
            'SELECT "column", value FROM cells WHERE file = ? AND line = ? ORDER BY rowid',
            (file, int(line)),
        )
    ]
