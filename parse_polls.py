import re, csv, sys, unicodedata

# Canonical CSV column order, and the registry of candidates we already know
# about. This is NOT a positional map onto any one wikitable: each sub-table's
# real column list is read from its own header row (see `table_columns`),
# because Wikipedia splits a year into dated sub-tables with different columns
# whenever a candidate enters or leaves the race. CANDIDATES only decides what
# order the columns come out in, and lets an "Autre" cell that names a dropped
# candidate find the column that candidate used to have.
CANDIDATES = ['Arthaud_LO','Melenchon_LFI','Roussel_PCF','Tondelier_LE','Glucksmann_PP',
              'Attal_RE','Philippe_HOR','Villepin_LFH','Retailleau_LR','DupontAignan_DLF',
              'RN','Zemmour_REC','Autre']

# Leading columns of a first-round table that describe the poll, not a
# candidate. Compared slugified, so accents and markup don't matter.
META_HEADERS = {'Sondeur', 'Date', 'Echantillon'}

# The RN column is a party slot rather than a person: Wikipedia wrote it as a
# "Candidat RN" placeholder until Le Pen declared on 2026-07-07, and as
# [[Marine Le Pen|Le Pen]] (RN) from the following table onward. Both are the
# same series -- the CSV column and visualize_polls.py's SERIES both call it
# RN -- so the named forms collapse onto it. The second-round tables
# deliberately keep LePen_RN and Bardella_RN apart: there, which RN candidate
# was polled is the whole point of the match-up.
FIRST_ROUND_ALIASES = {'LePen_RN': 'RN', 'Bardella_RN': 'RN'}

# The catch-all column. A note inside it names who the "other" candidate was;
# a note inside a candidate's own column names a substitute for that
# candidate. Only the former is re-routed (see `route_other`).
OTHER_COLUMN = 'Autre'

def get_attr_int(s, name):
    m = re.search(rf'{name}\s*=\s*"?(\d+)"?', s)
    return int(m.group(1)) if m else None

def strip_attrs(s):
    """Strip a single leading wikitable cell attribute segment (rowspan=.. style=.. |)
    respecting {{ }} / [[ ]] nesting, returning the remaining cell content."""
    s = s.strip()
    depth = 0
    i = 0
    while i < len(s):
        if s[i:i+2] in ('{{', '[['):
            depth += 1
            i += 2
            continue
        if s[i:i+2] in ('}}', ']]'):
            depth -= 1
            i += 2
            continue
        if s[i] == '|' and depth == 0:
            return s[i+1:].strip()
        i += 1
    return s

def strip_refs(s):
    """Drop <ref>…</ref> footnote markers. Header cells carry them between the
    candidate's name and their party ("SaufPrécision" and friends), which
    would otherwise break the name/party pattern."""
    s = re.sub(r'<ref[^>]*/>', '', s)
    s = re.sub(r'<ref[^>]*>.*?</ref>', '', s, flags=re.DOTALL)
    return s

def clean_text(s):
    s = re.sub(r'\{\{blanc\|([^}]*)\}\}', r'\1', s)
    s = re.sub(r"'''(.*?)'''", r'\1', s)
    s = re.sub(r'\{\{formatnum[:|]([^}]*)\}\}', r'\1', s, flags=re.IGNORECASE)
    s = re.sub(r'\[\[[^|\]]*\|([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\[\[([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\[https?://\S+\s+([^\]]+)\]', r'\1', s)
    s = re.sub(r'\[https?://\S+\]', '', s)
    s = re.sub(r'\{\{note\|[^}]*\}\}', '', s)
    s = re.sub(r'\{\{1er\}\}', '1er', s, flags=re.IGNORECASE)
    return s.strip()

def parse_value_cell(raw):
    content = strip_attrs(raw)
    content = clean_text(content)
    colspan = get_attr_int(raw, 'colspan') or 1
    note = None
    if '<br' in content:
        parts = re.split(r'<br\s*/?>', content, maxsplit=1)
        main = parts[0].strip()
        note = re.sub(r'</?small>', '', parts[1]).strip() if len(parts) > 1 else None
    else:
        main = re.sub(r'</?small>', '', content).strip()
    main = main.strip()
    if main in ('—', '-', '', '–'):
        val = None
    else:
        val = main.replace(',', '.').replace(' ', '')
        # Wikipedia occasionally reports a share as an upper bound ("<1").
        # Encode it as the midpoint of [0, bound) and keep the original
        # reading in the notes column.
        m = re.fullmatch(r'<(\d+(?:\.\d+)?)', val)
        if m:
            val = str(float(m.group(1)) / 2)
            note = f"reported as {main}" if note is None else f"{note}; reported as {main}"
    return val, note, colspan

def slugify(text):
    """ASCII-only identifier fragment: strip accents, drop non-alnum."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Za-z0-9]', '', text)

# A candidate's header cell, once refs are stripped:
#   [[Jean-Luc Mélenchon|Mélenchon]]<br><small>([[La France insoumise|LFI]])</small>
HEADER_NAME_RE = re.compile(
    r'\[\[[^|\]]+\|([^\]]+)\]\]\s*<br\s*/?>\s*<small>\(\s*\[\[[^|\]]+\|([^\]]+)\]\]'
)
# A party slot with nobody named in it yet:
#   Candidat<br>[[Rassemblement national|RN]]
HEADER_PLACEHOLDER_RE = re.compile(
    r'Candidat\s*<br\s*/?>\s*\[\[[^|\]]+\|([^\]]+)\]\]'
)

def header_key(cell):
    """Turn one header cell into its column key: Name_PARTY for a named
    candidate, PARTY alone for an un-named party slot, and the cleaned text
    itself (e.g. "Autre") for anything else."""
    cell = strip_refs(cell)
    m = HEADER_NAME_RE.search(cell)
    if m:
        key = f"{slugify(m.group(1))}_{slugify(m.group(2))}"
        return FIRST_ROUND_ALIASES.get(key, key)
    m = HEADER_PLACEHOLDER_RE.search(cell)
    if m:
        key = slugify(m.group(1))
        return FIRST_ROUND_ALIASES.get(key, key)
    return slugify(clean_text(strip_attrs(cell)))

def split_blocks(text):
    """Split a wikitable into its |- delimited row blocks, as lists of cell
    lines with the table's own {| / |} markers dropped."""
    blocks = []
    for block in re.split(r'(?m)^\|-[^\n]*\n?', text):
        lines = [l for l in block.split('\n') if l.strip() and l.strip() != '|}']
        lines = [l for l in lines if not l.lstrip().startswith('{|')]
        if lines:
            blocks.append(lines)
    return blocks

def table_columns(blocks):
    """Read a first-round wikitable's candidate columns off its own header.

    The header is two stacked rows -- portraits above, names and parties below
    -- plus cells like "Autre" that rowspan across both, so the columns can't
    be read off either row alone. Reconstruct the little header grid honouring
    rowspan/colspan and take, for each column, the deepest header cell that
    covers it: that is the name row where there is one, and the spanning cell
    otherwise. Returns (candidate_keys, number_of_leading poll-metadata columns).
    """
    rows = []
    for lines in blocks:
        if not any(l.lstrip().startswith('!') for l in lines):
            break  # first non-header block ends the header
        rows.append([l.lstrip()[1:] for l in lines if l.lstrip().startswith('!')])
    if not rows:
        return None, 0

    grid = {}
    width = 0
    for r, cells in enumerate(rows):
        c = 0
        for cell in cells:
            while (r, c) in grid:
                c += 1
            for dr in range(get_attr_int(cell, 'rowspan') or 1):
                for dc in range(get_attr_int(cell, 'colspan') or 1):
                    grid[(r + dr, c + dc)] = cell
            c += get_attr_int(cell, 'colspan') or 1
            width = max(width, c)

    keys = []
    for c in range(width):
        cell = next((grid[(r, c)] for r in reversed(range(len(rows))) if (r, c) in grid), None)
        key = header_key(cell) if cell is not None else ''
        # One header cell can colspan several data columns (a party bloc
        # polled under two line-ups, say). They are separate columns, so give
        # the repeats distinct keys rather than letting the last one silently
        # overwrite the rest of the row.
        if key in keys:
            key = f"{key}_{sum(k.split('_')[0] == key.split('_')[0] for k in keys) + 1}"
        keys.append(key)

    n_meta = 0
    while n_meta < len(keys) and keys[n_meta] in META_HEADERS:
        n_meta += 1
    return keys[n_meta:], n_meta

def is_event_row(lines, n_candidates):
    """A full-width annotation row (a candidate declaring, say) rather than a
    poll. Wikipedia is loose with the colspan on these -- they have been seen
    both matching the table width and overshooting it -- so anything spanning
    at least the candidate columns counts, which no data cell ever does."""
    if len(lines) != 1:
        return False
    if 'bgcolor' in lines[0]:
        return True
    colspan = get_attr_int(lines[0], 'colspan')
    return colspan is not None and colspan >= n_candidates

def route_other(note, columns, known):
    """Decide where an "Autre" value really belongs.

    When a candidate loses their own column but pollsters keep testing them,
    Wikipedia folds them into "Autre" and names them in a <br><small> note.
    That value belongs in the column that candidate had while they had one,
    not in the catch-all -- otherwise the series breaks in two at the date the
    column was dropped. Returns (target_column, remaining_note), and leaves
    the value in "Autre" when the note names somebody with no column of their
    own (Ruffin, Hollande) or is not a name at all ("reported as <1").
    """
    segments = [s.strip() for s in note.split(';') if s.strip()]
    for i, segment in enumerate(segments):
        # "Hollande (PS)" -> "Hollande"
        surname = slugify(re.sub(r'\(.*?\)', '', segment))
        target = known.get(surname)
        if target and target != OTHER_COLUMN and target not in columns:
            rest = '; '.join(segments[:i] + segments[i + 1:])
            return target, (rest or None)
    return OTHER_COLUMN, note

def known_candidate_columns(*column_lists):
    """Surname -> column key, over every candidate column we know of. Used to
    give an "Autre" note somewhere to go."""
    known = {}
    for columns in column_lists:
        for key in columns:
            if key == OTHER_COLUMN:
                continue
            known.setdefault(key.split('_')[0], key)
    return known

def parse_rows(text):
    """Parse every first-round wikitable in `text`. Returns (rows, columns),
    where `columns` is the CSV column order: CANDIDATES first, then any
    candidate the tables introduced that CANDIDATES has never seen."""
    tables = re.findall(r'(?m)^\{\|.*?^\|\}', text, re.DOTALL) or [text]
    parsed = [(blocks, *table_columns(blocks))
              for blocks in (split_blocks(t) for t in tables)]

    seen = [c for _, columns, _ in parsed if columns for c in columns]
    known = known_candidate_columns(CANDIDATES, seen)
    out_columns = CANDIDATES + [c for c in dict.fromkeys(seen) if c not in CANDIDATES]
    report_column_changes(parsed, seen)

    polls = []
    for blocks, columns, n_meta in parsed:
        if not columns:
            # No header of our shape: fall back to the canonical column list,
            # which is what the parser did for every table before it learned
            # to read headers.
            columns, n_meta = CANDIDATES, 3
        polls.extend(parse_table(blocks, columns, n_meta, known))
    return polls, out_columns

def report_column_changes(parsed, seen):
    """Say on stderr when a table's column set is not the canonical one. A
    candidate entering or leaving is exactly the event that used to make a
    re-parse silently disagree with the committed CSV, so it should be
    audible even though the parse itself now handles it."""
    for i, (_, columns, _) in enumerate(parsed, start=1):
        if columns is None:
            print(f"table {i}: no header row recognised, "
                  f"falling back to the canonical CANDIDATES order", file=sys.stderr)
            continue
        added = [c for c in columns if c not in CANDIDATES]
        dropped = [c for c in CANDIDATES if c not in columns]
        if added:
            print(f"table {i}: new candidate column(s) {', '.join(added)} "
                  f"-- add them to CANDIDATES to fix their place in the CSV",
                  file=sys.stderr)
        if dropped:
            print(f"table {i}: no column for {', '.join(dropped)}", file=sys.stderr)

def parse_table(blocks, columns, n_meta, known):
    polls = []
    pollster = date = sample = None
    remaining = 0
    scenario_idx = 0

    for lines in blocks:
        if any(l.lstrip().startswith('!') for l in lines):
            continue  # header row
        if is_event_row(lines, len(columns)):
            continue  # full-width event annotation row
        cells = [l[1:] if l.startswith('|') else l for l in lines]

        if remaining == 0:
            # legend/style row: every cell strips to empty content
            if all(strip_attrs(c) == '' for c in cells):
                continue
            meta = [clean_text(strip_attrs(c)) for c in cells[:n_meta]]
            pollster, date, sample = (meta + [None] * 3)[:3]
            sample = (sample or '').replace('\xa0', ' ')
            sample = re.sub(r'(?<=\d)\s(?=\d)', '', sample)
            r = get_attr_int(cells[0], 'rowspan') or 1
            remaining = r
            scenario_idx = 0
            value_cells = cells[n_meta:]
        else:
            value_cells = cells

        scenario_idx += 1
        remaining -= 1

        row = {'pollster': pollster, 'date': date, 'sample': sample, 'scenario': scenario_idx}
        notes = []
        ci = 0
        for raw_cell in value_cells:
            if ci >= len(columns):
                break
            val, note, colspan = parse_value_cell(raw_cell)
            column = columns[ci]
            if column == OTHER_COLUMN and val is not None and note:
                column, note = route_other(note, columns, known)
            row[column] = val
            if note:
                notes.append(f"{column}={float(val) if val is not None else ''} ({note})")
            for skip in range(1, colspan):
                if ci + skip < len(columns):
                    row[columns[ci + skip]] = None
            ci += colspan
        row['notes'] = '; '.join(notes)
        polls.append(row)
    return polls

# --- second-round (runoff) matchup tables -----------------------------
#
# Each "== Sondages concernant le second tour ==" subsection is one
# "=== Hypothèse X – Y ===" heading followed by its own small wikitable:
# Sondeur | Dates | Échantillon | X% | Y%. Unlike the first-round table
# there's no rowspan grouping (one wiki row = one poll) and the two columns
# are the match-up itself, so this reuses strip_attrs/clean_text/
# parse_value_cell but neither parse_table's rowspan bookkeeping nor its
# header-derived column list.
#
# The heading depth is not stable: in July 2026 Wikipedia regrouped the
# Hypothèse subsections under "=== Impliquant Marine Le Pen ===" /
# "=== Impliquant Jordan Bardella ===" parents and demoted them from ===
# to ====. Accept either depth, and anchor the heading to its own line --
# with re.DOTALL an unanchored "(.+?) ===" happily runs past the end of
# the line looking for the next ===-terminated heading, which silently
# swallowed whole subsections (45 rows -> 4) rather than failing loudly.
HYPOTHESIS_RE = re.compile(
    r'(?m)^={3,4} Hypothèse ([^\n]+?) ={3,4}$\n(.*?\n\|\})', re.DOTALL
)

def is_second_round_event_row(lines):
    return len(lines) == 1 and 'colspan' in lines[0]

def parse_second_round_rows(text):
    m = re.search(r'== Sondages concernant le second tour ==(.*?)\n== ', text, re.DOTALL)
    section = m.group(1) if m else text

    rows = []
    for heading, table in HYPOTHESIS_RE.findall(section):
        header = '\n'.join(l for l in table.split('\n') if l.lstrip().startswith('!'))
        names = HEADER_NAME_RE.findall(strip_refs(header))
        if len(names) != 2:
            continue
        (name_a, party_a), (name_b, party_b) = names
        cand_a = f"{slugify(name_a)}_{slugify(party_a)}"
        cand_b = f"{slugify(name_b)}_{slugify(party_b)}"

        for lines in split_blocks(table):
            if any(l.lstrip().startswith('!') for l in lines):
                continue  # header row
            if is_second_round_event_row(lines):
                continue  # full-width event annotation row
            cells = [l[1:] if l.startswith('|') else l for l in lines]
            if len(cells) < 5:
                continue
            if all(strip_attrs(c) == '' for c in cells):
                continue  # legend/style row

            pollster = clean_text(strip_attrs(cells[0]))
            date = clean_text(strip_attrs(cells[1]))
            sample = clean_text(strip_attrs(cells[2])).replace('\xa0', ' ')
            sample = re.sub(r'(?<=\d)\s(?=\d)', '', sample)
            pct_a, _, _ = parse_value_cell(cells[3])
            pct_b, _, _ = parse_value_cell(cells[4])

            rows.append({
                'matchup': f"{cand_a}-{cand_b}",
                'candidate_a': cand_a, 'candidate_b': cand_b,
                'pollster': pollster, 'date': date, 'sample': sample,
                'pct_a': pct_a, 'pct_b': pct_b,
            })
    return rows

if __name__ == '__main__':
    with open(sys.argv[1], encoding='utf-8') as f:
        text = f.read()

    if '--second-round' in sys.argv:
        rows = parse_second_round_rows(text)
        with open(sys.argv[2], 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=[
                'matchup', 'candidate_a', 'candidate_b',
                'pollster', 'date', 'sample', 'pct_a', 'pct_b'])
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"Parsed {len(rows)} second-round matchup rows")
    else:
        polls, columns = parse_rows(text)
        with open(sys.argv[2], 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['pollster', 'date', 'sample', 'scenario'] + columns + ['notes'])
            w.writeheader()
            for p in polls:
                w.writerow(p)
        print(f"Parsed {len(polls)} scenario-rows")
