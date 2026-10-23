# csvsearch

Import CSV files and spreadsheets (.xlsx, .xls, .ods) into a SQLite database (one row per cell) and search them from a small local web page.

## Database layout

- `cells(file, line, column, value)` with `UNIQUE(file, line, column)` — `file` is the base file name, `line` is the file line number (header = line 1, so data starts at line 2; for multi-line quoted fields it is the line the record starts on), `column` is the header name.
- `files(file, path, columns, rows, encoding, imported_at)` — one row per imported CSV.
- Index on `cells(column)`.

Re-importing a file replaces all its rows. Files are decoded as UTF-8 (BOM ok), falling back to Latin-1. Ragged rows are handled: missing cells are omitted, extra cells are stored as `extra1`, `extra2`, ...  Blank lines are skipped.

## Spreadsheets

`.xlsx`/`.xlsm` (openpyxl), `.xls` (xlrd) and `.ods` (pandas + odfpy) may be listed in `csv_files` too. Each sheet becomes its own table named `<file>:<sheet>` (e.g. `sales.xlsx:Orders`), even if the workbook has only one sheet. The first row holds column names and `line` is the spreadsheet row number (header = row 1). Fully blank rows are skipped. Values are stored as text: whole-number floats lose the `.0` (`3.0` -> `3`), dates become ISO (`2026-01-15`, or `2026-01-15 13:45:00` with a time), booleans become `TRUE`/`FALSE`, and formulas are stored as their last saved value. Re-importing a workbook replaces all its sheets (sheets that were deleted are removed).

`examples/make_spreadsheets.py` regenerates the sample spreadsheets (writing `.xls` needs `pip install xlwt`, not needed for reading).

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
