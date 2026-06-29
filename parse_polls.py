import re, csv, sys

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
    s = re.sub(r'\{\{formatnum:([^}]*)\}\}', r'\1', s)
    s = re.sub(r'\[\[[^|\]]*\|([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\[\[([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\[https?://\S+\s+([^\]]+)\]', r'\1', s)
    s = re.sub(r'\[https?://\S+\]', '', s)
    s = re.sub(r'\{\{note\|[^}]*\}\}', '', s)
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
        lines = [l for l in block.split('\n') if l.strip()]
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

if __name__ == '__main__':
    with open(sys.argv[1], encoding='utf-8') as f:
        text = f.read()
    polls = parse_rows(text)
    with open(sys.argv[2], 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['pollster', 'date', 'sample', 'scenario'] + CANDIDATES + ['notes'])
        w.writeheader()
        for p in polls:
            w.writerow(p)
    print(f"Parsed {len(polls)} scenario-rows")
