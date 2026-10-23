# csvsearch

Import CSV files into a SQLite database (one row per cell) and search them from a small local web page.

## Database layout

- `cells(file, line, column, value)` with `UNIQUE(file, line, column)` — `file` is the base file name, `line` is the file line number (header = line 1, so data starts at line 2; for multi-line quoted fields it is the line the record starts on), `column` is the header name.
- `files(file, path, columns, rows, encoding, imported_at)` — one row per imported CSV.
- Index on `cells(column)`.

Re-importing a file replaces all its rows. Files are decoded as UTF-8 (BOM ok), falling back to Latin-1. Ragged rows are handled: missing cells are omitted, extra cells are stored as `extra1`, `extra2`, ...  Blank lines are skipped.

## Install

```
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

## Configure

```
copy config.example.toml config.toml     # or: cp config.example.toml config.toml
```

Edit `config.toml`: `db` is the SQLite path and `csv_files` lists the CSVs. Relative paths are relative to the config file. `config.toml` is git-ignored.

## Use

```
python -m csvsearch import            # (re)load CSVs into the db
python -m csvsearch serve             # http://127.0.0.1:5000
python -m csvsearch -c other.toml serve --port 8080
```

The page has a value search (substring), an optional column-name filter, a table drop-down (default All tables), and a case-sensitive checkbox (default insensitive). Results show one row per matching line; click a row to see the whole line as name/value pairs. Buttons export the `.db` file or the current results as CSV.

## Tests

```
pytest
```

## License

MIT
