from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from math import ceil
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe_text(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "-"


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(_safe_text(value)), style)


def _as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _format_local_timestamp(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        local = parsed.astimezone()
        return local.strftime("%H:%M")
    except ValueError:
        return raw


def _status_label(value: Any) -> str:
    return _safe_text(value).replace("_", " ").upper()


def _build_trend_chart(stats_rows: list[dict[str, Any]]) -> Drawing:
    labels = [str(row.get("date") or "")[-5:] for row in stats_rows]
    fire_values = [_as_int(row.get("fire_alerts")) for row in stats_rows]
    intruder_values = [_as_int(row.get("intruder_alerts")) for row in stats_rows]
    unknown_values = [_as_int(row.get("unknown_detections")) for row in stats_rows]
    max_value = max([1, *fire_values, *intruder_values, *unknown_values])

    drawing = Drawing(7.0 * inch, 2.25 * inch)
    chart = VerticalBarChart()
    chart.x = 42
    chart.y = 36
    chart.height = 104
    chart.width = 360
    chart.data = [fire_values, intruder_values, unknown_values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(1, int(ceil(max_value / 2)) * 2)
    chart.valueAxis.valueStep = max(1, int(ceil(chart.valueAxis.valueMax / 4)))
    chart.valueAxis.labels.fontSize = 7
    chart.barSpacing = 1.5
    chart.groupSpacing = 8
    chart.bars[0].fillColor = colors.HexColor("#EF5350")
    chart.bars[1].fillColor = colors.HexColor("#FFA726")
    chart.bars[2].fillColor = colors.HexColor("#1E88E5")
    drawing.add(chart)

    legend = Legend()
    legend.x = 420
    legend.y = 102
    legend.fontSize = 7
    legend.boxAnchor = "nw"
    legend.columnMaximum = 3
    legend.colorNamePairs = [
        (colors.HexColor("#EF5350"), "Fire"),
        (colors.HexColor("#FFA726"), "Intruder"),
        (colors.HexColor("#1E88E5"), "Non-authorized"),
    ]
    drawing.add(legend)
    return drawing


def _table(data: list[list[Any]], col_widths: list[float] | None = None) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D47A1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6E4F0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F4F7FB")],
                ),
            ]
        )
    )
    return table


def _draw_footer(report_date: date):
    def _footer(canvas, doc) -> None:  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#4A6080"))
        canvas.drawString(
            36, 22, f"IntruFlare daily report for {report_date.isoformat()}"
        )
        canvas.drawRightString(A4[0] - 36, 22, f"Page {doc.page}")
        canvas.restoreState()

    return _footer


def build_daily_summary_pdf(
    *,
    report_date: date,
    generated_at: datetime,
    stats_rows: list[dict[str, Any]],
    alert_rows: list[dict[str, Any]],
    event_rows: list[dict[str, Any]],
    node_rows: list[dict[str, Any]],
) -> bytes:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0D1B2A"),
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "ReportSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0D47A1"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#263238"),
    )
    small_style = ParagraphStyle(
        "ReportSmall",
        parent=body_style,
        fontSize=8,
        leading=10,
    )

    selected_stats = next(
        (
            row
            for row in stats_rows
            if str(row.get("date") or "") == report_date.isoformat()
        ),
        {},
    )
    active_alerts = [row for row in alert_rows if not bool(row.get("acknowledged"))]
    online_nodes = sum(
        1 for row in node_rows if str(row.get("status") or "").strip().lower() == "online"
    )
    total_nodes = len(node_rows)
    fire_alerts = _as_int(selected_stats.get("fire_alerts"))
    intruder_alerts = _as_int(selected_stats.get("intruder_alerts"))
    unknown_detections = _as_int(selected_stats.get("unknown_detections"))
    authorized_faces = _as_int(selected_stats.get("authorized_faces"))
    smoke_events = _as_int(selected_stats.get("smoke_high_events"))
    flame_signals = _as_int(selected_stats.get("flame_signals"))

    if active_alerts:
        summary_state = f"{len(active_alerts)} active alert(s) still require attention."
    elif fire_alerts or intruder_alerts or unknown_detections or smoke_events or flame_signals:
        summary_state = "Incidents were recorded, but there are no active unresolved alerts."
    else:
        summary_state = "No critical activity was recorded for the selected day."

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=42,
        title=f"IntruFlare Daily Monitoring Report {report_date.isoformat()}",
    )

    story: list[Any] = []
    story.append(Paragraph("IntruFlare Daily Monitoring Report", title_style))
    story.append(
        Paragraph(
            f"Report date: <b>{report_date.isoformat()}</b><br/>Generated: "
            f"{generated_at.astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
            body_style,
        )
    )
    story.append(Spacer(1, 0.12 * inch))

    story.append(Paragraph("Executive Summary", section_style))
    story.append(
        Paragraph(
            escape(
                " ".join(
                    [
                        "The system monitored "
                        f"{total_nodes} deployed node(s), with {online_nodes} "
                        "online at generation time.",
                        "The selected day includes "
                        f"{len(alert_rows)} alert record(s) and "
                        f"{len(event_rows)} event record(s).",
                        summary_state,
                    ]
                )
            ),
            body_style,
        )
    )

    story.append(Paragraph("Key Metrics", section_style))
    story.append(
        _table(
            [
                ["Metric", "Value", "Metric", "Value"],
                [
                    "Active alerts",
                    len(active_alerts),
                    "Online nodes",
                    f"{online_nodes}/{total_nodes}",
                ],
                ["Fire alerts", fire_alerts, "Intruder alerts", intruder_alerts],
                [
                    "Authorized recognitions",
                    authorized_faces,
                    "Non-authorized detections",
                    unknown_detections,
                ],
                ["Smoke high events", smoke_events, "Flame signals", flame_signals],
            ],
            [1.75 * inch, 1.05 * inch, 1.9 * inch, 1.05 * inch],
        )
    )

    story.append(Paragraph("7-Day Incident Trend", section_style))
    story.append(_build_trend_chart(stats_rows))

    story.append(Paragraph("Deployed Node Status", section_style))
    node_data: list[list[Any]] = [["Node", "Type", "Location", "Status", "Note"]]
    for row in node_rows:
        node_data.append(
            [
                _paragraph(row.get("name") or row.get("id"), small_style),
                _status_label(row.get("type")),
                _paragraph(row.get("location"), small_style),
                _status_label(row.get("status")),
                _paragraph(row.get("note"), small_style),
            ]
        )
    if len(node_data) == 1:
        node_data.append(["-", "-", "-", "No node status available", "-"])
    story.append(
        _table(
            node_data,
            [1.55 * inch, 0.8 * inch, 1.35 * inch, 0.85 * inch, 1.75 * inch],
        )
    )

    story.append(Paragraph("Active Alerts", section_style))
    alert_data: list[list[Any]] = [["Time", "Severity", "Title", "Location", "Source"]]
    for row in active_alerts[:12]:
        alert_data.append(
            [
                _format_local_timestamp(row.get("timestamp")),
                _status_label(row.get("severity")),
                _paragraph(row.get("title"), small_style),
                _paragraph(row.get("location"), small_style),
                _paragraph(row.get("source_node"), small_style),
            ]
        )
    if len(alert_data) == 1:
        alert_data.append(["-", "-", "No active alerts", "-", "-"])
    story.append(
        _table(
            alert_data,
            [0.55 * inch, 0.75 * inch, 2.25 * inch, 1.3 * inch, 1.25 * inch],
        )
    )

    story.append(Paragraph("Recent Event Timeline", section_style))
    event_data: list[list[Any]] = [["Time", "Severity", "Code", "Source", "Summary"]]
    for row in event_rows[:24]:
        event_data.append(
            [
                _format_local_timestamp(row.get("timestamp")),
                _status_label(row.get("severity")),
                _paragraph(row.get("event_code"), small_style),
                _paragraph(row.get("source_node"), small_style),
                _paragraph(row.get("title") or row.get("description"), small_style),
            ]
        )
    if len(event_data) == 1:
        event_data.append(["-", "-", "-", "-", "No events recorded for this date"])
    story.append(
        _table(
            event_data,
            [0.55 * inch, 0.75 * inch, 1.15 * inch, 1.15 * inch, 2.5 * inch],
        )
    )

    story.append(Spacer(1, 0.16 * inch))
    story.append(
        Paragraph(
            "Snapshot thumbnails are intentionally excluded from this report version. "
            "Open the Alerts or Snapshots views for image evidence and bounding-box overlays.",
            small_style,
        )
    )

    footer = _draw_footer(report_date)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
