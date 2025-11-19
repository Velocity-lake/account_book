import zipfile
from xml.etree import ElementTree as ET

def _col_to_index(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n - 1

def _parse_shared_strings(z):
    try:
        with z.open('xl/sharedStrings.xml') as f:
            root = ET.fromstring(f.read())
        strings = []
        for si in root.iter():
            tag = si.tag if isinstance(si.tag, str) else ''
            if tag.endswith('si'):
                text = ''
                for t in si.iter():
                    ttag = t.tag if isinstance(t.tag, str) else ''
                    if ttag.endswith('t') and t.text is not None:
                        text += t.text
                strings.append(text)
        return strings
    except KeyError:
        return []

def _cell_value(c, shared):
    t = c.attrib.get('t')
    v = None
    for child in c:
        tag = child.tag if isinstance(child.tag, str) else ''
        if tag.endswith('v'):
            v = child.text
            break
        if tag.endswith('is'):
            for tt in child.iter():
                ttag = tt.tag if isinstance(tt.tag, str) else ''
                if ttag.endswith('t') and tt.text is not None:
                    return tt.text
    if t == 's' and v is not None:
        try:
            idx = int(v)
            return shared[idx] if 0 <= idx < len(shared) else ''
        except Exception:
            return ''
    return v if v is not None else ''

def read_xlsx(path):
    with zipfile.ZipFile(path) as z:
        shared = _parse_shared_strings(z)
        sheet_path = 'xl/worksheets/sheet1.xml'
        try:
            with z.open(sheet_path) as f:
                root = ET.fromstring(f.read())
        except KeyError:
            return []
    rows = []
    for row in root.iter():
        tag = row.tag if isinstance(row.tag, str) else ''
        if tag.endswith('row'):
            cells = {}
            max_idx = -1
            for c in row:
                ctag = c.tag if isinstance(c.tag, str) else ''
                if not ctag.endswith('c'):
                    continue
                ref = c.attrib.get('r', '')
                col = ''.join(ch for ch in ref if ch.isalpha())
                idx = _col_to_index(col) if col else (max_idx + 1)
                val = _cell_value(c, shared)
                cells[idx] = val
                if idx > max_idx:
                    max_idx = idx
            if max_idx >= 0:
                row_vals = [''] * (max_idx + 1)
                for i, v in cells.items():
                    row_vals[i] = v
                rows.append(row_vals)
    if not rows:
        return []
    header_idx = None
    for i, r in enumerate(rows):
        lowered = [str(x).strip() for x in r]
        if any(h in lowered for h in ["交易时间", "金额", "金额(元)"]):
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0
    header = [str(h).strip() for h in rows[header_idx]]
    out = []
    for r in rows[header_idx + 1:]:
        d = {}
        for i in range(min(len(header), len(r))):
            key = header[i] if header[i] else f"列{i}"
            d[key] = r[i]
        if any(str(v).strip() != '' for v in d.values()):
            out.append(d)
    return out
