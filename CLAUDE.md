# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A small scraper/parser that turns French Wikipedia's wikitext poll tables for
the 2027 French presidential election into clean CSV, plus matplotlib
visualizations. There is no build system, package manifest for the parser, or
test suite — just `parse_polls.py` (stdlib only: `re`, `csv`, `sys`,
`unicodedata`) and the CSVs it writes in the repo root. `visualize_polls.py`
and `visualize_second_round.py` (uv/matplotlib) render the CSVs to PNG.

Source page: [Liste de sondages sur l'élection présidentielle française de 2027](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027).

## Commands

Fetch raw wikitext for a section of the source page (see `.claude/settings.local.json`
for the pre-approved curl invocation pattern):

```
curl -s "https://fr.wikipedia.org/w/index.php?title=Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027&action=raw" -o /tmp/frelec_raw.wiki
```

Parse a wikitext file (or extracted section) into CSV:

```
python3 parse_polls.py <input.wiki> <output.csv>                  # first round
python3 parse_polls.py <input.wiki> <output.csv> --second-round   # second round (runoff)
```

There is no test suite; verify changes by re-running the parser against a
known wiki excerpt and diffing the resulting CSV against
`polls_2027_presidential_first_round.csv` or `polls_2027_second_round.csv`.

## Architecture: `parse_polls.py`

The input is a MediaWiki wikitable. Rows are delimited by `|-` markers, and a
single logical poll spans multiple wikitable rows because pollsters publish
several "scenarios" (different hypothetical candidate line-ups) per poll,
implemented via `rowspan` on the pollster/date/sample cells. The parser has to
reconstruct that grouping itself — there's no 1:1 mapping between wiki rows
and output rows:

- `parse_rows` splits the wikitext on `|-` into row blocks, skips header rows
  (`!`) and full-width event-annotation rows (`is_event_row`), then tracks a
  `remaining` counter driven by the pollster cell's `rowspan` attribute to
  know how many subsequent wiki rows belong to the current pollster/date/sample
  group (each becomes one `scenario` row in the output).
- `strip_attrs` removes the leading wikitable cell attribute segment
  (`rowspan=.. style=.. |`) while respecting `{{ }}` / `[[ ]]` nesting, since
  attribute segments can themselves contain template/link syntax.
- `clean_text` strips MediaWiki markup (`{{blanc|}}`, `'''bold'''`,
  `{{formatnum:}}`, `[[links]]`, external links, `{{note|}}`) down to plain text.
  Add new markup patterns here if Wikipedia's formatting changes.
- `parse_value_cell` turns a cleaned cell into `(value, note, colspan)`: a
  `<br>` inside a cell splits the main vote-share number from a small-text
  note (e.g. a candidate substitution like "Bardella / Le Pen"); dashes/empty
  become `None`; `colspan` causes the same `None` to be back-filled across the
  candidates a merged cell spans.
- `CANDIDATES` is the fixed, ordered list of output columns and must match the
  column order of the wikitable being parsed — if Wikipedia reorders or
  adds/removes candidate columns, update this list to match before re-parsing.

The `== Sondages concernant le second tour ==` section is a different shape —
one small standalone wikitable per `=== Hypothèse X – Y ===` heading (a
runoff match-up), no rowspan grouping. `parse_second_round_rows` (invoked via
`--second-round`) handles this: `HYPOTHESIS_RE` splits the section into
per-match-up tables, `HEADER_NAME_RE` pulls each contender's name and party
out of the table's column-header cells, and `slugify` turns those into the
same `Name_PARTY` key style as `CANDIDATES` (accent-stripped, ASCII-only) so
challengers who also appear in the first-round table share a key (e.g.
`Attal_RE`). Event/annotation rows in these tables (Le Pen's legal-status
changes) are single-line rows carrying a bare `colspan` attribute, detected
by `is_second_round_event_row` — a different heuristic from `is_event_row`
because the runoff tables are narrower and don't use the 13–19 colspan range.

## Visualizations

`visualize_polls.py` reads `polls_2027_presidential_first_round.csv` and
renders three PNGs: the overall trend (Gaussian-smoothed per candidate), a
recent-period zoom (`--recent-days`), and a per-pollster comparison (latest
poll per institute + a smoothed-average row). `visualize_second_round.py`
reads `polls_2027_second_round.csv` and renders a trend chart (each
challenger's share against whichever RN candidate they were polled against)
and a snapshot chart (most recent poll per match-up, as a stacked bar split
at the 50% majority line). Both scripts share the `SERIES` color/label map
and `THEMES` (light/dark) from `visualize_polls.py`, so a candidate's color
is consistent across every chart in the repo — reuse those rather than
hand-rolling new colors for a candidate who already appears elsewhere. Any
genuinely new color (e.g. Ruffin, who only appears in runoff polls) must be
checked with the dataviz skill's `scripts/validate_palette.js` against the
existing set before use.

## Data conventions

Both CSVs live in the repo root. See README.md's "The dataset" section for
the full description of the current dataset. Key points to preserve when
regenerating or extending it:

- One CSV row per scenario (not per poll); rows in the same poll share
  `pollster`/`date`/`sample` and are distinguished by `scenario` (1-indexed).
- Candidate columns are vote-share percentages; blank = not tested in that
  scenario.
- `notes` records scenario-specific candidate substitutions (e.g. a different
  RN or PS standard-bearer) as `Candidate=value (note)`, semicolon-separated.
