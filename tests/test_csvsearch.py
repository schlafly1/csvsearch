import os

import pytest

from csvsearch import db as dbm
from csvsearch.web import create_app


@pytest.fixture
def setup(tmp_path):
    a = tmp_path / "a.csv"
    a.write_text("name,city\nAlice,Boston\nBob,<b>Denver</b>\n\nCarol,boston,extra\nDan\n", encoding="utf-8")
    b = tmp_path / "b.csv"
    b.write_bytes("item,note\nCaf\xe9,hot\n".encode("latin-1"))
    dbp = str(tmp_path / "t.db")
    conn = dbm.connect(dbp)
    dbm.import_file(conn, str(a))
    dbm.import_file(conn, str(b))
    return conn, dbp, str(a)


def test_import_lines_and_ragged(setup):
    conn, _, _ = setup
    assert dbm.get_line(conn, "a.csv", 2) == [("name", "Alice"), ("city", "Boston")]
    assert dbm.get_line(conn, "a.csv", 5) == [("name", "Carol"), ("city", "boston"), ("extra1", "extra")]
    assert dbm.get_line(conn, "a.csv", 6) == [("name", "Dan")]
    assert dbm.get_line(conn, "b.csv", 2)[0] == ("item", "Café")


def test_reimport_replaces(setup):
    conn, _, path = setup
    with open(path, "w") as f:
        f.write("name\nZed\n")
    dbm.import_file(conn, path)
    assert conn.execute("SELECT COUNT(*) FROM cells WHERE file='a.csv'").fetchone()[0] == 1


def test_search_case(setup):
    conn, _, _ = setup
    assert dbm.search(conn, value="boston")[0] == 2
    assert dbm.search(conn, value="boston", case_sensitive=True)[0] == 1
    assert dbm.search(conn, value="o", column="city", file="a.csv")[0] == 2
    assert dbm.search(conn, value="%")[0] == 0


def test_web(setup):
    _, dbp, _ = setup
    c = create_app(dbp).test_client()
    r = c.get("/?q=denver")
    assert r.status_code == 200 and b"&lt;b&gt;Denver" in r.data and b"<b>Denver" not in r.data
    assert b"All tables" in r.data
    r = c.get("/line?file=a.csv&line=3")
    assert r.status_code == 200 and b"&lt;b&gt;" in r.data
    assert c.get("/line?file=a.csv&line=99").status_code == 404
    r = c.get("/export/results.csv?q=boston")
    assert r.mimetype == "text/csv" and b"Boston" in r.data
    r = c.get("/export/db")
    assert r.status_code == 200 and r.data[:15] == b"SQLite format 3"


# ---- spreadsheets ----
import datetime as dt

from csvsearch.sheets import fmt

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")


def test_fmt():
    assert fmt(3.0) == "3" and fmt(2.5) == "2.5" and fmt(None) == "" and fmt(float("nan")) == ""
    assert fmt(dt.datetime(2026, 1, 2)) == "2026-01-02"
    assert fmt(dt.datetime(2026, 1, 2, 13, 5)) == "2026-01-02 13:05:00"
    assert fmt(True) == "TRUE"


@pytest.mark.parametrize("name,table,line,expected", [
    ("sales.xlsx", "sales.xlsx:Orders", 5,
     [("order_id", "1003"), ("customer", "Carol Smith"), ("sku", "C400"),
      ("qty", "12"), ("unit_price", "7.25"), ("order_date", "2026-03-30")]),
    ("inventory.xls", "inventory.xls:Inventory", 2,
     [("sku", "A100"), ("warehouse", "Boston"), ("on_hand", "250"), ("counted", "2026-04-01")]),
    ("cities.ods", "cities.ods:Cities", 3,
     [("city", "Denver"), ("state", "Colo."), ("population", "715522"), ("area_sq_mi", "153.3")]),
])
def test_spreadsheet_import(tmp_path, name, table, line, expected):
    conn = dbm.connect(str(tmp_path / "s.db"))
    dbm.import_file(conn, os.path.join(EXAMPLES, name))
    assert dbm.get_line(conn, table, line) == expected


def test_xlsx_sheets_blank_rows_and_reimport(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    p = tmp_path / "book.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "One"
    ws.append(["a", "b"]); ws.append([1.0, "x"]); ws.append([None, None]); ws.append([2.5, "y"])
    wb.create_sheet("Two").append(["c"])
    wb.save(p)
    conn = dbm.connect(str(tmp_path / "s.db"))
    assert dbm.import_file(conn, str(p)) == 2
    assert dbm.list_files(conn) == ["book.xlsx:One", "book.xlsx:Two"]
    assert dbm.get_line(conn, "book.xlsx:One", 4) == [("a", "2.5"), ("b", "y")]
    assert dbm.get_line(conn, "book.xlsx:One", 2) == [("a", "1"), ("b", "x")]
    del wb["Two"]
    wb.save(p)
    dbm.import_file(conn, str(p))
    assert dbm.list_files(conn) == ["book.xlsx:One"]


def test_web_sheet_dropdown(tmp_path):
    dbp = str(tmp_path / "s.db")
    conn = dbm.connect(dbp)
    dbm.import_file(conn, os.path.join(EXAMPLES, "sales.xlsx"))
    c = create_app(dbp).test_client()
    r = c.get("/?q=boston&file=sales.xlsx:Stores")
    assert b"sales.xlsx:Stores" in r.data and b"1 matching line" in r.data
