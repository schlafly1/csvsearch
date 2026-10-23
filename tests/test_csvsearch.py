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
