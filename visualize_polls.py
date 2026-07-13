#!/usr/bin/env python3
"""Plot smoothed polling trends for the 2027 French presidential first round.

Reads polls_2027_presidential_first_round.csv (one row per poll
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

CSV_PATH = "polls_2027_presidential_first_round.csv"
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


def load_poll_records(path):
    """Return one record per poll (scenarios averaged together):
    [{'pollster', 'date', 'sample', <candidate>: mean_over_scenarios, ...}],
    sorted by date.
    """
    by_poll = defaultdict(lambda: defaultdict(list))
    meta = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mid = parse_french_date(row["date"])
            key = (row["pollster"], mid, row["sample"])
            meta[key] = (row["pollster"], mid, row["sample"])
            for cand in SERIES:
                cell = row.get(cand, "").strip()
                if cell:
                    by_poll[key][cand].append(float(cell))

    records = []
    for key, cands in by_poll.items():
        pollster, mid, sample = meta[key]
        rec = {"pollster": pollster, "date": mid, "sample": sample}
        for cand, vals in cands.items():
            rec[cand] = sum(vals) / len(vals)
        records.append(rec)
    records.sort(key=lambda r: r["date"])
    return records


def load_polls(path):
    """Return (poll_means, raw_points).

    poll_means: {candidate: [(date, mean_over_scenarios)]}
    raw_points: {candidate: [(date, value)]} — one point per scenario.
    """
    records = load_poll_records(path)
    raw_points = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mid = parse_french_date(row["date"])
            for cand in SERIES:
                cell = row.get(cand, "").strip()
                if cell:
                    raw_points[cand].append((mid, float(cell)))

    poll_means = defaultdict(list)
    for rec in records:
        for cand in SERIES:
            if cand in rec:
                poll_means[cand].append((rec["date"], rec[cand]))
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


def plot_trend(poll_means, raw_points, theme, dark, sigma, out, title, subtitle):
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
        color = dark_hex if dark else light_hex
        pts = poll_means.get(cand)
        if not pts:
            continue
        # raw per-scenario observations, faint, behind the trend
        xs, ys = zip(*raw_points[cand])
        ax.scatter(xs, ys, s=16, color=color, alpha=0.3,
                   edgecolors=theme["surface"], linewidths=0.6, zorder=2)
        smooth = gaussian_smooth(pts, grid, sigma)
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

    ax.set_title(title, color=theme["ink"], fontsize=14, fontweight="semibold",
                 loc="left", pad=26)
    ax.text(0, 1.045, subtitle, transform=ax.transAxes, fontsize=9,
            color=theme["secondary"])
    fig.text(0.06, 0.015,
             f"{EXCLUDED_NOTE}  Source : Wikipédia, « Liste de sondages sur "
             "l'élection présidentielle française de 2027 ».",
             fontsize=8, color=theme["muted"])

    fig.subplots_adjust(left=0.06, right=0.79, top=0.86, bottom=0.11)
    fig.savefig(out, facecolor=fig.get_facecolor())
    print(f"wrote {out}")


def dodge(values, gap=1.2, step=0.16):
    """Vertical offsets that spread out dots whose x-values nearly coincide."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    offsets = [0.0] * len(values)
    cluster = [order[0]]
    for i in order[1:] + [None]:
        if i is not None and values[i] - values[cluster[-1]] < gap:
            cluster.append(i)
            continue
        for k, idx in enumerate(cluster):
            offsets[idx] = (k - (len(cluster) - 1) / 2) * step
        cluster = [i] if i is not None else []
    return offsets


def plot_pollsters(records, theme, dark, sigma, out):
    """One row per pollster (their latest poll), plus a smoothed-average row."""
    latest = {}
    for rec in records:
        latest[rec["pollster"]] = rec  # records sorted ascending by date

    end_date = max(rec["date"] for rec in records)
    poll_means = defaultdict(list)
    for rec in records:
        for cand in SERIES:
            if cand in rec:
                poll_means[cand].append((rec["date"], rec[cand]))
    avg = {
        cand: gaussian_smooth(sorted(pts), [end_date], sigma)[0]
        for cand, pts in poll_means.items()
    }

    rows = sorted(latest.items(), key=lambda kv: kv[1].get("RN", 0))
    rows = [(f"{pollster}  ({rec['date']:%d %b})", rec) for pollster, rec in rows]
    rows.append((f"Moyenne lissée (σ={sigma:.0f} j)", avg))

    fig, ax = plt.subplots(figsize=(10.5, 0.62 * len(rows) + 2.2), dpi=160)
    fig.patch.set_facecolor(theme["page"])
    ax.set_facecolor(theme["surface"])

    xmax = 0.0
    for y, (label, values) in enumerate(rows):
        present = [c for c in SERIES if c in values and values[c] is not None]
        vals = [values[c] for c in present]
        offsets = dodge(vals)
        for cand, v, dy in zip(present, vals, offsets):
            _, light_hex, dark_hex = SERIES[cand]
            color = dark_hex if dark else light_hex
            ax.scatter(v, y + dy, s=80, color=color, zorder=3,
                       edgecolor=theme["surface"], linewidth=1.4)
        xmax = max(xmax, max(vals))

    ax.axhline(len(rows) - 1.5, color=theme["baseline"], linewidth=0.8)

    handles = [
        plt.Line2D([], [], marker="o", linestyle="", markersize=8,
                   markerfacecolor=(dark_hex if dark else light_hex),
                   markeredgecolor=theme["surface"], label=name)
        for name, light_hex, dark_hex in SERIES.values()
    ]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              ncol=4, frameon=False, fontsize=8.5, labelcolor=theme["ink"],
              handletextpad=0.2, columnspacing=0.9, borderaxespad=0.2)

    ax.set_xlim(0, xmax + 3)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_yticks(range(len(rows)), [label for label, _ in rows], fontsize=9.5)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.xaxis.grid(True, color=theme["grid"], linewidth=1.0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme["baseline"])
    ax.tick_params(colors=theme["muted"], length=0)
    for tick in ax.get_yticklabels():
        tick.set_color(theme["ink"])
    ax.get_yticklabels()[-1].set_fontweight("bold")

    fig.text(0.03, 0.965, "Présidentielle 2027 — 1er tour, sondages par institut",
              fontsize=14, color=theme["ink"], fontweight="semibold", va="top")
    fig.text(0.03, 0.925,
              f"Dernier sondage de chaque institut, au {end_date:%d %b %Y} · "
              "trié par score RN · scénarios moyennés par sondage",
              fontsize=9, color=theme["secondary"], va="top")
    fig.text(0.99, 0.015,
              "Source : Wikipédia, « Liste de sondages sur l'élection "
              "présidentielle française de 2027 ».",
              ha="right", fontsize=8, color=theme["muted"])

    fig.subplots_adjust(left=0.19, right=0.97, top=0.83, bottom=0.06)
    fig.savefig(out, facecolor=fig.get_facecolor())
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sigma", type=float, default=15.0,
                    help="Gaussian kernel sigma in days (default: 15)")
    ap.add_argument("--dark", action="store_true", help="dark theme")
    ap.add_argument("-o", "--output", default=None,
                    help="output PNG path (default: france-first_round[_dark].png)")
    ap.add_argument("--out-recent", default=None,
                    help="output PNG path for the recent-period chart")
    ap.add_argument("--out-pollsters", default=None,
                    help="output PNG path for the pollster-comparison chart")
    ap.add_argument("--recent-days", type=int, default=60,
                    help="window size in days for the recent-period chart (default: 60)")
    ap.add_argument("--csv", default=CSV_PATH, help="input CSV path")
    args = ap.parse_args()

    theme = THEMES["dark" if args.dark else "light"]
    suffix = "_dark" if args.dark else ""
    out = args.output or f"france-first_round{suffix}.png"
    out_recent = args.out_recent or f"france-first_round_recent{suffix}.png"
    out_pollsters = args.out_pollsters or f"france-first_round_pollsters{suffix}.png"

    poll_means, raw_points = load_polls(args.csv)
    if not poll_means:
        sys.exit("no polls parsed — check the CSV path/format")

    subtitle = (
        f"Moyenne à noyau gaussien (σ = {args.sigma:.0f} jours) des "
        "sondages, scénarios moyennés par sondage · points = scénarios "
        "individuels")
    plot_trend(poll_means, raw_points, theme, args.dark, args.sigma, out,
               "Présidentielle 2027 — intentions de vote, 1er tour", subtitle)

    end_date = max(d for pts in poll_means.values() for d, _ in pts)
    cutoff = end_date - timedelta(days=args.recent_days)
    recent_means = {
        cand: [(d, v) for d, v in pts if d >= cutoff]
        for cand, pts in poll_means.items()
    }
    recent_raw = {
        cand: [(d, v) for d, v in pts if d >= cutoff]
        for cand, pts in raw_points.items()
    }
    recent_means = {c: p for c, p in recent_means.items() if p}
    recent_subtitle = (
        f"{args.recent_days} derniers jours · moyenne à noyau gaussien "
        f"(σ = {args.sigma:.0f} jours) · points = scénarios individuels")
    plot_trend(recent_means, recent_raw, theme, args.dark, args.sigma, out_recent,
               "Présidentielle 2027 — 1er tour, tendance récente", recent_subtitle)

    records = load_poll_records(args.csv)
    plot_pollsters(records, theme, args.dark, args.sigma, out_pollsters)


if __name__ == "__main__":
    main()
