from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


BG = "#0b1623"
PANEL = "#162235"
TEXT = "#e5edf8"
MUTED = "#9db3cd"
GRID = "#48617c"
BLUE = "#3b82f6"
CYAN = "#22d3ee"
GREEN = "#10b981"
AMBER = "#f59e0b"
RED = "#ef4444"
PURPLE = "#a78bfa"
GRAY = "#94a3b8"

EVENT_COLORS = {
    "AUTHORIZED": GREEN,
    "UNKNOWN": AMBER,
    "DOOR_FORCE": BLUE,
    "SMOKE_HIGH": RED,
    "SMOKE_NORMAL": CYAN,
    "SMOKE_WARNING": AMBER,
    "FLAME_SIGNAL": RED,
}

ALERT_COLORS = {
    "AUTHORIZED_ENTRY": GREEN,
    "INTRUDER": BLUE,
    "SMOKE_WARNING": AMBER,
    "FIRE": RED,
    "CAMERA_OFFLINE": PURPLE,
    "NODE_OFFLINE": GRAY,
}

CONFUSION_LABEL_ORDER = [
    "NORMAL",
    "SMOKE",
    "FIRE",
    "INTRUDER",
    "AUTHORIZED",
    "NON_AUTHORIZED",
    "NO_FACE",
]


def load_json_rows(path: Path, key: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    rows = payload.get(key, [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def parse_ts(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def setup_ax(ax: plt.Axes, title: str, subtitle: str = "") -> None:
    ax.set_facecolor(PANEL)
    ax.set_title(title, loc="left", color=TEXT, fontsize=18, fontweight="bold", pad=22)
    if subtitle:
        ax.text(
            0,
            1.02,
            subtitle,
            transform=ax.transAxes,
            color=MUTED,
            fontsize=11,
            va="bottom",
        )
    ax.tick_params(colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color("#24425f")
    ax.grid(axis="y", color=GRID, linestyle="--", linewidth=0.8, alpha=0.75)
    ax.set_axisbelow(True)


def save_fig(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=180, facecolor=BG, bbox_inches="tight")
    plt.close(fig)


def compute_mean_latency(events: list[dict[str, Any]], alerts: list[dict[str, Any]]) -> float:
    event_ts_by_id = {
        str(row.get("id") or ""): parse_ts(row.get("timestamp")) for row in events
    }
    latencies: list[float] = []
    for alert in alerts:
        event_ts = event_ts_by_id.get(str(alert.get("event_id") or ""))
        alert_ts = parse_ts(alert.get("timestamp"))
        if event_ts is None or alert_ts is None:
            continue
        latencies.append(max(0.0, (alert_ts - event_ts).total_seconds()))
    return sum(latencies) / len(latencies) if latencies else 0.0


def compute_latency_by_type(
    events: list[dict[str, Any]], alerts: list[dict[str, Any]]
) -> dict[str, float]:
    event_ts_by_id = {
        str(row.get("id") or ""): parse_ts(row.get("timestamp")) for row in events
    }
    latencies_by_type: dict[str, list[float]] = defaultdict(list)
    for alert in alerts:
        event_ts = event_ts_by_id.get(str(alert.get("event_id") or ""))
        alert_ts = parse_ts(alert.get("timestamp"))
        if event_ts is None or alert_ts is None:
            continue
        alert_type = str(alert.get("event_code") or "UNKNOWN")
        latencies_by_type[alert_type].append(
            max(0.0, (alert_ts - event_ts).total_seconds())
        )
    return {
        alert_type: sum(values) / len(values)
        for alert_type, values in latencies_by_type.items()
        if values
    }


def dashboard_metrics(
    events: list[dict[str, Any]], alerts: list[dict[str, Any]]
) -> dict[str, float]:
    event_counts = Counter(str(row.get("event_code") or "") for row in events)
    alert_counts = Counter(str(row.get("event_code") or "") for row in alerts)
    dates = {
        ts.date()
        for ts in (parse_ts(row.get("timestamp")) for row in events + alerts)
        if ts is not None
    }
    days = max(1, len(dates))
    authorized = float(event_counts["AUTHORIZED"])
    unknown = float(event_counts["UNKNOWN"])
    fire_alerts = float(alert_counts["FIRE"])
    smoke_alerts = float(alert_counts["SMOKE_WARNING"])
    return {
        "Authorized Face Detections": authorized,
        "Unknown Detections": unknown,
        "Fire Fusion Alerts": fire_alerts,
        "Intruder Fusion Alerts": float(alert_counts["INTRUDER"]),
        "Average Response Time (s)": compute_mean_latency(events, alerts),
        "Authorized Detection Share (%)": authorized / max(1.0, authorized + unknown) * 100.0,
        "Alert Rate (/day)": len(alerts) / days,
        "Fire Evidence Conversion (%)": fire_alerts / max(1.0, fire_alerts + smoke_alerts) * 100.0,
    }


def save_dashboard_summary(path: Path, metrics: dict[str, float]) -> None:
    fig, ax = plt.subplots(figsize=(13.6, 7.2), facecolor=BG)
    ax.set_facecolor(BG)
    ax.axis("off")
    fig.suptitle(
        "Dashboard Statistics Summary",
        x=0.05,
        y=0.96,
        ha="left",
        color=TEXT,
        fontsize=22,
        fontweight="bold",
    )
    ax.text(
        0.03,
        0.89,
        "Generated from exported Chapter 4 event and alert logs",
        color=MUTED,
        fontsize=12,
        transform=ax.transAxes,
    )

    colors = [GREEN, AMBER, RED, BLUE, CYAN, GREEN, BLUE, RED]
    for index, (label, value) in enumerate(metrics.items()):
        row = index // 4
        col = index % 4
        x = 0.03 + col * 0.24
        y = 0.58 - row * 0.28
        width = 0.21
        height = 0.18
        ax.add_patch(
            plt.Rectangle(
                (x, y),
                width,
                height,
                transform=ax.transAxes,
                facecolor=PANEL,
                edgecolor="#24425f",
                linewidth=1.2,
            )
        )
        display = (
            f"{value:.2f}"
            if "Response" in label
            else f"{value:.1f}"
            if "%" in label or "/day" in label
            else f"{value:.0f}"
        )
        ax.text(x + 0.02, y + height - 0.055, label, color=MUTED, fontsize=10, transform=ax.transAxes)
        ax.text(
            x + 0.02,
            y + 0.055,
            display,
            color=TEXT,
            fontsize=26,
            fontweight="bold",
            transform=ax.transAxes,
        )
        ax.scatter(
            [x + width - 0.04],
            [y + 0.09],
            s=360,
            color=colors[index],
            alpha=0.22,
            transform=ax.transAxes,
        )
        ax.scatter(
            [x + width - 0.04],
            [y + 0.09],
            s=70,
            color=colors[index],
            transform=ax.transAxes,
        )
    save_fig(fig, path)


def save_bar_chart(
    path: Path,
    title: str,
    subtitle: str,
    data: dict[str, int | float],
    colors: dict[str, str],
) -> None:
    fig, ax = plt.subplots(figsize=(13.6, 7.2), facecolor=BG)
    setup_ax(ax, title, subtitle)
    labels = list(data.keys())
    values = [float(data[label]) for label in labels]
    bar_colors = [colors.get(label, BLUE) for label in labels]
    ax.bar(labels, values, color=bar_colors, edgecolor="none")
    ax.set_ylabel("Count", color=MUTED)
    ax.tick_params(axis="x", rotation=25)
    for index, value in enumerate(values):
        ax.text(index, value, f"{value:.0f}", ha="center", va="bottom", color=TEXT, fontsize=10)
    save_fig(fig, path)


def daily_series(
    events: list[dict[str, Any]], alerts: list[dict[str, Any]]
) -> tuple[list[str], dict[str, list[int]], dict[str, list[int]]]:
    dates = sorted(
        {
            str(row.get("timestamp") or "")[:10]
            for row in events + alerts
            if str(row.get("timestamp") or "")[:10]
        }
    )
    event_by_day: dict[str, Counter[str]] = defaultdict(Counter)
    alert_by_day: dict[str, Counter[str]] = defaultdict(Counter)
    for event in events:
        day = str(event.get("timestamp") or "")[:10]
        if day:
            event_by_day[day][str(event.get("event_code") or "")] += 1
    for alert in alerts:
        day = str(alert.get("timestamp") or "")[:10]
        if day:
            alert_by_day[day][str(alert.get("event_code") or "")] += 1

    events_series = {
        "Authorized": [event_by_day[day]["AUTHORIZED"] for day in dates],
        "Unknown": [event_by_day[day]["UNKNOWN"] for day in dates],
        "Smoke High": [
            event_by_day[day]["SMOKE_HIGH"] + event_by_day[day]["SMOKE_WARNING"]
            for day in dates
        ],
        "Door Force": [event_by_day[day]["DOOR_FORCE"] for day in dates],
    }
    alerts_series = {
        "Fire Alerts": [alert_by_day[day]["FIRE"] for day in dates],
        "Intruder Alerts": [alert_by_day[day]["INTRUDER"] for day in dates],
        "Smoke Alerts": [alert_by_day[day]["SMOKE_WARNING"] for day in dates],
    }
    return dates, events_series, alerts_series


def save_grouped_bar_chart(
    path: Path,
    title: str,
    subtitle: str,
    dates: list[str],
    series: dict[str, list[int]],
    colors: dict[str, str],
) -> None:
    fig, ax = plt.subplots(figsize=(13.6, 7.2), facecolor=BG)
    setup_ax(ax, title, subtitle)
    names = list(series.keys())
    x_positions = list(range(len(dates)))
    group_width = 0.78
    bar_width = group_width / max(1, len(names))
    for offset, name in enumerate(names):
        positions = [x - group_width / 2 + bar_width / 2 + offset * bar_width for x in x_positions]
        ax.bar(positions, series[name], width=bar_width * 0.88, label=name, color=colors.get(name, BLUE))
    ax.set_xticks(x_positions)
    ax.set_xticklabels(dates, rotation=0)
    ax.set_ylabel("Count", color=MUTED)
    legend = ax.legend(facecolor=PANEL, edgecolor="#24425f", labelcolor=TEXT)
    for text in legend.get_texts():
        text.set_color(TEXT)
    save_fig(fig, path)


def save_latency_chart(path: Path, events: list[dict[str, Any]], alerts: list[dict[str, Any]]) -> None:
    data = compute_latency_by_type(events, alerts)
    fig, ax = plt.subplots(figsize=(13.6, 7.2), facecolor=BG)
    setup_ax(
        ax,
        "Response-Time Summary",
        "Mean event-to-alert latency in seconds by alert type",
    )
    labels = list(data.keys())
    values = [float(data[label]) for label in labels]
    ax.bar(labels, values, color=[ALERT_COLORS.get(label, BLUE) for label in labels])
    ax.set_ylabel("Seconds", color=MUTED)
    ax.tick_params(axis="x", rotation=25)
    upper = max(values + [0.1]) * 1.25
    ax.set_ylim(0, upper)
    for index, value in enumerate(values):
        ax.text(index, value, f"{value:.3f}s", ha="center", va="bottom", color=TEXT, fontsize=10)
    save_fig(fig, path)


def save_confusion_matrix(path: Path, title: str, rows: list[dict[str, str]]) -> bool:
    usable = [
        row
        for row in rows
        if row.get("expected_label", "").strip()
        and row.get("predicted_label", "").strip()
        and row.get("remarks", "").strip().lower() != "excluded from computation"
    ]
    if not usable:
        return False

    labels = sorted(
        {
            row["expected_label"].strip()
            for row in usable
        }
        | {row["predicted_label"].strip() for row in usable},
        key=lambda label: (
            CONFUSION_LABEL_ORDER.index(label)
            if label in CONFUSION_LABEL_ORDER
            else 999,
            label,
        ),
    )
    index_by_label = {label: index for index, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for row in usable:
        expected = row["expected_label"].strip()
        predicted = row["predicted_label"].strip()
        matrix[index_by_label[expected]][index_by_label[predicted]] += 1

    correct = sum(matrix[index][index] for index in range(len(labels)))
    total = len(usable)
    accuracy = correct / total * 100.0 if total else 0.0

    fig, ax = plt.subplots(figsize=(9.2, 8.2), facecolor=BG)
    ax.set_facecolor(PANEL)
    image = ax.imshow(matrix, cmap="Blues")
    ax.set_title(
        f"{title}\nTotal evaluated trials: {total}; accuracy: {accuracy:.1f}%",
        color=TEXT,
        fontsize=15,
        fontweight="bold",
        pad=18,
    )
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, color=MUTED, rotation=35, ha="right")
    ax.set_yticklabels(labels, color=MUTED)
    ax.set_xlabel("Predicted Label", color=TEXT, labelpad=12)
    ax.set_ylabel("Expected Label", color=TEXT, labelpad=12)
    for row_index, row_values in enumerate(matrix):
        for col_index, value in enumerate(row_values):
            ax.text(col_index, row_index, str(value), ha="center", va="center", color=TEXT, fontsize=14, fontweight="bold")
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(colorbar.ax.get_yticklabels(), color=MUTED)
    save_fig(fig, path)
    return True


def write_metrics_csv(path: Path, metrics: dict[str, float]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["metric", "value"])
        for key, value in metrics.items():
            writer.writerow([key, f"{value:.4f}" if math.isfinite(value) else "0"])


def write_dashboard_html(path: Path, figure_paths: list[Path]) -> None:
    cards = "\n".join(
        f'<section><h2>{figure.stem.replace("_", " ").title()}</h2><img src="{figure.name}" alt="{figure.stem}"></section>'
        for figure in figure_paths
    )
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Chapter 4 Generated Figures</title>
  <style>
    body {{ margin: 0; background: {BG}; color: {TEXT}; font-family: Arial, sans-serif; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 28px; }}
    h1 {{ margin: 0 0 8px; }}
    p {{ color: {MUTED}; }}
    section {{ margin: 28px 0; padding: 18px; background: {PANEL}; border: 1px solid #24425f; border-radius: 16px; }}
    img {{ width: 100%; height: auto; display: block; border-radius: 12px; }}
  </style>
</head>
<body>
  <main>
    <h1>Chapter 4 Generated Figures</h1>
    <p>Generated from the exported event logs, alert logs, and trial review sheet.</p>
    {cards}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Chapter 4 dashboard graphs and confusion matrices."
    )
    parser.add_argument("--events", default="chapter4_events_log.json", type=Path)
    parser.add_argument("--alerts", default="chapter4_alerts_log.json", type=Path)
    parser.add_argument("--trials", default="chapter4_trial_review_sheet.csv", type=Path)
    parser.add_argument("--output-dir", default="chapter4_outputs", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    events = load_json_rows(args.events, "events")
    alerts = load_json_rows(args.alerts, "alerts")
    trials = load_csv_rows(args.trials)
    figures: list[Path] = []

    metrics = dashboard_metrics(events, alerts)
    path = args.output_dir / "01_dashboard_statistics_summary.png"
    save_dashboard_summary(path, metrics)
    figures.append(path)

    event_counts = dict(Counter(str(row.get("event_code") or "") for row in events).most_common(10))
    path = args.output_dir / "02_event_code_distribution.png"
    save_bar_chart(
        path,
        "Event Code Distribution",
        "Latest exported event records by event code",
        event_counts,
        EVENT_COLORS,
    )
    figures.append(path)

    dates, event_series, alert_series = daily_series(events, alerts)
    path = args.output_dir / "03_daily_event_trend.png"
    save_grouped_bar_chart(
        path,
        "Daily Event Trend",
        "Authorized, unknown, smoke, and door-force events by date",
        dates,
        event_series,
        {"Authorized": GREEN, "Unknown": AMBER, "Smoke High": RED, "Door Force": BLUE},
    )
    figures.append(path)

    path = args.output_dir / "04_fire_evidence_and_fusion_outputs.png"
    save_grouped_bar_chart(
        path,
        "Fire Evidence and Fusion Alert Outputs",
        "Daily fire, smoke, and intruder alert outputs",
        dates,
        alert_series,
        {"Fire Alerts": RED, "Intruder Alerts": BLUE, "Smoke Alerts": AMBER},
    )
    figures.append(path)

    severity_counts = dict(Counter(str(row.get("severity") or "") for row in alerts))
    path = args.output_dir / "05_alert_severity_distribution.png"
    save_bar_chart(
        path,
        "Alert Severity Distribution",
        "Latest exported alert records by severity",
        severity_counts,
        {"critical": RED, "warning": AMBER, "info": GREEN, "normal": CYAN},
    )
    figures.append(path)

    path = args.output_dir / "06_response_time_summary.png"
    save_latency_chart(path, events, alerts)
    figures.append(path)

    write_metrics_csv(args.output_dir / "chapter4_metrics_summary.csv", metrics)

    matrix_count = 0
    path = args.output_dir / "07_confusion_matrix_all.png"
    if save_confusion_matrix(path, "Overall Confusion Matrix", trials):
        figures.append(path)
        matrix_count += 1
        for module in sorted({row.get("module", "") for row in trials if row.get("module", "")}):
            module_rows = [row for row in trials if row.get("module") == module]
            module_path = args.output_dir / f"08_confusion_matrix_{module}.png"
            if save_confusion_matrix(module_path, f"{module.title()} Confusion Matrix", module_rows):
                figures.append(module_path)
                matrix_count += 1

    status = (
        f"Generated {matrix_count} confusion matrix figure(s).\n"
        if matrix_count
        else "No confusion matrix generated yet. Fill expected_label in chapter4_trial_review_sheet.csv, then rerun this script.\n"
    )
    (args.output_dir / "confusion_matrix_status.txt").write_text(status, encoding="utf-8")
    write_dashboard_html(args.output_dir / "chapter4_dashboard.html", figures)
    print(f"Generated {len(figures)} PNG figure(s) in {args.output_dir}")
    print(f"Open {args.output_dir / 'chapter4_dashboard.html'} to preview them together")


if __name__ == "__main__":
    main()
