import csv
import io
import os

from flask import Flask, Response, abort, render_template, request, send_file

from . import db as dbm

PAGE_SIZE = 50


def create_app(db_path):
    app = Flask(__name__)
    app.config["DB_PATH"] = os.path.abspath(db_path)

    def conn():
        return dbm.connect(app.config["DB_PATH"])

    def params():
        a = request.args
        return dict(
            value=a.get("q", ""),
            column=a.get("col", ""),
            file=a.get("file", ""),
            case_sensitive=a.get("cs") == "1",
        )

    @app.route("/")
    def index():
        p = params()
        try:
            page = max(1, int(request.args.get("page", 1)))
        except ValueError:
            page = 1
        c = conn()
        try:
            files = dbm.list_files(c)
            total, rows = 0, []
            searched = bool(p["value"] or p["column"] or "q" in request.args)
            if searched:
                total, rows = dbm.search(c, **p, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE)
        finally:
            c.close()
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        return render_template(
            "index.html", files=files, rows=rows, total=total, page=page,
            pages=pages, p=p, searched=searched, preview=4,
        )

    @app.route("/line")
    def line():
        file = request.args.get("file", "")
        try:
            ln = int(request.args.get("line", ""))
        except ValueError:
            abort(400)
        c = conn()
        try:
            cells = dbm.get_line(c, file, ln)
        finally:
            c.close()
        if not cells:
            abort(404)
        return render_template("line.html", file=file, line=ln, cells=cells)

    @app.route("/export/db")
    def export_db():
        path = app.config["DB_PATH"]
        return send_file(path, as_attachment=True, download_name=os.path.basename(path))

    @app.route("/export/results.csv")
    def export_results():
        p = params()
        c = conn()
        try:
            _, rows = dbm.search(c, **p, limit=10**9, offset=0)
        finally:
            c.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["file", "line", "column", "value"])
        for r in rows:
            for col, val in r["cells"]:
                w.writerow([r["file"], r["line"], col, val])
        return Response(
            buf.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=results.csv"},
        )

    return app
