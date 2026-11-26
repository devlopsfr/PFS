import os
import re
import zipfile
from datetime import datetime

import openpyxl


def extract_logo(xlsx_path, dest_dir, client_id):
    try:
        z = zipfile.ZipFile(xlsx_path)
    except Exception:
        return None
    best = None
    for name in z.namelist():
        match = re.match(r"xl/media/.+\.(png|jpe?g)$", name, re.IGNORECASE)
        if not match:
            continue
        try:
            data = z.read(name)
        except Exception:
            continue
        if best is None or len(data) > best[1]:
            best = (data, len(data), match.group(1).lower())
    if not best:
        return None
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"client_{client_id}.{best[2]}")
    with open(dest, "wb") as f:
        f.write(best[0])
    return dest


def _clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace("\n", " ").strip()
        return value or None
    return value


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_workbook(path, default_rate=0.0):
    wb = openpyxl.load_workbook(path, data_only=True)
    groups = {}
    for ws in wb.worksheets:
        for item in _parse_sheet(ws, default_rate):
            key = (item["po_number"], item["code"], item["mission"])
            group = groups.setdefault(key, [])
            for existing in group:
                if _compatible(existing["entries"], item["entries"]):
                    _merge(existing, item)
                    break
            else:
                group.append(item)
    return [item for group in groups.values() for item in group]


def _merge(existing, new):
    existing["budget_uo"] = max(existing["budget_uo"] or 0, new["budget_uo"] or 0)
    if existing["rate"] is None:
        existing["rate"] = new["rate"]
    for month, days in new["entries"].items():
        existing["entries"][month] = max(existing["entries"].get(month, 0), days)


def _compatible(a, b):
    return _is_subset(a, b) or _is_subset(b, a)


def compatible(a, b):
    return _compatible(a, b)


def _is_subset(small, large):
    if not small:
        return True
    return all(v <= large.get(month, 0) for month, v in small.items())


def _parse_sheet(ws, default_rate):
    row_months = {}
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, datetime):
                months = row_months.setdefault(cell.row, {})
                months[cell.column] = date_key(cell.value)

    header_rows = sorted(row_months)
    if not header_rows:
        return []

    projects = []
    pending_missions = []
    last_project = None

    for r in range(1, ws.max_row + 1):
        if r in row_months:
            continue

        b = _clean(ws.cell(row=r, column=2).value)
        c = _clean(ws.cell(row=r, column=3).value)
        d = _clean(ws.cell(row=r, column=4).value)
        e = ws.cell(row=r, column=5).value

        if not any(v is not None for v in (b, c, d, e)):
            continue

        months = _months_for_row(row_months, header_rows, r)
        row_values = {
            col: ws.cell(row=r, column=col).value for col in months
        }
        if _is_total_row(b, c, d):
            last_project = None
            continue

        if _is_number(d) and _is_number(e) and not b and not c:
            if last_project is not None and not last_project["rate"]:
                last_project["rate"] = float(d)
            continue

        if b and c and not d:
            for mission in pending_missions:
                mission["po_number"] = str(b)
                mission["code"] = str(c)
                projects.append(mission)
            pending_missions = []
            last_project = None
            continue

        if d and _is_number(e) and not b and not c:
            pending_missions.append(
                _make_project(None, None, str(d), float(e), months, row_values, default_rate)
            )
            continue

        if b and c and d and _is_number(e):
            project = _make_project(str(b), str(c), str(d), float(e), months, row_values, default_rate)
            projects.append(project)
            last_project = project
            continue

    for mission in pending_missions:
        projects.append(mission)

    return projects


def _is_total_row(b, c, d):
    for value in (b, c, d):
        if isinstance(value, str) and value.strip().lower().startswith("total"):
            return True
    return False


def _months_for_row(row_months, header_rows, r):
    candidates = [h for h in header_rows if h < r]
    if not candidates:
        return {}
    return row_months[candidates[-1]]


def _make_project(po_number, code, mission, budget_uo, months, row_values, default_rate):
    entries = {}
    for col, month in months.items():
        value = row_values.get(col)
        if _is_number(value) and value != 0:
            entries[month] = float(value)
    return {
        "po_number": po_number or "",
        "code": code or "",
        "mission": mission,
        "budget_uo": float(budget_uo),
        "rate": None,
        "default_rate": default_rate,
        "entries": entries,
    }


def date_key(value):
    if isinstance(value, datetime):
        return f"{value.year:04d}-{value.month:02d}"
    return str(value)
