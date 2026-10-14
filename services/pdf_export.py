"""
PDF / print export for the player Records & Activity view.

Uses QTextDocument + QPrinter. On Windows the system print dialog also
offers "Save as PDF", giving a fully detailed PDF without any external
dependency.

Font sizing notes:
  Qt's HTML renderer for QTextDocument respects pt sizes well. We use
  10.5pt for body, 11pt for section headers, 24pt for the academy name.
  That's roughly Word's 10pt-11pt default and reads comfortably printed.
"""

import os
import sys
from datetime import date, datetime
from collections import OrderedDict

from PyQt6.QtGui import QTextDocument, QPageSize, QPageLayout
from PyQt6.QtCore import QMarginsF
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_academy_name, load_config, get_plan_label
from services import activity_service
from ui import i18n
from ui.i18n import t


MONTH_KEYS = [
    "month.january", "month.february", "month.march", "month.april",
    "month.may", "month.june", "month.july", "month.august",
    "month.september", "month.october", "month.november", "month.december",
]


def print_player_history(parent_widget, player, attendance, active_subs,
                         all_subs, timeline):
    html = _build_html(player, attendance, active_subs, all_subs, timeline)

    doc = QTextDocument()
    doc.setDefaultFont(doc.defaultFont())
    doc.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(
        QMarginsF(20, 18, 20, 18),
        QPageLayout.Unit.Millimeter,
    )

    dlg = QPrintDialog(printer, parent_widget)
    dlg.setWindowTitle(t("history.print_dialog_title"))
    if dlg.exec() != QPrintDialog.DialogCode.Accepted:
        return

    doc.print(printer)


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _esc(s) -> str:
    return (str(s) if s is not None else "") \
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _is_rtl() -> bool:
    return i18n.current_language() == "ar"


def _dir_attr() -> str:
    return 'dir="rtl"' if _is_rtl() else 'dir="ltr"'


def _build_html(player, attendance, active_subs, all_subs, timeline) -> str:
    academy = get_academy_name()
    cfg = load_config()
    academy_ar = cfg.get("academy_name_ar") or academy

    rtl = _is_rtl()
    align_start = "right" if rtl else "left"
    align_end = "left" if rtl else "right"

    # --- KPI computation ---
    allowed = [e for e in attendance if e.result == "allowed"]
    denied = [e for e in attendance if e.result == "denied"]
    total_attended = len(allowed)
    total_denied = len(denied)

    today = date.today()
    month_prefix = f"{today.year:04d}-{today.month:02d}"
    this_month = sum(1 for e in allowed if e.scan_datetime.startswith(month_prefix))

    remaining_total = sum(s.sessions_remaining for s in active_subs) if active_subs else 0
    sessions_total = sum(s.sessions_total for s in active_subs) if active_subs else 0

    # Total paid across all subscriptions
    total_paid = sum(
        (s.payment_amount or 0) for s in all_subs
    )

    # --- Styles ---
    parts = []
    parts.append(f"""
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, sans-serif;
            color: #172033;
            font-size: 10.5pt;
            line-height: 1.5;
        }}
        h1 {{
            font-size: 24pt;
            margin: 0 0 2px 0;
            color: #1E40AF;
            font-weight: 700;
        }}
        h2 {{
            font-size: 13pt;
            margin: 22px 0 10px 0;
            color: #1E3A5F;
            border-bottom: 2px solid #2563EB;
            padding-bottom: 5px;
            font-weight: 700;
        }}
        .academy-en {{
            font-size: 11pt;
            color: #64748B;
            margin-bottom: 4px;
        }}
        .report-title {{
            font-size: 11pt;
            color: #2563EB;
            font-weight: 600;
        }}
        .muted {{ color: #64748B; }}
        .small {{ font-size: 9.5pt; }}
        .tiny  {{ font-size: 8.5pt; }}

        table {{ border-collapse: collapse; width: 100%; }}
        td {{ padding: 6px 8px; vertical-align: top; }}

        .kv td:first-child {{
            color: #64748B;
            width: 160px;
            font-weight: 600;
        }}

        /* KPI summary boxes */
        .kpi-table {{ width: 100%; margin-top: 6px; }}
        .kpi-table td {{
            text-align: center;
            vertical-align: middle;
            background: #F1F5F9;
            border: 1px solid #DCE3EC;
            border-radius: 6px;
            padding: 10px 6px;
            width: 25%;
        }}
        .kpi-value {{
            font-size: 20pt;
            font-weight: 700;
            color: #1E40AF;
            line-height: 1.1;
        }}
        .kpi-value.green  {{ color: #16A34A; }}
        .kpi-value.red    {{ color: #DC2626; }}
        .kpi-label {{
            font-size: 8.5pt;
            color: #64748B;
            margin-top: 2px;
        }}

        /* Subscription cards */
        .sub-box {{
            padding: 10px 14px;
            margin: 6px 0;
            background: #F8FAFC;
            border: 1px solid #DCE3EC;
            border-radius: 6px;
        }}
        .sub-box .sub-title {{
            font-size: 12pt;
            font-weight: 700;
            color: #172033;
            margin-bottom: 4px;
        }}

        /* Timeline */
        .month-head {{
            background: #EEF2F7;
            color: #1E40AF;
            padding: 6px 12px;
            font-weight: 700;
            font-size: 11pt;
            margin-top: 12px;
            border-left: 4px solid #2563EB;
        }}
        .event-row td {{
            border-bottom: 1px dotted #DCE3EC;
            padding: 5px 8px;
        }}
        .event-time {{
            color: #64748B;
            font-size: 9.5pt;
            width: 130px;
            white-space: nowrap;
        }}
        .event-badge {{
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 5px;
            margin-right: 6px;
        }}
        .badge-attendance   {{ background: #2563EB; }}
        .badge-payment      {{ background: #16A34A; }}
        .badge-subscription {{ background: #D97706; }}
        .badge-player       {{ background: #8B5CF6; }}
        .badge-admin        {{ background: #64748B; }}

        /* Footer */
        .footer {{
            margin-top: 24px;
            padding-top: 8px;
            border-top: 1px solid #DCE3EC;
            font-size: 8.5pt;
            color: #64748B;
            text-align: center;
        }}
    </style>
    """)

    # ---------- Header block ----------
    parts.append(f"""
    <div style="text-align: {align_start};">
      <h1>{_esc(academy_ar)}</h1>
      <div class="academy-en">{_esc(academy)}</div>
      <div class="report-title">{t("history.report_title")}</div>
    </div>
    <hr style="border: none; border-top: 2px solid #2563EB; margin: 14px 0 0 0;"/>
    """)

    # ---------- Player details ----------
    parts.append(f'<h2>{t("history.report.player_section")}</h2>')
    parts.append(f"""
    <table class="kv" {_dir_attr()}>
      <tr><td>{t("history.report.name")}</td><td><b>{_esc(player.full_name)}</b></td></tr>
      <tr><td>{t("history.report.player_id")}</td><td>{_esc(player.player_id)}</td></tr>
      <tr><td>{t("history.report.phone")}</td><td>{_esc(player.phone)}</td></tr>
      <tr><td>{t("history.report.national_id")}</td><td>{_esc(player.national_id or '—')}</td></tr>
      <tr><td>{t("history.report.dob")}</td><td>{_esc(player.dob)}</td></tr>
    </table>
    """)

    # ---------- KPI summary ----------
    parts.append(f'<h2>{t("history.report.summary_section")}</h2>')
    parts.append('<table class="kpi-table"><tr>')
    parts.append(
        f'<td><div class="kpi-value">{total_attended}</div>'
        f'<div class="kpi-label">{t("progress.kpi.total")}</div></td>'
    )
    parts.append(
        f'<td><div class="kpi-value green">{this_month}</div>'
        f'<div class="kpi-label">{t("progress.kpi.this_month")}</div></td>'
    )
    if active_subs:
        parts.append(
            f'<td><div class="kpi-value">{remaining_total} / {sessions_total}</div>'
            f'<div class="kpi-label">{t("progress.kpi.remaining")}</div></td>'
        )
    else:
        parts.append(
            f'<td><div class="kpi-value muted">—</div>'
            f'<div class="kpi-label">{t("progress.kpi.remaining")}</div></td>'
        )
    if total_denied > 0:
        parts.append(
            f'<td><div class="kpi-value red">{total_denied}</div>'
            f'<div class="kpi-label">{t("progress.kpi.denials")}</div></td>'
        )
    else:
        parts.append(
            f'<td><div class="kpi-value muted">0</div>'
            f'<div class="kpi-label">{t("progress.kpi.denials")}</div></td>'
        )
    parts.append('</tr></table>')

    # Total paid line
    if total_paid > 0:
        parts.append(
            f'<p style="text-align: {align_start}; margin-top: 10px;">'
            f'<b>{t("history.report.total_paid")}:</b> '
            f'<span style="color: #16A34A; font-size: 12pt; font-weight: 700;">'
            f'{total_paid:,.0f} EGP</span></p>'
        )

    # ---------- Active subscriptions ----------
    if active_subs:
        parts.append(f'<h2>{t("history.report.active_subs_section")}</h2>')
        for sub in active_subs:
            parts.append(_sub_block(sub, is_active=True))

    # ---------- Past subscriptions ----------
    past = [s for s in all_subs if s not in active_subs]
    if past:
        parts.append(f'<h2>{t("history.report.all_subs_section")}</h2>')
        for sub in past:
            parts.append(_sub_block(sub, is_active=False))

    # ---------- Timeline ----------
    if timeline:
        parts.append(f'<h2>{t("history.report.timeline_section")}</h2>')

        groups = OrderedDict()
        for e in timeline:
            ym = e.when[:7]
            groups.setdefault(ym, []).append(e)

        for ym, events in groups.items():
            parts.append(f'<div class="month-head">{_month_label(ym)}</div>')
            parts.append('<table>')
            for e in events:
                when = e.when[:16]
                badge_class = _badge_class(e.kind)
                parts.append(
                    f'<tr class="event-row">'
                    f'<td class="event-time">{_esc(when)}</td>'
                    f'<td><span class="event-badge {badge_class}"></span> '
                    f'{_esc(e.summary)}</td>'
                    f'</tr>'
                )
            parts.append('</table>')

    # ---------- Footer ----------
    from app_state import app as app_state
    user = app_state.user
    user_str = user.username if user else "system"
    parts.append(
        f'<div class="footer">'
        f'{t("history.report.footer_generated_by")}: {_esc(user_str)} '
        f'· {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        f'</div>'
    )

    return "".join(parts)


def _badge_class(kind: str) -> str:
    return {
        "attendance":   "badge-attendance",
        "payment":      "badge-payment",
        "subscription": "badge-subscription",
        "player":       "badge-player",
        "admin":        "badge-admin",
    }.get(kind, "badge-admin")


def _sub_block(sub, is_active: bool) -> str:
    act = activity_service.get(sub.activity_id) if sub.activity_id else None
    act_name = activity_service.get_localized_name(act) if act else "—"
    plan_text = get_plan_label(sub.plan_type) if sub.plan_type else t("detail.sub.custom")

    used = sub.sessions_total - sub.sessions_remaining
    payment_line = ""
    if sub.payment_amount is not None and sub.payment_amount > 0:
        payment_line = (
            f'<div class="muted small">'
            f'{t("progress.hist.payment", amount=f"{sub.payment_amount:,.0f}", date=sub.payment_date or "—")}'
            f'</div>'
        )

    days = ", ".join(t(f"weekday.{d.lower()}") for d in (sub.allowed_days or []))

    status_text = {
        "active":    t("players.status.active"),
        "expired":   t("players.status.expired"),
        "suspended": t("players.status.suspended"),
    }.get(sub.status, t("players.status.none"))

    return f"""
    <div class="sub-box">
      <div class="sub-title">{_esc(plan_text)} · {_esc(act_name)}
        <span class="muted small">— {_esc(status_text)}</span>
      </div>
      <div class="muted small">{t("progress.hist.dates", start=sub.start_date, end=sub.expiry_date)}</div>
      <div class="muted small">{t("progress.hist.sessions", used=used, total=sub.sessions_total, remaining=sub.sessions_remaining)}</div>
      {payment_line}
      <div class="muted small">{t("progress.hist.days", days=_esc(days))}</div>
    </div>
    """


def _month_label(ym: str) -> str:
    try:
        year, month = ym.split("-")
        return f"{t(MONTH_KEYS[int(month)-1])} {year}"
    except Exception:
        return ym