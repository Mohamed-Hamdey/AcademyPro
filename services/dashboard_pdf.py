"""
PDF export for the daily and monthly dashboard views.

Uses QTextDocument + QPrinter — same pattern as services/pdf_export.py
for player history. On Windows the print dialog also offers "Save as PDF".
"""

import os
import sys
import calendar
from datetime import date, datetime

from PyQt6.QtGui import QTextDocument, QPageSize, QPageLayout
from PyQt6.QtCore import QMarginsF
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_academy_name, load_config
from services import dashboard_service, activity_service
from ui import i18n
from ui.i18n import t


MONTH_KEYS = [
    "month.january", "month.february", "month.march", "month.april",
    "month.may", "month.june", "month.july", "month.august",
    "month.september", "month.october", "month.november", "month.december",
]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def print_day(parent_widget, day: date):
    summary = dashboard_service.day_summary(day)
    html = _build_day_html(day, summary)
    _print_html(parent_widget, html, t("dash.print_dialog.day_title"))


def print_month(parent_widget, year: int, month: int):
    summary = dashboard_service.month_summary(year, month)
    html = _build_month_html(year, month, summary)
    _print_html(parent_widget, html, t("dash.print_dialog.month_title"))


# ---------------------------------------------------------------------------
# Printer helper
# ---------------------------------------------------------------------------

def _print_html(parent_widget, html: str, title: str):
    doc = QTextDocument()
    doc.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(
        QMarginsF(20, 18, 20, 18),
        QPageLayout.Unit.Millimeter,
    )

    dlg = QPrintDialog(printer, parent_widget)
    dlg.setWindowTitle(title)
    if dlg.exec() != QPrintDialog.DialogCode.Accepted:
        return

    doc.print(printer)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(s) -> str:
    return (str(s) if s is not None else "") \
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _align_start() -> str:
    return "right" if i18n.current_language() == "ar" else "left"


def _common_style() -> str:
    return """
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif;
               color: #172033; font-size: 10.5pt; line-height: 1.5; }
        h1 { font-size: 22pt; margin: 0; color: #1E40AF; font-weight: 700; }
        h2 { font-size: 13pt; margin: 20px 0 8px 0; color: #1E3A5F;
             border-bottom: 2px solid #2563EB; padding-bottom: 5px;
             font-weight: 700; }
        .academy-en { font-size: 11pt; color: #64748B; margin-bottom: 4px; }
        .report-title { font-size: 11pt; color: #2563EB; font-weight: 600; }
        .muted { color: #64748B; }
        .small { font-size: 9.5pt; }
        table { border-collapse: collapse; width: 100%; }
        td { padding: 5px 8px; vertical-align: top; }

        .kpi-table { width: 100%; margin-top: 6px; }
        .kpi-table td {
            text-align: center; vertical-align: middle;
            background: #F1F5F9; border: 1px solid #DCE3EC;
            border-radius: 6px; padding: 10px 6px; width: 25%;
        }
        .kpi-value { font-size: 20pt; font-weight: 700;
                     color: #1E40AF; line-height: 1.1; }
        .kpi-value.green { color: #16A34A; }
        .kpi-value.red   { color: #DC2626; }
        .kpi-label { font-size: 8.5pt; color: #64748B; margin-top: 2px; }

        .row-item td { border-bottom: 1px dotted #DCE3EC; }

        .footer {
            margin-top: 24px; padding-top: 8px;
            border-top: 1px solid #DCE3EC;
            font-size: 8.5pt; color: #64748B; text-align: center;
        }
    </style>
    """


def _header_block() -> str:
    academy = get_academy_name()
    cfg = load_config()
    academy_ar = cfg.get("academy_name_ar") or academy
    return f"""
    <div style="text-align: {_align_start()};">
      <h1>{_esc(academy_ar)}</h1>
      <div class="academy-en">{_esc(academy)}</div>
    </div>
    <hr style="border: none; border-top: 2px solid #2563EB; margin: 12px 0 0 0;"/>
    """


def _footer_block() -> str:
    from app_state import app as app_state
    user = app_state.user
    user_str = user.username if user else "system"
    return (
        f'<div class="footer">'
        f'{t("history.report.footer_generated_by")}: {_esc(user_str)} '
        f'· {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Day report
# ---------------------------------------------------------------------------

def _build_day_html(day: date, s: dict) -> str:
    parts = [_common_style(), _header_block()]

    parts.append(f"""
    <div style="text-align: {_align_start()}; margin-top: 10px;">
      <div class="report-title">{t("dash.report.day_title")} — {_esc(day.isoformat())}</div>
    </div>
    """)

    # KPIs
    parts.append('<table class="kpi-table"><tr>')
    parts.append(
        f'<td><div class="kpi-value green">{s["revenue"]:,.0f}</div>'
        f'<div class="kpi-label">{t("dash.kpi.revenue")} (EGP)</div></td>'
    )
    parts.append(
        f'<td><div class="kpi-value red">{s["expenses"]:,.0f}</div>'
        f'<div class="kpi-label">{t("dash.kpi.expenses")} (EGP)</div></td>'
    )
    net_prefix = "+" if s["net"] > 0 else ""
    parts.append(
        f'<td><div class="kpi-value">{net_prefix}{s["net"]:,.0f}</div>'
        f'<div class="kpi-label">{t("dash.kpi.net")} (EGP)</div></td>'
    )
    parts.append(
        f'<td><div class="kpi-value">{s["attendance_total"]}</div>'
        f'<div class="kpi-label">{t("dash.kpi.attendance")}</div></td>'
    )
    parts.append('</tr></table>')

    # Attendance by activity
    parts.append(f'<h2>{t("dash.by_activity")}</h2>')
    if not s["attendance_by_activity"]:
        parts.append(f'<p class="muted">{t("dash.by_activity_empty")}</p>')
    else:
        parts.append('<table>')
        for row in s["attendance_by_activity"]:
            name = _activity_name(row)
            parts.append(
                f'<tr class="row-item">'
                f'<td>{_esc(name)}</td>'
                f'<td style="text-align: right;"><b>{row["cnt"]}</b></td>'
                f'</tr>'
            )
        parts.append(
            f'<tr><td><b>{t("dash.total")}</b></td>'
            f'<td style="text-align: right;"><b>{s["attendance_total"]}</b></td></tr>'
        )
        parts.append('</table>')

    # Payments
    parts.append(f'<h2>{t("dash.payments")}</h2>')
    if not s["payments"]:
        parts.append(f'<p class="muted">{t("dash.payments_empty")}</p>')
    else:
        parts.append('<table>')
        for p in s["payments"]:
            act = _activity_name({
                "name_en": p.get("activity_name_en"),
                "name_ar": p.get("activity_name_ar"),
            })
            note = p.get("notes") or ""
            detail = " · ".join(x for x in [act, note] if x)
            parts.append(
                f'<tr class="row-item">'
                f'<td>{_esc(p["player_name"])}</td>'
                f'<td class="muted small">{_esc(detail)}</td>'
                f'<td style="text-align: right;">'
                f'<b>{p["amount"]:,.0f} {_esc(p["currency"])}</b></td>'
                f'</tr>'
            )
        parts.append('</table>')

    # New signups
    parts.append(f'<h2>{t("dash.signups")}</h2>')
    if not s["new_player_list"]:
        parts.append(f'<p class="muted">{t("dash.signups_empty")}</p>')
    else:
        parts.append('<table>')
        for pl in s["new_player_list"]:
            parts.append(
                f'<tr class="row-item">'
                f'<td>{_esc(pl["full_name"])}</td>'
                f'<td class="muted small">{_esc(pl["phone"])}</td>'
                f'</tr>'
            )
        parts.append('</table>')

    # Alerts
    alerts = _collect_alerts(s)
    if alerts:
        parts.append(f'<h2>{t("dash.alerts")}</h2>')
        parts.append('<table>')
        for a in alerts:
            parts.append(f'<tr class="row-item"><td>{_esc(a)}</td></tr>')
        parts.append('</table>')

    parts.append(_footer_block())
    return "".join(parts)


# ---------------------------------------------------------------------------
# Month report
# ---------------------------------------------------------------------------

def _build_month_html(year: int, month: int, s: dict) -> str:
    parts = [_common_style(), _header_block()]

    month_label = f"{t(MONTH_KEYS[month-1])} {year}"
    parts.append(f"""
    <div style="text-align: {_align_start()}; margin-top: 10px;">
      <div class="report-title">{t("dash.report.month_title")} — {_esc(month_label)}</div>
    </div>
    """)

    # KPIs
    parts.append('<table class="kpi-table"><tr>')
    parts.append(
        f'<td><div class="kpi-value green">{s["revenue"]:,.0f}</div>'
        f'<div class="kpi-label">{t("dash.kpi.revenue")} (EGP)</div></td>'
    )
    parts.append(
        f'<td><div class="kpi-value red">{s["expenses"]:,.0f}</div>'
        f'<div class="kpi-label">{t("dash.kpi.expenses")} (EGP)</div></td>'
    )
    net_prefix = "+" if s["net"] > 0 else ""
    parts.append(
        f'<td><div class="kpi-value">{net_prefix}{s["net"]:,.0f}</div>'
        f'<div class="kpi-label">{t("dash.kpi.net")} (EGP)</div></td>'
    )
    parts.append(
        f'<td><div class="kpi-value">{s["attendance_total"]}</div>'
        f'<div class="kpi-label">{t("dash.kpi.attendance")}</div></td>'
    )
    parts.append('</tr></table>')

    # Revenue by activity
    parts.append(f'<h2>{t("dash.month.by_activity")}</h2>')
    if not s["revenue_by_activity"]:
        parts.append(f'<p class="muted">{t("dash.month.no_data")}</p>')
    else:
        parts.append('<table>')
        for row in s["revenue_by_activity"]:
            name = _activity_name(row)
            parts.append(
                f'<tr class="row-item">'
                f'<td>{_esc(name)}</td>'
                f'<td style="text-align: right;">'
                f'<b>{row["total"]:,.0f} EGP</b>'
                f' <span class="muted small">({row["count"]})</span></td>'
                f'</tr>'
            )
        parts.append('</table>')

    # Expenses by category
    parts.append(f'<h2>{t("dash.month.expenses_by_category")}</h2>')
    if not s["expenses_by_category"]:
        parts.append(f'<p class="muted">{t("dash.month.no_data")}</p>')
    else:
        parts.append('<table>')
        for row in s["expenses_by_category"]:
            name = t(f"expenses.cat.{row['category']}")
            parts.append(
                f'<tr class="row-item">'
                f'<td>{_esc(name)}</td>'
                f'<td style="text-align: right;">'
                f'<b>{row["total"]:,.0f} EGP</b>'
                f' <span class="muted small">({row["count"]})</span></td>'
                f'</tr>'
            )
        parts.append('</table>')

    # Revenue by method
    parts.append(f'<h2>{t("dash.month.by_method")}</h2>')
    if not s["revenue_by_method"]:
        parts.append(f'<p class="muted">{t("dash.month.no_data")}</p>')
    else:
        parts.append('<table>')
        for row in s["revenue_by_method"]:
            parts.append(
                f'<tr class="row-item">'
                f'<td>{_esc(row["method"])}</td>'
                f'<td style="text-align: right;">'
                f'<b>{row["total"]:,.0f} EGP</b>'
                f' <span class="muted small">({row["count"]})</span></td>'
                f'</tr>'
            )
        parts.append('</table>')

    parts.append(_footer_block())
    return "".join(parts)


# ---------------------------------------------------------------------------

def _activity_name(row: dict) -> str:
    if i18n.current_language() == "ar":
        return row.get("name_ar") or row.get("name_en") or ""
    return row.get("name_en") or row.get("name_ar") or ""


def _collect_alerts(s: dict) -> list[str]:
    alerts = []
    for lp in s.get("low_session_players", []):
        act = _activity_name({
            "name_en": lp.get("activity_name_en"),
            "name_ar": lp.get("activity_name_ar"),
        })
        alerts.append(
            t("dash.alert.low_sessions",
              name=lp["full_name"],
              count=lp["sessions_remaining"],
              activity=act or "")
        )
    for exp in s.get("expiring_soon", []):
        act = _activity_name({
            "name_en": exp.get("activity_name_en"),
            "name_ar": exp.get("activity_name_ar"),
        })
        alerts.append(
            t("dash.alert.expiring_soon",
              name=exp["full_name"],
              date=exp["expiry_date"],
              activity=act or "")
        )
    return alerts