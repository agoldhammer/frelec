# frelec

Polling data for the 2027 French presidential election, scraped from
[French Wikipedia](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027)
into `data/polls_2027_presidential_first_round.csv` (first round) and
`data/polls_2027_second_round.csv` (runoff match-ups), plus trend
visualizations for each. See `data/README.md` for the dataset conventions.

## How to run

### Visualization

Requires [uv](https://docs.astral.sh/uv/) (dependencies: matplotlib, declared
in `pyproject.toml`):

```
# First round: overall trend, recent-period trend, and per-pollster comparison
uv run python visualize_polls.py            # light theme → france-first_round[_recent|_pollsters].png
uv run python visualize_polls.py --dark     # dark theme  → …_dark.png
uv run python visualize_polls.py --sigma 10 -o custom.png
uv run python visualize_polls.py --recent-days 30

# Second round: runoff trend by challenger, and latest-poll-per-matchup snapshot
uv run python visualize_second_round.py            # light theme → france-second_round_trend.png, …_snapshot.png
uv run python visualize_second_round.py --dark      # dark theme  → …_dark.png
```

First-round scenarios are averaged within each poll, then each candidate's
series is smoothed with a Gaussian kernel over time (`--sigma` days, default
15). Faint dots show raw per-scenario values. The pollster-comparison chart
shows each institute's latest poll plus a smoothed-average row. The
second-round trend chart plots each challenger's own share against the RN
candidate (Bardella or Le Pen) over time; the snapshot chart shows the most
recent poll for each hypothetical match-up.

### Parser (stdlib only, no uv needed)

Fetch the raw wikitext and regenerate the CSVs:

```
curl -s "https://fr.wikipedia.org/w/index.php?title=Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027&action=raw" -o /tmp/frelec_raw.wiki
python3 parse_polls.py /tmp/frelec_raw.wiki data/polls_2027_presidential_first_round.csv
python3 parse_polls.py /tmp/frelec_raw.wiki data/polls_2027_second_round.csv --second-round
```
