from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

    projects = db.relationship(
        "Project", backref="client", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def budget_uo(self):
        return sum(p.budget_uo or 0 for p in self.projects)

    @property
    def consumed_uo(self):
        return sum(p.consumed_uo for p in self.projects)

    @property
    def balance_uo(self):
        return self.budget_uo - self.consumed_uo

    @property
    def consumed_eur(self):
        return sum(p.consumed_eur for p in self.projects)

    @property
    def usage_pct(self):
        if not self.budget_uo:
            return 0
        return min(999, round(self.consumed_uo / self.budget_uo * 100))


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    po_number = db.Column(db.String(80), default="")
    code = db.Column(db.String(80), default="")
    mission = db.Column(db.String(200), nullable=False)
    rate = db.Column(db.Float, default=0.0)
    budget_uo = db.Column(db.Float, default=0.0)

    entries = db.relationship(
        "Entry", backref="project", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def consumed_uo(self):
        return sum(e.days or 0 for e in self.entries)

    @property
    def balance_uo(self):
        return (self.budget_uo or 0) - self.consumed_uo

    @property
    def budget_eur(self):
        return (self.budget_uo or 0) * (self.rate or 0)

    @property
    def consumed_eur(self):
        return self.consumed_uo * (self.rate or 0)

    @property
    def balance_eur(self):
        return self.budget_eur - self.consumed_eur

    @property
    def usage_pct(self):
        if not self.budget_uo:
            return 0
        return min(999, round(self.consumed_uo / self.budget_uo * 100))

    @property
    def status(self):
        if self.balance_uo < 0:
            return "over"
        if self.budget_uo and self.balance_uo < self.budget_uo * 0.1:
            return "warning"
        return "ok"


class Entry(db.Model):
    __tablename__ = "entries"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    month = db.Column(db.Date, nullable=False)
    days = db.Column(db.Float, nullable=False, default=0.0)

    __table_args__ = (
        db.UniqueConstraint("project_id", "month", name="uq_entry_project_month"),
    )

    @property
    def eur(self):
        return (self.days or 0) * (self.project.rate or 0)
