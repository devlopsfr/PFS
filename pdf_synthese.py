import io
import os

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

NAVY = HexColor("#002060")
GREY = HexColor("#F2F2F2")
GREEN = HexColor("#E2EFDA")
RED = HexColor("#C00000")
LIGHT_GREY = HexColor("#BFBFBF")

MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                "juil.", "août", "sept.", "oct.", "nov.", "déc."]

COL_WIDTHS = [50, 60, 140, 34, 46, 46]
MONTH_COL_W = 29
MARGIN = 22


def _fmt(v, thin=True):
    v = round(v or 0, 2)
    if v == int(v):
        return str(int(v))
    sep = "\u202f" if thin else " "
    s = f"{v:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", sep).replace(".", ",")


def build_synthese_pdf(client, groups, totals, year, today):
    buf = io.BytesIO()
    W, H = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"Synthèse {client.name} {year}")

    logo_h = 30
    if client.logo_path and os.path.exists(client.logo_path):
        try:
            img = ImageReader(client.logo_path)
            iw, ih = img.getSize()
            scale = min(170 / iw, logo_h / ih)
            dw, dh = iw * scale, ih * scale
            c.drawImage(img, W - MARGIN - dw, H - MARGIN - dh + 4,
                        dw, dh, mask="auto")
        except Exception:
            pass

    band_h = 40
    band_y = H - MARGIN - logo_h - band_h
    c.setFillColor(NAVY)
    c.rect(MARGIN, band_y, W - 2 * MARGIN, band_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(MARGIN + 8, band_y + 15,
                 f"Suivi des commandes / facturation — {client.name}")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(W - MARGIN - 8, band_y + 15, today)

    y = band_y - 12
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 6)
    c.drawString(MARGIN, y, "=> les lignes en rouge sont les dépassements de budget.")
    y -= 8

    months = [f"{MONTHS_SHORT[m - 1]} {str(year)[2:]}" for m in range(1, 13)]
    col_xs = []
    x = MARGIN
    for w in COL_WIDTHS:
        col_xs.append(x)
        x += w
    month_xs = []
    for _ in months:
        month_xs.append(x)
        x += MONTH_COL_W
    table_w = x - MARGIN

    rows = []
    for g in groups:
        for i, msn in enumerate(g["missions"]):
            rows.append(("mission", g, msn, i))
        rows.append(("total", g, None, None))
    rows.append(("grand", None, None, None))

    header_h = 20
    avail = y - MARGIN - 14
    n_rows = max(len(rows), 1)
    row_h = min(13.5, avail / n_rows)
    fs = max(4.8, min(7.5, row_h * 0.62))

    c.setFillColor(NAVY)
    c.rect(MARGIN, y - header_h, table_w, header_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", fs)
    headers = ["N° PO", "Code", "Mission / taux", "UO", "Consommé", "Solde"]
    for i, label in enumerate(headers):
        c.drawString(col_xs[i] + 3, y - header_h + 6, label)
    for i, label in enumerate(months):
        c.drawString(month_xs[i] + 3, y - header_h + 6, label)
    y -= header_h

    for kind, g, msn, idx in rows:
        if y - row_h < MARGIN:
            break
        if kind == "grand":
            c.setFillColor(NAVY)
            c.rect(MARGIN, y - row_h, table_w, row_h, fill=1, stroke=0)
            c.setFillColor(white)
        elif kind == "total":
            c.setFillColor(GREY)
            c.rect(MARGIN, y - row_h, table_w, row_h, fill=1, stroke=0)
            c.setFillColor(RED if g["over"] else black)
        else:
            c.setFillColor(RED if msn["over"] else black)

        first_of_group = kind == "mission" and idx == 0
        c.setFont("Helvetica-Bold", fs)
        c.drawString(MARGIN + 3, y - row_h + 3.5,
                     g["po_number"] if first_of_group else "")
        c.drawString(col_xs[1] + 3, y - row_h + 3.5,
                     g["code"] if first_of_group else "")
        if kind == "mission":
            c.drawString(col_xs[2] + 3, y - row_h + 3.5, msn["mission"][:52])
            c.drawRightString(col_xs[3] + COL_WIDTHS[3] - 3, y - row_h + 3.5,
                              _fmt(msn["budget"]))
            c.drawRightString(col_xs[4] + COL_WIDTHS[4] - 3, y - row_h + 3.5,
                              _fmt(msn["consumed"]))
            c.drawRightString(col_xs[5] + COL_WIDTHS[5] - 3, y - row_h + 3.5,
                              _fmt(msn["solde"]))
            for j, days in enumerate(msn["monthly"]):
                if days:
                    c.setFillColor(GREEN)
                    c.rect(month_xs[j], y - row_h, MONTH_COL_W, row_h,
                           fill=1, stroke=0)
                    c.setFillColor(RED if msn["over"] else black)
                    c.drawRightString(month_xs[j] + MONTH_COL_W - 2,
                                      y - row_h + 3.5, _fmt(days))
        elif kind == "total":
            c.drawString(col_xs[2] + 3, y - row_h + 3.5, "Total PO")
            c.drawRightString(col_xs[3] + COL_WIDTHS[3] - 3, y - row_h + 3.5,
                              _fmt(g["budget"]))
            c.drawRightString(col_xs[4] + COL_WIDTHS[4] - 3, y - row_h + 3.5,
                              _fmt(g["consumed"]))
            c.drawRightString(col_xs[5] + COL_WIDTHS[5] - 3, y - row_h + 3.5,
                              _fmt(g["solde"]))
            month_sums = [
                sum(msn["monthly"][j] for msn in g["missions"]) for j in range(12)
            ]
            for j, days in enumerate(month_sums):
                if days:
                    c.drawRightString(month_xs[j] + MONTH_COL_W - 2,
                                      y - row_h + 3.5, _fmt(days))
        else:
            c.drawString(col_xs[2] + 3, y - row_h + 3.5, "TOTAL CLIENT")
            c.drawRightString(col_xs[3] + COL_WIDTHS[3] - 3, y - row_h + 3.5,
                              _fmt(totals["budget"]))
            c.drawRightString(col_xs[4] + COL_WIDTHS[4] - 3, y - row_h + 3.5,
                              _fmt(totals["consumed"]))
            c.drawRightString(col_xs[5] + COL_WIDTHS[5] - 3, y - row_h + 3.5,
                              _fmt(totals["solde"]))
            for j, days in enumerate(totals["monthly"]):
                if days:
                    c.drawRightString(month_xs[j] + MONTH_COL_W - 2,
                                      y - row_h + 3.5, _fmt(days))
        y -= row_h

    y -= 4
    if y > MARGIN:
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(MARGIN, y,
                     f"Total {year} : {_fmt(totals['consumed'], thin=False)} j — "
                     f"{_fmt(totals['consumed_eur'], thin=False)} €")

    c.showPage()
    c.save()
    return buf.getvalue()
