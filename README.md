# csvsearch

Load CSV files and spreadsheets (.xlsx, .xls, .ods) into a SQLite database, then search every cell from a small local web page.

Each cell is stored as one row `(file, line, column, value)`, so you can search for a value across every table and column at once and jump to the full line it came from.

## Requirements

- Python 3.9 or newer (3.11+ recommended)
- Git (to clone)

## Install

### Windows (PowerShell)

```powershell
git clone https://github.com/schlafly1/csvsearch.git
cd csvsearch
python -m venv .venv
.venv\Scripts\Activate.ps1      # cmd.exe: .venv\Scripts\activate.bat
pip install -r requirements.txt
```

If PowerShell refuses to run the activate script, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `.venv\Scripts\python.exe` directly in place of `python`.

### Linux / macOS

```bash
git clone https://github.com/schlafly1/csvsearch.git
cd csvsearch
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Activate the venv in each new terminal before running the commands below.

## Configure

Copy the example and edit it:

```
copy config.example.toml config.toml      # Windows
cp config.example.toml config.toml        # Linux / macOS
```

`config.toml` is a TOML file with two settings:

```toml
# SQLite database to create/use
db = "csvsearch.db"

# Files to import: CSV (.csv or any text) and spreadsheets (.xlsx, .xlsm, .xls, .ods)
csv_files = [
  "examples/people.csv",
  "examples/products.csv",
  "examples/sales.xlsx",
  'C:\data\customers.csv',          # Windows path: use single quotes...
  "C:/data/orders.xlsx",            # ...or forward slashes
  "/home/me/data/inventory.ods",
]
```

- **Relative paths are relative to the folder containing the config file**, not the current directory. `~` is expanded.
- Every CSV must have a header row of column names.
- `config.toml` and `*.db` are listed in `.gitignore`, so your real config and database are never committed. Only `config.example.toml` is in the repo.

### Using a config file from somewhere else

By default csvsearch reads `config.toml` in the current directory. To use a different file:

1. Command-line option `-c PATH` / `--config PATH`, which works before or after the subcommand:
   ```
   python -m csvsearch -c D:\projects\clients.toml import
   python -m csvsearch import --config ~/work/csvsearch.toml
   python -m csvsearch serve -c D:\projects\clients.toml --port 8080
   ```
2. Environment variable `CSVSEARCH_CONFIG`, used when `-c` is not given:
   ```powershell
   $env:CSVSEARCH_CONFIG = "D:\projects\clients.toml"     # PowerShell
   ```
   ```bash
   export CSVSEARCH_CONFIG=~/work/csvsearch.toml           # bash
   ```
3. Otherwise, `./config.toml`.

Precedence: `-c` > `CSVSEARCH_CONFIG` > `./config.toml`. The config file in use is printed at startup.

## Import

```
python -m csvsearch import
```

This reads every file listed in the config into the database. Run it again whenever the files change: re-importing a file replaces all of its old rows.

Details:
- **Table names:** a CSV's table name is its base file name (`people.csv`). Files with the same base name in different folders share a table, and the last one imported wins.
- **Line numbers:** `line` is the file line number. The header is line 1, so data starts at line 2. A record with a multi-line quoted field is numbered by the line it starts on.
- **Encoding:** files are read as UTF-8 (a BOM is fine), falling back to Latin-1.
- **Blank and ragged rows:** blank lines are skipped. Short rows simply have fewer cells, and extra cells beyond the header are stored as columns `extra1`, `extra2`, ...

## Serve and search

```
python -m csvsearch serve                # http://127.0.0.1:5000
python -m csvsearch serve --port 8080
```

Open the address in a browser. The server listens only on 127.0.0.1, so it can't be reached from other machines. Press Ctrl+C to stop it.

The search page has:

- **Value box:** finds cells whose value *contains* the text (substring match). Leave it empty and fill only the column box to list every line that has that column.
- **Column box (optional):** limits matches to columns whose name contains this text, e.g. `email`.
- **Table drop-down:** *All tables* (default), or one CSV file or spreadsheet sheet.
- **Case-sensitive checkbox:** off by default (`boston` matches `Boston`). Tick it for an exact-case match. It applies to the column box too.
- **Results:** one row per matching line, showing the table, line number and the first few `name=value` pairs (long values are shortened). 50 lines per page, with prev/next links.
- **Click a result row** to see the whole line as a two-column name/value table.
- **Export database (.db):** downloads the SQLite file, which you can open with any SQLite tool (e.g. DB Browser for SQLite or `sqlite3`).
- **Export results (CSV):** downloads all lines matching the current search (not just the current page) as `file,line,column,value` rows.

## Spreadsheets

`.xlsx`/`.xlsm` (via openpyxl), `.xls` (via xlrd) and `.ods` (via pandas + odfpy) can be listed in `csv_files` alongside CSVs.

- **One table per sheet:** each sheet becomes its own table named `<file>:<sheet>`, e.g. `sales.xlsx:Orders`. The sheet name is included even if the workbook has only one sheet.
- **Header and line numbers:** the first row holds the column names, and `line` is the spreadsheet row number (header = row 1). Fully blank rows are skipped.
- **Values are stored as text:**
  - Whole-number floats lose the `.0` (`3.0` becomes `3`).
  - Dates become ISO format, e.g. `2026-01-15`, or `2026-01-15 13:45:00` when there is a time.
  - True/false values become `TRUE`/`FALSE`.
  - Formulas are stored as their last saved value.
- **Re-importing a workbook** replaces all of its sheets, and sheets that were deleted from the workbook are removed.

`examples/make_spreadsheets.py` regenerates the sample spreadsheets. Writing the `.xls` file needs `pip install xlwt`; reading `.xls` doesn't.

## Database layout

| table | columns |
|---|---|
| `cells` | `file, line, column, value`, `UNIQUE(file, line, column)`, index on `column` |
| `files` | `file, path, columns, rows, encoding, imported_at`, one row per table |

Example query: `SELECT * FROM cells WHERE value LIKE '%boston%';`

## Quick start with the samples

```
cp config.example.toml config.toml        # Windows: copy ...
python -m csvsearch import
python -m csvsearch serve
```

Then browse to http://127.0.0.1:5000 and search for `boston`.

## Tests

```
pytest
```

## License

MIT, see [LICENSE](LICENSE).
