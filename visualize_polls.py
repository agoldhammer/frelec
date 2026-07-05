#!/usr/bin/env python3
"""Plot smoothed polling trends for the 2027 French presidential first round.

Reads data/polls_2027_presidential_first_round.csv (one row per poll
scenario), averages scenarios within each poll, then smooths each candidate's
series with a Gaussian kernel over time (default sigma = 15 days). Raw
per-scenario values are drawn as faint dots behind the trend lines.

Usage:
    python3 visualize_polls.py [--sigma DAYS] [--dark] [-o OUTPUT.png]
"""

import argparse
import csv
import math
import sys
from collections import defaultdict
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

CSV_PATH = "data/polls_2027_presidential_first_round.csv"
POLL_YEAR = 2026

FRENCH_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "decembre": 12,
}

# Fixed hue assignment: palette slot order is the CVD-safety mechanism, and
# color follows the candidate — do not reassign slots when polls reshuffle
# the ranking. (light hex, dark hex)
SERIES = {
    "RN":            ("Rassemblement national", "#2a78d6", "#3987e5"),
    "Philippe_HOR":  ("Philippe (HOR)",         "#1baf7a", "#199e70"),
    "Melenchon_LFI": ("Mélenchon (LFI)",        "#eda100", "#c98500"),
    "Attal_RE":      ("Attal (RE)",             "#008300", "#008300"),
    "Glucksmann_PP": ("Glucksmann (PP)",        "#4a3aa7", "#9085e9"),
    "Retailleau_LR": ("Retailleau (LR)",        "#e34948", "#e66767"),
    "Zemmour_REC":   ("Zemmour (REC)",          "#e87ba4", "#d55181"),
    "Tondelier_LE":  ("Tondelier (LE)",         "#eb6834", "#d95926"),
}

# Consistently minor candidates left off the chart (kept in the footnote so
# the reader knows they were tested).
EXCLUDED_NOTE = ("Non représentés (moyenne < 4%) : Villepin, Roussel, "
                 "Dupont-Aignan, Arthaud.")

THEMES = {
    "light": {
        "surface": "#fcfcfb", "page": "#f9f9f7", "ink": "#0b0b0b",
        "secondary": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "baseline": "#c3c2b7", "slot": 1,
    },
    "dark": {
        "surface": "#1a1a19", "page": "#0d0d0d", "ink": "#ffffff",
        "secondary": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "baseline": "#383835", "slot": 2,
    },
}


def parse_french_date(text, year=POLL_YEAR):
    """Return the midpoint date of a French field-period string.

    Handles "22 mars", "22-24 juin" and "30 avril-2 mai".
    """
    text = text.strip().lower().replace("–", "-").replace("—", "-")
    parts = [p.strip() for p in text.split("-")]

    def one(part, default_month=None):
        tokens = part.split()
        if len(tokens) == 2:
            return int(tokens[0]), FRENCH_MONTHS[tokens[1]]
        if len(tokens) == 1 and default_month is not None:
            return int(tokens[0]), default_month
        raise ValueError(f"unparseable date fragment: {part!r}")

    end_day, end_month = one(parts[-1])
    if len(parts) == 1:
        return date(year, end_month, end_day)
    start_day, start_month = one(parts[0], default_month=end_month)
    start = date(year, start_month, start_day)
    end = date(year, end_month, end_day)
    return start + (end - start) / 2


def load_polls(path):
    """Return (poll_means, raw_points).

    poll_means: {candidate: [(date, mean_over_scenarios)]}
    raw_points: {candidate: [(date, value)]} — one point per scenario.
    """
    by_poll = defaultdict(lambda: defaultdict(list))
    raw_points = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mid = parse_french_date(row["date"])
            key = (row["pollster"], mid, row["sample"])
            for cand in SERIES:
                cell = row.get(cand, "").strip()
                if cell:
                    v = float(cell)
                    by_poll[key][cand].append(v)
                    raw_points[cand].append((mid, v))

    poll_means = defaultdict(list)
    for (_, mid, _), cands in by_poll.items():
        for cand, vals in cands.items():
            poll_means[cand].append((mid, sum(vals) / len(vals)))
    for cand in poll_means:
        poll_means[cand].sort()
    return poll_means, raw_points


def gaussian_smooth(points, grid, sigma_days):
    """Gaussian-kernel weighted average of (date, value) points on grid."""
    out = []
    for t in grid:
        wsum = vsum = 0.0
        for d, v in points:
            w = math.exp(-0.5 * ((t - d).days / sigma_days) ** 2)
            wsum += w
            vsum += w * v
        out.append(vsum / wsum)
    return out


def spread_labels(items, min_gap):
    """Nudge label y-positions apart (bottom-up) so they don't collide.

    items: sorted list of [y, ...]; mutated in place.
    """
    for i in range(1, len(items)):
        if items[i][0] - items[i - 1][0] < min_gap:
            items[i][0] = items[i - 1][0] + min_gap


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sigma", type=float, default=15.0,
                    help="Gaussian kernel sigma in days (default: 15)")
    ap.add_argument("--dark", action="store_true", help="dark theme")
    ap.add_argument("-o", "--output", default=None,
                    help="output PNG path (default: polls_2027_first_round[_dark].png)")
    ap.add_argument("--csv", default=CSV_PATH, help="input CSV path")
    args = ap.parse_args()

    theme = THEMES["dark" if args.dark else "light"]
    out = args.output or (
        "polls_2027_first_round_dark.png" if args.dark
        else "polls_2027_first_round.png")

    poll_means, raw_points = load_polls(args.csv)
    if not poll_means:
        sys.exit("no polls parsed — check the CSV path/format")

    all_dates = [d for pts in poll_means.values() for d, _ in pts]
    start, end = min(all_dates), max(all_dates)
    grid = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    fig, ax = plt.subplots(figsize=(10.5, 6.3), dpi=160)
    fig.patch.set_facecolor(theme["page"])
    ax.set_facecolor(theme["surface"])

    ax.yaxis.grid(True, color=theme["grid"], linewidth=1.0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme["baseline"])
    ax.tick_params(colors=theme["muted"], labelsize=9, length=0)

    labels = []  # [y, name, value, color]
    for cand, (name, light_hex, dark_hex) in SERIES.items():
        color = dark_hex if args.dark else light_hex
        pts = poll_means.get(cand)
        if not pts:
            continue
        # raw per-scenario observations, faint, behind the trend
        xs, ys = zip(*raw_points[cand])
        ax.scatter(xs, ys, s=16, color=color, alpha=0.3,
                   edgecolors=theme["surface"], linewidths=0.6, zorder=2)
        smooth = gaussian_smooth(pts, grid, args.sigma)
        ax.plot(grid, smooth, color=color, linewidth=2,
                solid_capstyle="round", solid_joinstyle="round", zorder=3)
        # end marker with a surface ring so it survives line crossings
        ax.scatter([grid[-1]], [smooth[-1]], s=42, color=color, zorder=4,
                   edgecolors=theme["surface"], linewidths=2)
        labels.append([smooth[-1], name, smooth[-1], color])

    ymax = ax.get_ylim()[1]
    ax.set_ylim(0, max(ymax, 40))
    ax.set_yticks(range(0, int(ax.get_ylim()[1]) + 1, 10))
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")

    # direct end labels, nudged apart, with leader lines when displaced
    labels.sort(key=lambda r: r[0])
    spread_labels(labels, min_gap=ax.get_ylim()[1] * 0.045)
    x_text = grid[-1] + timedelta(days=3)
    for y, name, value, color in labels:
        if abs(y - value) > 0.2:
            ax.plot([grid[-1] + timedelta(days=1), x_text], [value, y],
                    color=theme["baseline"], linewidth=0.8,
                    clip_on=False, zorder=1)
        ax.annotate(f"{name}  {value:.0f}%", (x_text, y),
                    va="center", fontsize=9, color=theme["ink"],
                    annotation_clip=False)
        ax.scatter([x_text - timedelta(days=1.6)], [y], s=22, color=color,
                   clip_on=False, zorder=4)

    ax.set_xlim(start - timedelta(days=4), end + timedelta(days=2))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    ax.set_title("Présidentielle 2027 — intentions de vote, 1er tour",
                 color=theme["ink"], fontsize=14, fontweight="semibold",
                 loc="left", pad=26)
    ax.text(0, 1.045,
            f"Moyenne à noyau gaussien (σ = {args.sigma:.0f} jours) des "
            "sondages, scénarios moyennés par sondage · points = scénarios "
            "individuels",
            transform=ax.transAxes, fontsize=9, color=theme["secondary"])
    fig.text(0.06, 0.015,
             f"{EXCLUDED_NOTE}  Source : Wikipédia, « Liste de sondages sur "
             "l'élection présidentielle française de 2027 ».",
             fontsize=8, color=theme["muted"])

    fig.subplots_adjust(left=0.06, right=0.79, top=0.86, bottom=0.11)
    fig.savefig(out, facecolor=fig.get_facecolor())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
