# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A small scraper/parser that turns French Wikipedia's wikitext poll tables for
the 2027 French presidential election into clean CSV. There is no build
system, package manifest, or test suite — just `parse_polls.py` (stdlib only:
`re`, `csv`, `sys`) and the `data/` output.

Source page: [Liste de sondages sur l'élection présidentielle française de 2027](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027).

## Commands

Fetch raw wikitext for a section of the source page (see `.claude/settings.local.json`
for the pre-approved curl invocation pattern):

```
curl -s "https://fr.wikipedia.org/w/index.php?title=Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027&action=raw" -o /tmp/frelec_raw.wiki
```

Parse a wikitext file (or extracted section) into CSV:

```
python3 parse_polls.py <input.wiki> <output.csv>
```

There is no test suite; verify changes by re-running the parser against a
known wiki excerpt and diffing the resulting CSV against `data/polls_2027_presidential_first_round.csv`.

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

## Data conventions (`data/`)

See `data/README.md` for the full description of the current dataset. Key
points to preserve when regenerating or extending it:

- One CSV row per scenario (not per poll); rows in the same poll share
  `pollster`/`date`/`sample` and are distinguished by `scenario` (1-indexed).
- Candidate columns are vote-share percentages; blank = not tested in that
  scenario.
- `notes` records scenario-specific candidate substitutions (e.g. a different
  RN or PS standard-bearer) as `Candidate=value (note)`, semicolon-separated.
