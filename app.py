import io
import os
import re
import sys
import tempfile
from datetime import date
from itertools import groupby

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy import func
from werkzeug.utils import secure_filename

from importer import compatible, extract_logo, parse_workbook
from models import Client, Entry, Project, db

def resource_dir():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))

app = Flask(
    __name__,
    template_folder=os.path.join(resource_dir(), "templates"),
    static_folder=os.path.join(resource_dir(), "static"),
)
os.makedirs(DATA_DIR, exist_ok=True)
LOGO_DIR = os.path.join(DATA_DIR, "logos")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(DATA_DIR, "budget.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

db.init_app(app)
with app.app_context():
    db.create_all()
    with db.engine.begin() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(clients)")]
        if "logo_path" not in cols:
            conn.exec_driver_sql("ALTER TABLE clients ADD COLUMN logo_path VARCHAR(255)")

MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
             "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def month_label(d):
    return f"{MONTHS_FR[d.month - 1]} {d.year}"


@app.before_request
def require_basic_auth():
    user = os.environ.get("ADMIN_USER", "")
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not user or not password:
        return None
    auth = request.authorization
    if auth and auth.username == user and auth.password == password:
        return None
    return Response(
        "Authentification requise.", 401,
        {"WWW-Authenticate": 'Basic realm="Suivi Budgetaire"'},
    )


def get_client(client_id):
    return db.session.get(Client, client_id) or abort(404)


def get_project(project_id):
    return db.session.get(Project, project_id) or abort(404)


@app.context_processor
def inject_globals():
    return {"month_label": month_label}


@app.route("/")
def dashboard():
    projects = Project.query.all()
    clients = Client.query.order_by(Client.name).all()

    total_budget = sum(p.budget_uo or 0 for p in projects)
    total_consumed = sum(p.consumed_uo for p in projects)
    total_balance = total_budget - total_consumed
    over_budget = [p for p in projects if p.status == "over"]
    near_budget = [p for p in projects if p.status == "warning"]

    years = sorted({e.month.year for p in projects for e in p.entries})
    yearly = []
    for year in years:
        consumed = sum(e.days for p in projects for e in p.entries if e.month.year == year)
        yearly.append({"year": year, "consumed": round(consumed, 2)})

    return render_template(
        "dashboard.html",
        clients=clients,
        total_budget=round(total_budget, 2),
        total_consumed=round(total_consumed, 2),
        total_balance=round(total_balance, 2),
        nb_projects=len(projects),
        over_budget=over_budget,
        near_budget=near_budget,
        yearly=yearly,
    )


@app.route("/api/monthly")
def api_monthly():
    client_id = request.args.get("client_id", type=int)
    q = db.session.query(Entry.month, func.sum(Entry.days)).join(Project)
    if client_id:
        q = q.filter(Project.client_id == client_id)
    rows = q.group_by(Entry.month).order_by(Entry.month).all()
    return jsonify([
        {"month": m.isoformat(), "label": month_label(m), "days": round(v or 0, 2)}
        for m, v in rows
    ])


@app.route("/clients", methods=["GET", "POST"])
def clients():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Le nom du client est obligatoire.", "danger")
        elif Client.query.filter(func.lower(Client.name) == name.lower()).first():
            flash("Ce client existe déjà.", "warning")
        else:
            db.session.add(Client(name=name))
            db.session.commit()
            flash(f"Client « {name} » ajouté.", "success")
        return redirect(url_for("clients"))
    return render_template(
        "clients.html",
        clients=Client.query.order_by(Client.name).all(),
    )


@app.route("/clients/<int:client_id>/delete", methods=["POST"])
def delete_client(client_id):
    client = get_client(client_id)
    if client.projects:
        flash("Impossible de supprimer un client ayant des projets.", "danger")
    else:
        db.session.delete(client)
        db.session.commit()
        flash(f"Client « {client.name} » supprimé.", "success")
    return redirect(url_for("clients"))


def _fmt_fr(v):
    v = round(v or 0, 2)
    if v == int(v):
        return str(int(v))
    return f"{v:,.2f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")


app.jinja_env.filters["fmt_fr"] = _fmt_fr


def synthese_data(client, year):
    months = [date(year, m, 1) for m in range(1, 13)]
    ordered = sorted(
        client.projects,
        key=lambda p: ((p.po_number or "").strip(), (p.code or "").strip(), p.mission),
    )
    groups = []
    for key, items in groupby(
        ordered, key=lambda p: ((p.po_number or "").strip(), (p.code or "").strip())
    ):
        items = list(items)
        missions = []
        for p in items:
            emap = {e.month: e.days or 0 for e in p.entries}
            missions.append({
                "po_number": p.po_number,
                "code": p.code,
                "mission": p.mission,
                "budget": p.budget_uo or 0,
                "consumed": p.consumed_uo,
                "solde": p.balance_uo,
                "monthly": [emap.get(m, 0) for m in months],
                "over": p.balance_uo < 0,
            })
        solde = sum(m["solde"] for m in missions)
        groups.append({
            "po_number": key[0],
            "code": key[1],
            "budget": sum(m["budget"] for m in missions),
            "consumed": sum(m["consumed"] for m in missions),
            "solde": solde,
            "monthly": [sum(m["monthly"][j] for m in missions) for j in range(12)],
            "missions": missions,
            "over": solde < 0,
        })
    totals = {
        "budget": sum(g["budget"] for g in groups),
        "consumed": sum(g["consumed"] for g in groups),
        "solde": sum(g["solde"] for g in groups),
        "monthly": [sum(g["monthly"][j] for g in groups) for j in range(12)],
        "consumed_eur": sum(p.consumed_eur for p in client.projects),
    }
    return months, groups, totals


@app.route("/clients/<int:client_id>/logo")
def client_logo(client_id):
    client = get_client(client_id)
    if not client.logo_path or not os.path.exists(client.logo_path):
        abort(404)
    return send_file(client.logo_path)


@app.route("/clients/<int:client_id>/logo", methods=["POST"])
def upload_logo(client_id):
    client = get_client(client_id)
    file = request.files.get("logo")
    if not file or not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        flash("Logo : merci de déposer une image PNG ou JPG.", "danger")
        return redirect(url_for("clients"))
    os.makedirs(LOGO_DIR, exist_ok=True)
    ext = "png" if file.filename.lower().endswith(".png") else "jpg"
    dest = os.path.join(LOGO_DIR, f"client_{client.id}.{ext}")
    file.save(dest)
    client.logo_path = dest
    db.session.commit()
    flash(f"Logo de « {client.name} » mis à jour.", "success")
    return redirect(url_for("clients"))


@app.route("/clients/<int:client_id>/synthese")
def client_synthese(client_id):
    client = get_client(client_id)
    years = sorted({e.month.year for p in client.projects for e in p.entries}, reverse=True)
    year = request.args.get("year", type=int) or (years[0] if years else date.today().year)
    months, groups, totals = synthese_data(client, year)
    month_labels = [f"{MONTHS_FR[m.month - 1]} {str(m.year)[2:]}" for m in months]
    return render_template(
        "synthese.html",
        client=client,
        year=year,
        years=years,
        month_labels=month_labels,
        groups=groups,
        totals=totals,
        today=date.today().strftime("%d/%m/%Y"),
    )


@app.route("/clients/<int:client_id>/synthese.pdf")
def client_synthese_pdf(client_id):
    client = get_client(client_id)
    year = request.args.get("year", type=int) or date.today().year
    months, groups, totals = synthese_data(client, year)
    from pdf_synthese import build_synthese_pdf
    pdf = build_synthese_pdf(client, groups, totals, year, date.today().strftime("%d/%m/%Y"))
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=synthese-{client.id}-{year}.pdf"
            )
        },
    )


@app.route("/projects")
def projects():
    client_id = request.args.get("client_id", type=int)
    query = Project.query
    if client_id:
        query = query.filter(Project.client_id == client_id)
    return render_template(
        "projects.html",
        projects=query.join(Client).order_by(Client.name, Project.mission).all(),
        clients=Client.query.order_by(Client.name).all(),
        current_client=client_id,
    )


@app.route("/projects", methods=["POST"])
def create_project():
    form = request.form
    client = get_client(int(form["client_id"]))
    try:
        project = Project(
            client_id=client.id,
            po_number=form.get("po_number", "").strip(),
            code=form.get("code", "").strip(),
            mission=form.get("mission", "").strip(),
            rate=float(form.get("rate") or 0),
            budget_uo=float(form.get("budget_uo") or 0),
        )
    except ValueError:
        flash("Valeurs numériques invalides.", "danger")
        return redirect(url_for("projects"))
    if not project.mission:
        flash("La mission est obligatoire.", "danger")
        return redirect(url_for("projects"))
    db.session.add(project)
    db.session.commit()
    flash(f"Projet « {project.mission} » créé.", "success")
    return redirect(url_for("project_detail", project_id=project.id))


@app.route("/projects/<int:project_id>")
def project_detail(project_id):
    project = get_project(project_id)
    entries = sorted(project.entries, key=lambda e: e.month)
    clients = Client.query.order_by(Client.name).all()
    return render_template("project_detail.html", project=project, entries=entries, clients=clients)


@app.route("/projects/<int:project_id>/edit", methods=["POST"])
def edit_project(project_id):
    project = get_project(project_id)
    form = request.form
    try:
        project.po_number = form.get("po_number", "").strip()
        project.code = form.get("code", "").strip()
        project.mission = form.get("mission", "").strip() or project.mission
        project.rate = float(form.get("rate") or 0)
        project.budget_uo = float(form.get("budget_uo") or 0)
        if form.get("client_id"):
            project.client_id = int(form["client_id"])
    except ValueError:
        flash("Valeurs numériques invalides.", "danger")
        return redirect(url_for("project_detail", project_id=project.id))
    db.session.commit()
    flash("Projet mis à jour.", "success")
    return redirect(url_for("project_detail", project_id=project.id))


@app.route("/projects/<int:project_id>/delete", methods=["POST"])
def delete_project(project_id):
    project = get_project(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Projet supprimé.", "success")
    return redirect(url_for("projects"))


@app.route("/projects/<int:project_id>/entries", methods=["POST"])
def add_entry(project_id):
    project = get_project(project_id)
    try:
        month = date.fromisoformat(request.form["month"] + "-01")
        days = float(request.form["days"])
    except (KeyError, ValueError):
        flash("Mois ou nombre de jours invalide.", "danger")
        return redirect(url_for("project_detail", project_id=project.id))
    entry = Entry.query.filter_by(project_id=project.id, month=month).first()
    if entry:
        entry.days = days
    else:
        db.session.add(Entry(project_id=project.id, month=month, days=days))
    db.session.commit()
    flash(f"Consommation {month_label(month)} enregistrée.", "success")
    return redirect(url_for("project_detail", project_id=project.id))


@app.route("/entries/<int:entry_id>/delete", methods=["POST"])
def delete_entry(entry_id):
    entry = db.session.get(Entry, entry_id) or abort(404)
    project_id = entry.project_id
    db.session.delete(entry)
    db.session.commit()
    flash("Consommation supprimée.", "success")
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/import", methods=["GET"])
def import_form():
    return render_template("import.html")


@app.route("/import", methods=["POST"])
def import_file():
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".xlsx"):
        flash("Merci de déposer un fichier .xlsx.", "danger")
        return redirect(url_for("import_form"))

    client_name = request.form.get("client_name", "").strip()
    if not client_name:
        match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9 _]*?)\s*-", file.filename)
        client_name = match.group(1).strip().upper() if match else "Import"

    try:
        default_rate = float(request.form.get("default_rate") or 0)
    except ValueError:
        default_rate = 0

    path = os.path.join(tempfile.gettempdir(), secure_filename(file.filename))
    file.save(path)
    try:
        parsed = parse_workbook(path, default_rate=default_rate)
    except Exception:
        os.remove(path)
        flash("Impossible de lire ce fichier. Vérifiez qu'il s'agit bien d'une version du fichier Excel « Project Financial Sheet » (.xlsx).", "danger")
        return redirect(url_for("import_form"))

    if not parsed:
        os.remove(path)
        flash("Aucun projet détecté dans ce fichier.", "warning")
        return redirect(url_for("import_form"))

    client = Client.query.filter(func.lower(Client.name) == client_name.lower()).first()
    if not client:
        client = Client(name=client_name)
        db.session.add(client)
        db.session.flush()

    if not client.logo_path or not os.path.exists(client.logo_path):
        try:
            client.logo_path = extract_logo(path, LOGO_DIR, client.id)
        except Exception:
            pass
    os.remove(path)

    created, updated, entries_added = 0, 0, 0
    for item in parsed:
        item_entries = {
            date.fromisoformat(month_str + "-01"): days
            for month_str, days in item["entries"].items()
        }
        candidates = Project.query.filter_by(
            client_id=client.id,
            po_number=item["po_number"],
            code=item["code"],
            mission=item["mission"],
        ).all()
        project = next(
            (p for p in candidates
             if compatible({e.month: e.days for e in p.entries}, item_entries)),
            None,
        )
        if not project:
            project = Project(
                client_id=client.id,
                po_number=item["po_number"],
                code=item["code"],
                mission=item["mission"],
                rate=item["rate"] if item["rate"] is not None else default_rate,
                budget_uo=item["budget_uo"],
            )
            db.session.add(project)
            db.session.flush()
            created += 1
        else:
            project.code = project.code or item["code"]
            if item["rate"]:
                project.rate = item["rate"]
            if item["budget_uo"]:
                project.budget_uo = max(project.budget_uo or 0, item["budget_uo"])
            updated += 1
        for month_str, days in item["entries"].items():
            month = date.fromisoformat(month_str + "-01")
            entry = Entry.query.filter_by(project_id=project.id, month=month).first()
            if entry:
                if days > entry.days:
                    entry.days = days
                    entries_added += 1
            else:
                db.session.add(Entry(project_id=project.id, month=month, days=days))
                entries_added += 1

    db.session.commit()
    flash(
        f"Import réussi : {created} projet(s) créé(s), {updated} mis à jour, "
        f"{entries_added} ligne(s) de consommation. Client : {client.name}.",
        "success",
    )
    return redirect(url_for("projects", client_id=client.id))


if __name__ == "__main__":
    import threading
    import webbrowser

    port = int(os.environ.get("PORT", "8000"))
    if os.environ.get("NO_BROWSER") != "1":
        threading.Timer(
            1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")
        ).start()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
