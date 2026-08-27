# frelec

Polling data for the 2027 French presidential election, scraped from
[French Wikipedia](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027)
into `polls_2027_presidential_first_round.csv` (first round) and
`polls_2027_second_round.csv` (runoff match-ups), plus trend
visualizations for each. See "The dataset" below for conventions.

## How to run

### Visualization

Requires [uv](https://docs.astral.sh/uv/) (dependencies: matplotlib, declared
in `pyproject.toml`):

```
# First round: overall trend, recent-period trend, and per-pollster comparison
uv run python visualize_polls.py            # france-first_round[_recent|_pollsters].png
uv run python visualize_polls.py --sigma 10 -o custom.png
uv run python visualize_polls.py --recent-days 30

# Second round: runoff trend by challenger, and latest-poll-per-matchup snapshot
uv run python visualize_second_round.py            # france-second_round_trend.png, …_snapshot.png
```

Both scripts still take `--dark`, but nothing uses its output any more: the
poll site renders each chart inside its own themed viewer page rather than
serving a separately generated dark PNG, so as of 2026-07-29 the five
`…_dark.png` files are gone from this repo and from the server, and the daily
update no longer regenerates them. `--dark` is kept for one-off local use; if
you run it, do not commit or deploy the result.

First-round scenarios are averaged within each poll, then each candidate's
series is smoothed with a Gaussian kernel over time (`--sigma` days, default
15). Faint dots show raw per-scenario values. The pollster-comparison chart
shows each institute's latest poll, ordered by poll date, plus a
smoothed-average row. The
second-round trend chart plots each challenger's own share against the RN
candidate (Bardella or Le Pen) over time; the snapshot chart shows the most
recent poll for each hypothetical match-up **against Le Pen**. Bardella's
match-ups are left out of the snapshot — he stopped being the RN candidate
when Le Pen declared on 2026-07-07, and the snapshot is a picture of the race
as it stands. They stay in the CSV and on the trend chart, where each point
is read against whoever the RN candidate was at the time. The set is
`SNAPSHOT_RN_CANDIDATES` in `visualize_second_round.py`.

### Parser (stdlib only, no uv needed)

Fetch the raw wikitext and regenerate the CSVs:

```
curl -s "https://fr.wikipedia.org/w/index.php?title=Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027&action=raw" -o /tmp/frelec_raw.wiki
python3 parse_polls.py /tmp/frelec_raw.wiki polls_2027_presidential_first_round.csv
python3 parse_polls.py /tmp/frelec_raw.wiki polls_2027_second_round.csv --second-round
```

## The dataset

### `polls_2027_presidential_first_round.csv`

First-round voting-intention polls, January–August 2026, scraped from the French
Wikipedia article
["Liste de sondages sur l'élection présidentielle française de 2027"](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027)
(pulled 2026-08-27).

Starting with the 7–8 July 2026 polls (Wikipedia's "Second semestre 2026"
sub-table), the table switched the RN column from a hypothetical "candidate"
placeholder to Marine Le Pen by name and dropped the Dominique de Villepin
column — Le Pen officially declared her candidacy on 2026-07-07, her period of
ineligibility having been reduced on appeal. Both tables' columns are read
from their own headers, so the RN series continues unbroken across the
rename, and the `Villepin_LFH` column is simply blank in the rows where the
sub-table has no Villepin column.

Pollsters kept testing Villepin after he lost his column, and Wikipedia
reports him inside the "Autre" cell with a small note naming him. The parser
routes those values back into `Villepin_LFH` rather than leaving them in
`Autre`, so his series doesn't break in two on 7 July. An "Autre" value whose
note names somebody who never had a column of their own — Ruffin, in the
9–10 July Elabe scenarios — stays in `Autre`, with the name kept in `notes`.

Each poll is published with several "scenarios" (different hypothetical candidate
line-ups, e.g. Attal vs. Philippe running, or Le Pen vs. Bardella as the RN
candidate) — one CSV row per scenario, grouped by `pollster`/`date`/`sample`.
Values are vote-share percentages; blank means that candidate wasn't tested in
that scenario. The `notes` column records scenario-specific substitutions
(e.g. Hollande or Faure standing in for the PS line, Ruffin, Knafo, Darmanin,
Lecornu, etc.). A share Wikipedia reports only as an upper bound (e.g. `<1`)
is encoded as the midpoint of that bound (`0.5`), with the original reading
kept in `notes`.

Latest poll: Ifop (n=1598, 24–25 August) — RN (Le Pen) 33–35%, Mélenchon
16–19%, Philippe 14.5–21%, Glucksmann 11–18%, Attal 8–15%, Retailleau 6–12%
(the scenarios standing Hollande in for Glucksmann and Le Maire in for Attal
are left out of those two ranges).

Caveat (per Wikipedia, citing Le Monde): polls taken a year-plus before a French
presidential election have historically been poor predictors — in 2022 LFI
polled ~9% a year out and scored 22%; RN polled ~29% and scored 23%.

Older first-round polls (2023–2025) are on the same Wikipedia page but weren't
included in this CSV — ask if you want those pulled too.

### `polls_2027_second_round.csv`

Second-round (runoff) hypothetical match-up polls, January 2024 – August 2026,
scraped from the same Wikipedia page's "Sondages concernant le second tour"
section (pulled 2026-08-27). Each subsection there ("Hypothèse X – Y") polls
one specific pairing — Attal, Mélenchon, Philippe, Glucksmann and Retailleau
each against the RN candidate (Bardella through early 2026, Le Pen from her
2026-07-07 candidacy onward), plus a single early Ruffin–Le Pen poll and, from
Ifop's 24–25 August 2026 poll, a first Hollande–Le Pen match-up.

One CSV row per poll: `matchup` (`candidate_a-candidate_b`, e.g.
`Attal_RE-Bardella_RN`), `candidate_a`/`candidate_b` (the two contenders,
`candidate_a` is always the non-RN challenger), `pollster`, `date`, `sample`,
and `pct_a`/`pct_b` (the two runoff vote shares, which sum to 100).

Two events reshape these match-ups and are worth keeping in mind when reading
the trend: Marine Le Pen's five-year ineligibility sentence with provisional
execution (2025-03-31, on appeal at the time) and her declared candidacy
following that appeal (2026-07-07) — the RN candidate in these polls is
Bardella throughout that window and Le Pen herself before and after it.
