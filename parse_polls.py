import re, csv, sys, unicodedata

CANDIDATES = ['Arthaud_LO','Melenchon_LFI','Roussel_PCF','Tondelier_LE','Glucksmann_PP',
              'Attal_RE','Philippe_HOR','Villepin_LFH','Retailleau_LR','DupontAignan_DLF',
              'RN','Zemmour_REC','Autre']

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

def is_event_row(lines):
    return len(lines) == 1 and ('bgcolor' in lines[0] or re.search(r'colspan\s*=\s*"?1[3-9]"?', lines[0]))

def parse_rows(text):
    blocks = re.split(r'(?m)^\|-[^\n]*\n?', text)
    blocks = [b for b in blocks if b.strip()]
    polls = []
    pollster = date = sample = None
    remaining = 0
    scenario_idx = 0

    for block in blocks:
        lines = [l for l in block.split('\n') if l.strip() and l.strip() != '|}']
        if not lines:
            continue
        if any(l.lstrip().startswith('!') for l in lines):
            continue  # header row
        if is_event_row(lines):
            continue  # full-width event annotation row
        cells = [l[1:] if l.startswith('|') else l for l in lines]

        if remaining == 0:
            # legend/style row: every cell strips to empty content
            if all(strip_attrs(c) == '' for c in cells):
                continue
            pollster_raw, date_raw, sample_raw = cells[0], cells[1], cells[2]
            pollster = clean_text(strip_attrs(pollster_raw))
            date = clean_text(strip_attrs(date_raw))
            sample = clean_text(strip_attrs(sample_raw)).replace('\xa0', ' ')
            sample = re.sub(r'(?<=\d)\s(?=\d)', '', sample)
            r = get_attr_int(pollster_raw, 'rowspan') or 1
            remaining = r
            scenario_idx = 0
            value_cells = cells[3:]
        else:
            value_cells = cells

        scenario_idx += 1
        remaining -= 1

        row = {'pollster': pollster, 'date': date, 'sample': sample, 'scenario': scenario_idx}
        notes = []
        ci = 0
        for raw_cell in value_cells:
            if ci >= len(CANDIDATES):
                break
            val, note, colspan = parse_value_cell(raw_cell)
            row[CANDIDATES[ci]] = val
            if note:
                notes.append(f"{CANDIDATES[ci]}={float(val) if val is not None else ''} ({note})")
            for skip in range(1, colspan):
                if ci + skip < len(CANDIDATES):
                    row[CANDIDATES[ci + skip]] = None
            ci += colspan
        row['notes'] = '; '.join(notes)
        polls.append(row)
    return polls

# --- second-round (runoff) matchup tables -----------------------------
#
# Each "== Sondages concernant le second tour ==" subsection is one
# "=== Hypothèse X – Y ===" heading followed by its own small wikitable:
# Sondeur | Dates | Échantillon | X% | Y%. Unlike the first-round table
# there's no rowspan grouping (one wiki row = one poll), so this reuses
# strip_attrs/clean_text/parse_value_cell but not parse_rows's rowspan
# bookkeeping.

HYPOTHESIS_RE = re.compile(r'=== Hypothèse (.+?) ===\n(.*?\n\|\})', re.DOTALL)
# Column header cells look like:
#   [[Jean-Luc Mélenchon|Mélenchon]]<br><small>([[La France insoumise|LFI]])</small>
HEADER_NAME_RE = re.compile(
    r'\[\[[^|\]]+\|([^\]]+)\]\]<br>\s*<small>\(\[\[[^|\]]+\|([^\]]+)\]\]\)</small>'
)

def slugify(text):
    """ASCII-only identifier fragment: strip accents, drop non-alnum."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Za-z0-9]', '', text)

def is_second_round_event_row(lines):
    return len(lines) == 1 and 'colspan' in lines[0]

def parse_second_round_rows(text):
    m = re.search(r'== Sondages concernant le second tour ==(.*?)\n== ', text, re.DOTALL)
    section = m.group(1) if m else text

    rows = []
    for heading, table in HYPOTHESIS_RE.findall(section):
        names = HEADER_NAME_RE.findall(table)
        if len(names) != 2:
            continue
        (name_a, party_a), (name_b, party_b) = names
        cand_a = f"{slugify(name_a)}_{slugify(party_a)}"
        cand_b = f"{slugify(name_b)}_{slugify(party_b)}"

        blocks = re.split(r'(?m)^\|-[^\n]*\n?', table)
        for block in blocks:
            lines = [l for l in block.split('\n') if l.strip() and l.strip() != '|}']
            lines = [l for l in lines if not l.lstrip().startswith('{|')]
            if not lines:
                continue
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
        polls = parse_rows(text)
        with open(sys.argv[2], 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['pollster', 'date', 'sample', 'scenario'] + CANDIDATES + ['notes'])
            w.writeheader()
            for p in polls:
                w.writerow(p)
        print(f"Parsed {len(polls)} scenario-rows")
