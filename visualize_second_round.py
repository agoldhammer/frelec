#!/usr/bin/env python3
"""Plot second-round (runoff) hypothetical matchup polls for the 2027
French presidential election.

Reads polls_2027_second_round.csv (one row per poll per matchup, e.g.
"Attal vs. Bardella") and renders two charts:

- a trend chart: each challenger's share against the RN candidate (whether
  Bardella or Le Pen) over time
- a snapshot chart: the most recent poll for each matchup, as a stacked bar
  split at the 50% majority line

Usage:
    python3 visualize_second_round.py [--dark] [-o OUTPUT_PREFIX]
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from visualize_polls import FRENCH_MONTHS, SERIES, THEMES, spread_labels

CSV_PATH = "polls_2027_second_round.csv"

# Reuse first-round colors for challengers that also appear in the
# first-round palette; Ruffin only runs in the runoff tables, so he gets a
# new slot validated with scripts/validate_palette.js against that same
# 8-color set (light: chroma/lightness/CVD all PASS; dark: CVD separation
# WARN in the 8-12 floor band, acceptable because this chart direct-labels
# every line).
CHALLENGERS = {
    "Attal_RE":       SERIES["Attal_RE"],
    "Philippe_HOR":   SERIES["Philippe_HOR"],
    "Melenchon_LFI":  SERIES["Melenchon_LFI"],
    "Glucksmann_PP":  SERIES["Glucksmann_PP"],
    "Retailleau_LR":  SERIES["Retailleau_LR"],
    "Ruffin_D":       ("Ruffin (D!)", "#8a5a13", "#b8863d"),
}

RN_CANDIDATES = {
    "Bardella_RN": ("Bardella", SERIES["RN"][1], SERIES["RN"][2]),
    "LePen_RN":    ("Le Pen", SERIES["RN"][1], SERIES["RN"][2]),
}

# Le Pen's shifting legal/candidacy status, relevant to every matchup
# against RN in this dataset.
EVENTS = {
    date(2025, 3, 31): "Inéligibilité (1re instance)",
    date(2026, 7, 7): "Candidature officialisée",
}


def parse_matchup_date(text):
    """Return the midpoint date of a dated field-period string that carries
    its own year, e.g. "25 - 27 mai 2026" or "31 janvier - 1er février 2024".
    """
    text = text.strip().lower().replace("–", "-").replace("—", "-")
    parts = [p.strip() for p in text.split("-")]

    def to_day(tok):
        return 1 if tok in ("1er", "1e") else int(tok)

    end_tokens = parts[-1].split()
    year = int(end_tokens[-1])
    end_month = FRENCH_MONTHS[end_tokens[-2]]
    end_day = to_day(end_tokens[-3])

    if len(parts) == 1:
        return date(year, end_month, end_day)
    start_tokens = parts[0].split()
    if len(start_tokens) == 1:
        start_day, start_month = to_day(start_tokens[0]), end_month
    else:
        start_day, start_month = to_day(start_tokens[0]), FRENCH_MONTHS[start_tokens[1]]
    start = date(year, start_month, start_day)
    end = date(year, end_month, end_day)
    return start + (end - start) / 2


def load_runoff(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "matchup": row["matchup"],
                "candidate_a": row["candidate_a"], "candidate_b": row["candidate_b"],
                "pollster": row["pollster"], "date": parse_matchup_date(row["date"]),
                "pct_a": float(row["pct_a"]), "pct_b": float(row["pct_b"]),
            })
    rows.sort(key=lambda r: r["date"])
    return rows


def style_axes(ax, theme):
    ax.yaxis.grid(True, color=theme["grid"], linewidth=1.0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme["baseline"])
    ax.tick_params(colors=theme["muted"], labelsize=9, length=0)


def plot_runoff_trend(rows, theme, dark, out_path):
    by_challenger = defaultdict(list)
    for r in rows:
        by_challenger[r["candidate_a"]].append((r["date"], r["pct_a"]))

    fig, ax = plt.subplots(figsize=(10.5, 6.3), dpi=160)
    fig.patch.set_facecolor(theme["page"])
    ax.set_facecolor(theme["surface"])
    style_axes(ax, theme)

    ax.axhline(50, color=theme["baseline"], linewidth=1.2, linestyle=(0, (4, 3)))

    labels = []  # [y, name, value, color]
    for key, pts in by_challenger.items():
        pts.sort()
        name, light_hex, dark_hex = CHALLENGERS[key]
        color = dark_hex if dark else light_hex
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=color, linewidth=1.8, marker="o", markersize=5,
                 markeredgecolor=theme["surface"], markeredgewidth=1,
                 solid_capstyle="round", zorder=3)
        labels.append([ys[-1], name, ys[-1], color])

    all_dates = [d for pts in by_challenger.values() for d, _ in pts]
    start, end = min(all_dates), max(all_dates)
    for ev_date, ev_label in EVENTS.items():
        if start <= ev_date <= end:
            ax.axvline(ev_date, color=theme["muted"], linewidth=0.8,
                        linestyle=(0, (4, 4)), alpha=0.6)
            ax.annotate(ev_label, (ev_date, 0.985), xycoords=("data", "axes fraction"),
                        xytext=(-4, 0), textcoords="offset points",
                        ha="right", va="top", fontsize=7.5, color=theme["muted"],
                        rotation=90, annotation_clip=False)

    ax.set_ylim(20, 80)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.annotate("50 % — majorité", (start, 50), xytext=(0, 4),
                textcoords="offset points", fontsize=8.5, color=theme["muted"])

    labels.sort(key=lambda r: r[0])
    spread_labels(labels, min_gap=(ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.05)
    x_text = end + timedelta(days=25)
    for y, name, value, color in labels:
        if abs(y - value) > 0.2:
            ax.plot([end + timedelta(days=8), x_text], [value, y],
                    color=theme["baseline"], linewidth=0.8, clip_on=False, zorder=1)
        ax.annotate(f"{name}  {value:.0f}%", (x_text, y),
                    va="center", fontsize=9, color=theme["ink"], annotation_clip=False)
        ax.scatter([x_text - timedelta(days=12)], [y], s=22, color=color,
                    clip_on=False, zorder=4)

    ax.set_xlim(start - timedelta(days=20), end + timedelta(days=20))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    ax.set_title("Présidentielle 2027 — second tour, hypothèses face au RN",
                 color=theme["ink"], fontsize=14, fontweight="semibold",
                 loc="left", pad=32)
    ax.text(0, 1.06,
            "Score de chaque candidat face au RN (Bardella ou Le Pen selon le "
            "sondage) · points = sondages individuels",
            transform=ax.transAxes, fontsize=9, color=theme["secondary"])
    fig.text(0.06, 0.015,
             "Source : Wikipédia, « Liste de sondages sur l'élection "
             "présidentielle française de 2027 » (sondages second tour).",
             fontsize=8, color=theme["muted"])

    fig.subplots_adjust(left=0.06, right=0.80, top=0.85, bottom=0.11)
    fig.savefig(out_path, facecolor=fig.get_facecolor())
    print(f"wrote {out_path}")


def plot_runoff_snapshot(rows, theme, dark, out_path):
    latest = {}
    for r in rows:
        latest[r["matchup"]] = r  # rows sorted ascending by date; last wins

    order_b = {"LePen_RN": 0, "Bardella_RN": 1}
    matchups = sorted(latest.values(),
                       key=lambda r: (order_b.get(r["candidate_b"], 2), r["pct_b"]))

    fig, ax = plt.subplots(figsize=(10.5, 0.95 * len(matchups) + 1.6), dpi=160)
    fig.patch.set_facecolor(theme["page"])
    ax.set_facecolor(theme["surface"])

    for y, r in enumerate(matchups):
        chal_name, chal_light, chal_dark = CHALLENGERS[r["candidate_a"]]
        rn_name, rn_light, rn_dark = RN_CANDIDATES[r["candidate_b"]]
        chal_color = chal_dark if dark else chal_light
        rn_color = rn_dark if dark else rn_light

        ax.barh(y, r["pct_a"], left=0, height=0.6, color=chal_color,
                edgecolor=theme["surface"], linewidth=2, zorder=2)
        ax.barh(y, r["pct_b"], left=r["pct_a"], height=0.6, color=rn_color,
                edgecolor=theme["surface"], linewidth=2, zorder=2)

        ax.annotate(f"{chal_name}  {r['pct_a']:.0f}", (r["pct_a"] / 2, y),
                    ha="center", va="center", fontsize=9.5, color="#ffffff")
        ax.annotate(f"{rn_name}  {r['pct_b']:.0f}",
                    (r["pct_a"] + r["pct_b"] / 2, y),
                    ha="center", va="center", fontsize=9.5, color="#ffffff")
        ax.annotate(f"{r['pollster']} · {r['date']:%d %b %Y}", (0, y),
                    xytext=(0, 22), textcoords="offset points",
                    va="center", fontsize=9, color=theme["secondary"])

    ax.axvline(50, color=theme["ink"], linewidth=1, linestyle=(0, (4, 3)))
    ax.annotate("50 %", (50, 1.0), xycoords=("data", "axes fraction"),
                xytext=(0, 6), textcoords="offset points",
                ha="center", fontsize=9, color=theme["ink"])

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, len(matchups) - 0.35)
    ax.set_yticks([])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.xaxis.grid(True, color=theme["grid"], linewidth=1.0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme["baseline"])
    ax.tick_params(colors=theme["muted"], labelsize=9, length=0)

    fig.text(0.045, 0.965,
             "Présidentielle 2027 — second tour, dernier sondage par hypothèse",
             fontsize=14, color=theme["ink"], fontweight="semibold", va="top")
    fig.text(0.045, 0.925,
             "Chaque barre = le sondage le plus récent pour ce duel · "
             "trait pointillé = seuil de majorité (50 %)",
             fontsize=9, color=theme["secondary"], va="top")
    fig.text(0.99, 0.015,
             "Source : Wikipédia, « Liste de sondages sur l'élection "
             "présidentielle française de 2027 » (sondages second tour).",
             ha="right", fontsize=8, color=theme["muted"])

    fig.subplots_adjust(left=0.045, right=0.97, top=0.85, bottom=0.05)
    fig.savefig(out_path, facecolor=fig.get_facecolor())
    print(f"wrote {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dark", action="store_true", help="dark theme")
    ap.add_argument("--csv", default=CSV_PATH, help="input CSV path")
    ap.add_argument("-o", "--output-prefix", default=None,
                     help="output path prefix (default: france-second_round)")
    args = ap.parse_args()

    theme = THEMES["dark" if args.dark else "light"]
    suffix = "_dark" if args.dark else ""
    prefix = args.output_prefix or "france-second_round"

    rows = load_runoff(args.csv)
    if not rows:
        sys.exit("no polls parsed — check the CSV path/format")

    plot_runoff_trend(rows, theme, args.dark, f"{prefix}_trend{suffix}.png")
    plot_runoff_snapshot(rows, theme, args.dark, f"{prefix}_snapshot{suffix}.png")


if __name__ == "__main__":
    main()
