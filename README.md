# frelec

Polling data for the 2027 French presidential election (first round), scraped
from [French Wikipedia](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027)
into `data/polls_2027_presidential_first_round.csv`, plus a trend
visualization. See `data/README.md` for the dataset conventions.

## How to run

### Visualization

Requires [uv](https://docs.astral.sh/uv/) (dependencies: matplotlib, declared
in `pyproject.toml`):

```
uv run python visualize_polls.py            # light theme → polls_2027_first_round.png
uv run python visualize_polls.py --dark     # dark theme → polls_2027_first_round_dark.png
uv run python visualize_polls.py --sigma 10 -o custom.png
```

Scenarios are averaged within each poll, then each candidate's series is
smoothed with a Gaussian kernel over time (`--sigma` days, default 15). Faint
dots show raw per-scenario values.

### Parser (stdlib only, no uv needed)

Fetch the raw wikitext and regenerate the CSV:

```
curl -s "https://fr.wikipedia.org/w/index.php?title=Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027&action=raw" -o /tmp/frelec_raw.wiki
python3 parse_polls.py /tmp/frelec_raw.wiki data/polls_2027_presidential_first_round.csv
```
