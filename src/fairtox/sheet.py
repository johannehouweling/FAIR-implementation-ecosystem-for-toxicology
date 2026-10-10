"""Curation workbook: build an .xlsx with drop-downs (uploaded to Google Drive as a Google Sheet), and read the
curated copy back into the dataset with every check, reporting problems by sheet cell."""
import copy
import datetime as dt
import re

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from fairtox import fip, model, site

SPARE = 50
GREY = PatternFill('solid', fgColor='EDEDED')
HEAD = PatternFill('solid', fgColor='D6DEE6')
BOLD = Font(bold=True)
FSR_LABEL = {**{k: v[0] for k, v in model.fsr_types().items()}, **site.CLASSES}   # IRI -> label, as on the dashboard
FSR_IRI = {v: k for k, v in FSR_LABEL.items()}


def _fsr_list():
    """FSR type label -> its direct FSR subclass and category, for the types offered; grouped by direct FSR subclass."""
    t = model.fsr_types()
    group = lambda i: t[t[i][1]][0]
    return {t[i][0]: f'{group(i)}; {site.CLASSES[model.FER if t[i][2] else model.FSR]}'
            for i in sorted(model.FSR_OFFERED, key=lambda i: (group(i).casefold(), t[i][0].casefold()))}


LISTS = {
    'Decision': model.DECISION, 'Exclusion reason': model.EXCLUSION, 'Type': model.VOCABULARIES['fairsharingType'],
    'Scope': model.SCOPE, 'Phase': model.PHASES, 'Date basis': model.DATE_BASIS,
    'Maintained': model.MAINTAINED, 'In manuscript': model.MANUSCRIPT, 'FAIRsharing match': model.MATCH,
    'Relation': {k: v[2] for k, v in model.RELATIONS.items()}, 'Evidence': model.EVIDENCE,
    'Keep': {'keep': 'Keep this relation.', 'remove': 'Remove this relation.'},
    'Mark': {'x': 'Applies.'}, 'FSR type': _fsr_list(), 'FIP relation': model.FIP_PROPERTIES,
}
CREATOR_HEAD = {s: f'Made by {s.lower()}' for s in model.STAKEHOLDER}
SPAN_HEAD = {p: f'Span: {p.lower()}' for p in model.PHASES}
# (header, dataset field, kind, width, header note). Kinds: key, text, aliases, date, list:<List>, keys, mark, creator,
# span, and the grey kinds lane, fslink, static, version, which are computed or imported and ignored on import.
RESOURCE_COLUMNS = [
    ('Key', 'key', 'key', 16, 'Stable identifier. Leave empty for a new row; a key is assigned on import.'),
    ('Name', 'name', 'text', 36, 'Full name of the resource.'),
    ('Decision', 'decision', 'list:Decision', 12, 'include, exclude or undecided.'),
    ('Exclusion reason', 'exclusionReason', 'list:Exclusion reason', 10,
     'Required when Decision is exclude. Codes E1-E8 are defined on the Instructions tab.'),
    ('Covered by', 'coveredBy', 'keys', 14, 'For exclusion reason E6: the key of the row that covers this one.'),
    ('Aliases', 'alternateName', 'aliases', 18,
     'Abbreviations and other names, separated by ";". The first one is shown in the figure.'),
    ('FAIRsharing type', 'fairsharingType', 'list:Type', 32, 'FAIRsharing registry and record type, or Tool.'),
    ('FSR type', 'fsrType', 'list:FSR type', 28, 'What kind of FAIR resource this is. The Instructions tab says how to '
     'choose.'),
    ('Class', None, 'static', 16, 'Derived from FSR type: FAIR-Enabling Resource or FAIR Supporting Resource.'),
    ('Principles', None, 'static', 12, 'Principles of the FIP questions the resource is declared for.'),
    ('Declared in', None, 'static', 30, 'The toxicology FIPs that declare the resource, with the questions.'),
    ('Scope', 'scope', 'list:Scope', 18, 'Generic, Life Sciences or Toxicology.'),
    ('FAIRsharing subjects', None, 'static', 24, "FAIRsharing's subjects of the record, read when the sheet is made; "
     'compare with Scope.'),
    ('Phase', 'phase', 'list:Phase', 26,
     'The phase it acts on; the earliest when several. Only for scope Toxicology; it sets the lane.'),
    *[(SPAN_HEAD[p], p, 'span', 11, f'Mark x when a toxicology resource acts on {p.lower()}. The earliest phase '
       'marked is the Phase.') for p in model.PHASES],
    ('FAIRsharing domains', None, 'static', 24, "FAIRsharing's domains of the record, read when the sheet is made; "
     'compare with Phase and Span.'),
    ('Lane', None, 'lane', 26, 'Computed from Scope and Phase.'),
    *[(CREATOR_HEAD[s], s, 'creator', 12, f'Mark x when {s.lower()} helped create the resource. Only for scope '
       'Toxicology; several may apply.') for s in model.STAKEHOLDER],
    ('Builds on FAIR', None, 'static', 10,
     'Derived from the Relations tab: implements, extends, profiles or recommends a Generic resource.'),
    *[(s, s, 'mark', 11, f'Mark x when the resource belongs to {s}. Several sub-domains may apply.')
      for s in model.SUBDOMAINS],
    ('First published', 'datePublished', 'date', 14,
     'When the resource first became public: YYYY, YYYY-MM or YYYY-MM-DD.'),
    ('Date basis', 'dateBasis', 'list:Date basis', 16, 'What the date refers to. The Lists tab explains each choice.'),
    ('Date source', 'dateSource', 'text', 32, 'DOI or web page that shows the date.'),
    ('Creator', 'creator', 'text', 26, 'Organisation(s) that made the resource.'),
    ('Identifier', None, 'static', 34, "Computed: a community's FIC nanopublication, else the FAIRsharing DOI, else "
     'the address of the resource in this dataset.'),
    ('Homepage', 'url', 'text', 32, 'Main web address.'),
    ('Description', 'description', 'text', 50, 'One to three sentences. Needed to register it in FAIRsharing.'),
    ('Maintained', 'maintained', 'list:Maintained', 14, 'active, discontinued, in development or unknown.'),
    ('In manuscript', 'manuscript', 'list:In manuscript', 14, 'cited, named, comment only or absent.'),
    ('Manuscript evidence', 'manuscriptEvidence', 'text', 26, 'Section and line numbers in the frozen draft.'),
    ('FAIRsharing record', 'fairsharingRecord', 'text', 20, 'FAIRsharing.xxxxxx code or numeric record id.'),
    ('FAIRsharing match', 'fairsharingMatch', 'list:FAIRsharing match', 14,
     'confirmed when the FAIRsharing record is this resource.'),
    ('FAIRsharing link', None, 'fslink', 10, 'Computed from FAIRsharing record.'),
    ('In FAIRsharing collection', None, 'static', 12, 'Member of the FAIRsharing Toxicology collection (3496).'),
    ('FAIRsharing year', None, 'static', 10, "FAIRsharing's year of creation."),
    ('FAIRsharing name, type, status', None, 'static', 34, 'As recorded in FAIRsharing.'),
    ('Warnings', None, 'static', 44, 'Checks that will need attention before release.'),
    ('Reviewed by', 'reviewedBy', 'text', 12, 'Your initials once you have checked the row.'),
    ('Note', 'note', 'text', 44, 'Anything the next curator should know.'),
    ('Row version', None, 'version', 12, 'Do not edit. Detects rows that changed elsewhere after this sheet was made.'),
]
RELATION_COLUMNS = [
    ('Resource', 'subject', 'keys', 16, 'Key of the resource that builds on or relates to the target.'),
    ('Relation', 'hadRole', 'list:Relation', 14, 'How the resource relates to the target, read from left to right: '
     '"CTD implements ExO". On a grey row, what a FIP declares.'),
    ('Target', 'target', 'keys', 16, 'Key of the earlier or related resource.'),
    ('Vocabulary', None, 'static', 12, 'Where the label comes from: FAIRsharing, or a FIP on the grey rows.'),
    ('Reads as', None, 'reads', 60, 'Computed.'),
    ('Evidence', 'evidence', 'list:Evidence', 13, 'Where the relation is stated.'),
    ('Source', 'source', 'text', 34, 'Line numbers, DOI or URL.'),
    ('Question', 'question', 'static', 10, 'FIP rows: the FIP question the declaration answers.'),
    ('Use', 'use', 'static', 12, 'FIP rows: current use, planned use, planned development or planned replacement.'),
    ('Keep', None, 'list:Keep', 9, 'Set to remove to drop the relation.'),
    ('Enterable in FAIRsharing', None, 'static', 14, 'Whether FAIRsharing allows this relation between these two '
     'records.'),
    ('Reviewed by', 'reviewedBy', 'text', 12, 'Your initials once you have checked the relation.'),
    ('Note', 'note', 'text', 40, ''),
]
GREY_KINDS = {'lane', 'fslink', 'static', 'version', 'reads'}
FOLDED = ('Lane', 'Warnings', 'Row version')   # no information for curators: grouped and collapsed
INSTRUCTIONS = [
    'Edit only the white cells. Grey columns, and the grey rows on the Relations tab, are computed or read from '
    'FAIRsharing and the FIPs when the sheet is made, and are ignored when it is read back. Lane, Warnings and Row '
    'version are folded; open them with the + above the column letters.',
    'Never delete a row. To drop a resource, set Decision to exclude and choose an Exclusion reason.',
    'Add new resources at the bottom of the Resources tab and leave Key empty; a key is assigned on import.',
    'Mark each sub-domain that applies with x. A resource can belong to several.',
    'First published is the date the resource first became public, as YYYY, YYYY-MM or YYYY-MM-DD. '
    'Put the DOI or web page that shows the date in Date source.',
    'Phase is the phase a toxicology resource acts on and sets its lane: Data generation, Data integration or '
    'Regulatory assessment. When it acts on several, choose the earliest at which it must be applied. Choose by what '
    'the resource is used for, not by who made it. Mark x under Span for every phase it acts on; the earliest one '
    'marked is the Phase.',
    'FSR type is the kind of FAIR resource it is. When a toxicology FIP declares the resource, use the type the FIP '
    'gives it; otherwise choose the one that fits best (a database is a registry). Class, Principles and Declared in '
    'follow from it.',
    'FAIR Implementation Community is only for a community identified by its FIC nanopublication; any other community '
    'stays excluded as E1.',
    'Mark x in each "Made by" column that describes who created a toxicology resource; several may apply. '
    'The dashboard can also arrange the toxicology lanes by creator.',
    'Builds on FAIR is derived: a toxicology resource that implements, extends, profiles or recommends a Generic '
    'resource on the Relations tab.',
    'Relations read from left to right, for example "CTD implements ExO". Set Keep to remove to drop one; '
    'add new ones at the bottom of the Relations tab. The grey rows are what the toxicology FIPs declare, read when '
    'the sheet is made; they are read-only. Vocabulary says which is which.',
    'Put your initials in Reviewed by when you have checked a row.',
]
CRITERIA_TEXT = [
    'I1 It is a resource, not an organisation, project, community, event or publication, except a FAIR Implementation '
    'Community identified by its FIC nanopublication.',
    'I2 It is named and identifiable (homepage or DOI).',
    'I3 It is or was publicly available.',
    'I4 Its use in toxicology is documented: in the manuscript, in the FAIRsharing Toxicology collection or in a '
    'toxicology FIP.',
    'I5 It makes data or metadata findable, accessible, interoperable or reusable.',
]


def _lists_columns():
    return {name: get_column_letter(i + 1) for i, name in enumerate(LISTS)}


def _validation(ws, kind, letter, rows, keys_range):
    if kind.startswith('list:'):
        name = kind[5:]
        col = _lists_columns()[name]
        formula = f'=Lists!${col}$2:${col}${1 + len(LISTS[name])}'
    elif kind == 'keys':
        formula = keys_range
    elif kind in ('mark', 'creator', 'span'):
        formula = '"x"'
    else:
        return
    dv = DataValidation(type='list', formula1=formula, allow_blank=True, showErrorMessage=True, errorStyle='stop',
                        errorTitle='Not an allowed value', error='Choose a value from the list.')
    for first, last in rows:
        if first <= last:
            dv.add(f'{letter}{first}:{letter}{last}')
    ws.add_data_validation(dv)


def _header(ws, columns):
    for i, (head, field, kind, width, note) in enumerate(columns, 1):
        c = ws.cell(row=1, column=i, value=head)
        c.font, c.fill = BOLD, HEAD
        c.alignment = Alignment(wrap_text=True, vertical='top')
        if note:
            c.comment = Comment(note, 'fairtox')
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[1].height = 45


def _sort_key(r):
    lanes = model.LANES + ['']
    return (r.get('decision') == 'exclude', lanes.index(model.lane(r)), r['name'].lower())


def build(doc, path):
    """Write the curation workbook for the dataset with FAIRsharing and the FIP declarations added (fairsharing.enrich,
    fip.enrich)."""
    doc = model.normalise(copy.deepcopy(doc))
    _, warnings = model.check(doc)
    warn = {}
    for w in warnings:
        warn.setdefault(w.split(':', 1)[0], []).append(w.split(':', 1)[1].strip())
    rows = sorted(doc['hasPart'], key=_sort_key)
    rels = model.relation_rows(doc)
    by_key = {r['key']: r for r in doc['hasPart']}
    key_of = {r['@id']: r['key'] for r in doc['hasPart']}
    fips = sorted(({'subject': r['key'], 'hadRole': p, 'target': key_of.get(d[p], d[p]), 'evidence': 'FIP',
                    'source': d['@id'], 'question': fip._q(d['question']),
                    'use': p.removeprefix('declares-').removesuffix('-of').replace('-', ' ')}
                   for r in doc['hasPart'] for d in r.get('fipDeclaration', [])
                   for p in model.FIP_PROPERTIES.keys() & d.keys()),
                  key=lambda x: (x['subject'], x['target'], x['question']))
    declared = {}                                           # declared resource key -> FIP key -> questions
    for x in fips:
        declared.setdefault(x['target'], {}).setdefault(x['subject'], set()).add(x['question'])
    wb = Workbook()
    ins = wb.active
    ins.title = 'Instructions'
    res = wb.create_sheet('Resources')
    rel = wb.create_sheet('Relations')
    lst = wb.create_sheet('Lists')
    src = wb.create_sheet('Sources')

    # Instructions
    ins.column_dimensions['A'].width = 28
    ins.column_dimensions['B'].width = 110
    ins['A1'] = 'Curation sheet: FAIR implementation ecosystem for toxicology'
    ins['A1'].font = Font(bold=True, size=14)
    stamp = [('Dataset version', doc['version']), ('Sheet made on', dt.date.today().isoformat()),
             ('Resources', len(rows)), ('Relations', len(rels))]
    for i, (a, b) in enumerate(stamp, 3):
        ins.cell(row=i, column=1, value=a).font = BOLD
        ins.cell(row=i, column=2, value=b).alignment = Alignment(horizontal='left')
    line = 8
    for title, items in (('How to edit', INSTRUCTIONS),
                         ('Lanes', [f'{k}: {v}' for k, v in model.LANE_DEF.items()]),
                         ('Include a resource when all of these hold', CRITERIA_TEXT),
                         ('Exclusion reasons', [f'{k} {v}' for k, v in model.EXCLUSION.items()]),
                         ('Full criteria', [site.CRITERIA])):
        ins.cell(row=line, column=1, value=title).font = BOLD
        for text in items:
            ins.cell(row=line, column=2, value=text).alignment = Alignment(wrap_text=True)
            line += 1
        line += 1

    # Lists: one column of values per list, then a definitions table
    letters = _lists_columns()
    for name, vocab in LISTS.items():
        col = letters[name]
        lst[f'{col}1'] = name
        lst[f'{col}1'].font = BOLD
        for i, value in enumerate(vocab, 2):
            lst[f'{col}{i}'] = value
        lst.column_dimensions[col].width = max(10, min(36, max(len(str(v)) for v in vocab) + 2))
    d0 = len(LISTS) + 2
    for j, head in enumerate(('List', 'Value', 'Definition')):
        c = lst.cell(row=1, column=d0 + j, value=head)
        c.font = BOLD
    i = 2
    for name, vocab in LISTS.items():
        for value, definition in vocab.items():
            for j, v in enumerate((name, value, definition)):
                lst.cell(row=i, column=d0 + j, value=v)
            i += 1
    lst.column_dimensions[get_column_letter(d0 + 2)].width = 90

    # Resources
    _header(res, RESOURCE_COLUMNS)
    last = 1 + len(rows) + SPARE
    keys_range = f'=Resources!$A$2:$A${last}'
    col_of = {head: get_column_letter(i) for i, (head, *_) in enumerate(RESOURCE_COLUMNS, 1)}
    for n in range(2, last + 1):
        r = rows[n - 2] if n - 2 < len(rows) else None
        for i, (head, field, kind, *_) in enumerate(RESOURCE_COLUMNS, 1):
            c = res.cell(row=n, column=i)
            if kind in GREY_KINDS or kind == 'key':
                c.fill = GREY
            if kind == 'date':
                c.number_format = '@'
            if kind == 'lane':
                s, k = f'{col_of["Scope"]}{n}', f'{col_of["Phase"]}{n}'
                c.value = (f'=IF({s}="Generic","Generic infrastructure",'
                           f'IF({s}="Life Sciences","Life sciences infrastructure",IF({s}="Toxicology",{k}&"","")))')
                continue
            if kind == 'fslink':
                f = f'{col_of["FAIRsharing record"]}{n}'
                c.value = (f'=IF({f}="","",HYPERLINK(IF(LEFT({f},12)="FAIRsharing.","https://doi.org/10.25504/"&{f},'
                           f'"https://fairsharing.org/"&{f}),"open"))')
                continue
            if r is None:
                continue
            fs = r.get('fairsharing') or {}
            if kind == 'mark':
                c.value = 'x' if field in r.get('subdomains', []) else None
            elif kind == 'creator':
                c.value = 'x' if field in r.get('creatorType', []) else None
            elif kind == 'span':
                c.value = 'x' if field in r.get('span', []) else None
            elif field == 'fsrType':
                c.value = next((FSR_LABEL.get(t, t) for t in r.get('fsrType', [])), None)
            elif head == 'Class':
                c.value = FSR_LABEL.get(r.get('fsrCategory'))
            elif head == 'Principles':
                c.value = ', '.join(r.get('principles', [])) or None
            elif head == 'Declared in':
                c.value = '; '.join(f'{site.label(by_key[k])} ({", ".join(sorted(q))})'
                                    for k, q in declared.get(r['key'], {}).items()) or None
            elif head == 'Builds on FAIR':
                c.value = 'yes' if r.get('buildsOnFair') else None
            elif kind == 'aliases':
                c.value = '; '.join(r.get('alternateName', [])) or None
            elif kind == 'version':
                c.value = model.row_hash(r)
            elif field in ('datePublished', 'dateBasis'):   # the date and its basis, whichever field holds it
                c.value = model.first_date(r)[field == 'dateBasis'] or None
            elif head == 'Identifier':
                c.value = r.get('identifier')
            elif head == 'In FAIRsharing collection':
                c.value = ('yes' if fs.get('inCollection') else 'no') if fs else None
            elif head in ('FAIRsharing subjects', 'FAIRsharing domains'):
                c.value = '; '.join(t['label'] for t in fs.get(head.split()[1], [])) or None
            elif head == 'FAIRsharing year':
                c.value = fs.get('yearCreation')
            elif head == 'FAIRsharing name, type, status':
                c.value = ', '.join(str(fs[k]) for k in ('name', 'recordType', 'status') if fs.get(k)) or None
            elif head == 'Warnings':
                c.value = '; '.join(warn.get(r['key'], [])) or None
            elif field:
                c.value = r.get(field) or None
    for i, (head, field, kind, *_) in enumerate(RESOURCE_COLUMNS, 1):
        _validation(res, kind, get_column_letter(i), [(2, last)], keys_range)
    for i, (head, *_) in enumerate(RESOURCE_COLUMNS, 1):
        if head in FOLDED:
            res.column_dimensions.group(get_column_letter(i), hidden=True)
    res.freeze_panes = 'C2'
    res.auto_filter.ref = f'A1:{get_column_letter(len(RESOURCE_COLUMNS))}{last}'

    # Relations: the curated ones, the FIP declarations (grey, read-only), then empty rows for new ones
    _header(rel, RELATION_COLUMNS)
    lines = rels + fips
    rlast = 1 + len(lines) + SPARE
    for n in range(2, rlast + 1):
        x = lines[n - 2] if n - 2 < len(lines) else None
        fixed = x is not None and x['hadRole'] in model.FIP_PROPERTIES
        for i, (head, field, kind, *_) in enumerate(RELATION_COLUMNS, 1):
            c = rel.cell(row=n, column=i)
            if kind in GREY_KINDS or fixed:
                c.fill = GREY
            if kind == 'reads':
                c.value = (f'=IF(OR(A{n}="",C{n}=""),"",IFERROR(VLOOKUP(A{n},Resources!$A:$B,2,FALSE),A{n})&" "&'
                           f'SUBSTITUTE(B{n},"_"," ")&" "&IFERROR(VLOOKUP(C{n},Resources!$A:$B,2,FALSE),C{n}))')
                continue
            if x is None:
                continue
            if head == 'Keep' and not fixed:
                c.value = 'keep'
            elif head == 'Enterable in FAIRsharing' and not fixed:
                pair = (model.registry(by_key[x['subject']]), model.registry(by_key[x['target']]))
                c.value = 'yes' if pair in model.ALLOWED.get(x['hadRole'], set()) else 'no'
            elif head == 'Vocabulary':
                c.value = 'FIP ontology' if fixed else 'FAIRsharing'
            elif field:
                c.value = x.get(field) or None
    for i, (head, field, kind, *_) in enumerate(RELATION_COLUMNS, 1):   # not on the FIP rows
        _validation(rel, kind, get_column_letter(i), [(2, 1 + len(rels)), (2 + len(lines), rlast)], keys_range)
    rel.freeze_panes = 'A2'
    rel.auto_filter.ref = f'A1:{get_column_letter(len(RELATION_COLUMNS))}{rlast}'

    # Sources
    src.append(['Source', 'Details', 'Used for'])
    for c in src[1]:
        c.font = BOLD
    used = {'manuscript': 'Resources named in the manuscript, their manuscript status and line references.',
            'fairsharing': 'Members of the FAIRsharing Toxicology collection and FAIRsharing record data.',
            'previous': 'Earlier evidence for dates, DOIs and FAIRsharing records, to be verified.',
            'fip': 'FIP declarations: the grey rows on the Relations tab, and Principles and Declared in.'}
    for name, s in doc.get('sources', {}).items():
        for title, v in ({f'{name} {k}': v for k, v in s.items()} if name == 'fip' else {name: s}).items():  # per FIP
            details = '; '.join(f'{k}: {", ".join(x) if isinstance(x, list) else x}' for k, x in v.items()) \
                if isinstance(v, dict) else str(v)
            src.append([title, details, used.get(name, '')])
    src.column_dimensions['A'].width = 16
    src.column_dimensions['B'].width = 100
    src.column_dimensions['C'].width = 70
    wb.save(path)
    return len(rows), len(rels)


# ---- reading a curated workbook back ---------------------------------------------------------------------------------

def _text(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime('%Y-%m-%d')
    return str(v).strip()


def _url(v):
    v = _text(v)
    if re.match(r'^10\.\d{4,}/\S+$', v):
        return 'https://doi.org/' + v
    if v.lower().startswith('doi:'):
        return 'https://doi.org/' + v[4:].strip()
    return v


def ingest(doc, path, force=False):
    """Read a curated workbook. Returns (new_doc, changes, problems, notes, reviewers); new_doc is None when there are
    problems. Problems are dicts with sheet, cell, column, value, problem; reviewers maps key -> Reviewed by."""
    wb = load_workbook(path, data_only=True)
    problems, notes = [], []

    def problem(sheet, cell, column, value, text):
        problems.append({'sheet': sheet, 'cell': cell, 'column': column, 'value': _text(value), 'problem': text})

    for name in ('Resources', 'Relations'):
        if name not in wb.sheetnames:
            problem(name, '', '', '', f'the {name} tab is missing')
    if problems:
        return None, [], problems, notes, {}
    new = copy.deepcopy(doc)
    rows = {r['key']: r for r in new['hasPart']}
    current = {r['key']: model.row_hash(r) for r in doc['hasPart']}
    ws = wb['Resources']
    head = {_text(c.value): i for i, c in enumerate(ws[1]) if _text(c.value)}
    missing = [h for h, f, *_ in RESOURCE_COLUMNS if f and h not in head]
    if missing:
        problem('Resources', '1', ', '.join(missing), '', 'columns missing; do not rename or delete columns')
        return None, [], problems, notes, {}
    seen, row_of, reviewer = set(), {}, {}
    for cells in ws.iter_rows(min_row=2):
        n = cells[0].row
        val = {h: cells[i].value for h, i in head.items() if i < len(cells)}
        where = {h: f'{get_column_letter(i + 1)}{n}' for h, i in head.items()}
        if not any(_text(val.get(h)) for h, f, k, *_ in RESOURCE_COLUMNS if f and k != 'key'):
            continue
        key = _text(val.get('Key'))
        version = _text(val.get('Row version'))
        parsed, bad = {}, False
        for h, field, kind, *_ in RESOURCE_COLUMNS:
            if not field or kind in ('key', 'mark', 'creator', 'span'):
                continue
            v = val.get(h)
            if kind == 'aliases':
                parsed[field] = [a.strip() for a in _text(v).split(';') if a.strip()]
            elif kind == 'date':
                parsed[field] = _text(v)
                if isinstance(v, (dt.datetime, dt.date)):
                    notes.append(f'Resources!{where[h]}: a date was converted by the spreadsheet; check its precision')
            elif kind.startswith('list:'):
                t = _text(v)
                if kind == 'list:Exclusion reason':
                    t = t.split()[0] if t else ''
                if t and t not in LISTS[kind[5:]]:
                    problem('Resources', where[h], h, v, f'{t!r} is not one of the allowed values')
                    bad = True
                if field == 'fsrType':                      # FSR type, back to its IRI
                    parsed[field] = [FSR_IRI[t]] if t in LISTS['FSR type'] else []
                else:
                    parsed[field] = t
            elif field in ('url', 'dateSource'):
                parsed[field] = _url(v)
            else:
                parsed[field] = _text(v)
        parsed['subdomains'] = [s for s in model.SUBDOMAINS if _text(val.get(s)).lower() == 'x']
        parsed['creatorType'] = [s for s in model.STAKEHOLDER if _text(val.get(CREATOR_HEAD[s])).lower() == 'x']
        parsed['span'] = [p for p in model.PHASES if _text(val.get(SPAN_HEAD[p])).lower() == 'x']
        parsed['fsrType'] = list(dict.fromkeys(parsed['fsrType']))
        for mark in list(model.SUBDOMAINS) + list(CREATOR_HEAD.values()) + list(SPAN_HEAD.values()):
            t = _text(val.get(mark)).lower()
            if t and t != 'x':
                problem('Resources', where.get(mark, ''), mark, val.get(mark), 'mark with x or leave it empty')
                bad = True
        if not parsed['name']:
            problem('Resources', where['Name'], 'Name', '', 'every row needs a name')
            continue
        if key and key in seen:
            problem('Resources', where['Key'], 'Key', key, 'this key appears twice')
            continue
        if key and key not in rows:
            if version:
                problem('Resources', where['Key'], 'Key', key, 'unknown key; keys must not be edited')
                continue
            if not model.KEY_RE.match(key):
                problem('Resources', where['Key'], 'Key', key, 'a new key may only use a-z, 0-9, _ and -')
                continue
        if not key:
            key = model.slug((parsed['alternateName'] or [parsed['name']])[0], set(rows) | seen)
            notes.append(f'Resources row {n}: new resource {parsed["name"]!r} gets key {key!r}')
        seen.add(key)
        row_of[key] = n
        if bad:
            continue
        old = rows.get(key)
        if old is None:
            parsed.setdefault('decision', 'undecided')
            parsed['decision'] = parsed['decision'] or 'undecided'
            parsed['manuscript'] = parsed.get('manuscript') or 'absent'
            rows[key] = {'key': key, **parsed}
            new['hasPart'].append(rows[key])
        else:
            date, basis = model.first_date(old)                  # the sheet's form of the date
            seen_as = {**old, 'datePublished': date, 'dateBasis': basis}
            changed = any(model._text(seen_as.get(f)) != model._text(parsed.get(f)) for f in parsed)
            if changed and version and version != current.get(key) and not force:
                problem('Resources', where['Key'], 'Key', key,
                        'this row changed in the dataset after the sheet was made; make a new sheet or re-check it')
                continue
            old.update(parsed)
        if _text(val.get('Reviewed by')):
            reviewer[key] = _text(val.get('Reviewed by'))
    absent = sorted(set(current) - seen)
    if absent:
        notes.append(f'{len(absent)} rows are not in the sheet and were left unchanged: {", ".join(absent[:12])}'
                     + (' ...' if len(absent) > 12 else ''))

    model.normalise(new)
    id_of = {r['key']: r['@id'] for r in new['hasPart']}
    by_key = {r['key']: r for r in new['hasPart']}
    ws = wb['Relations']
    head = {_text(c.value): i for i, c in enumerate(ws[1]) if _text(c.value)}
    for cells in ws.iter_rows(min_row=2):
        n = cells[0].row
        val = {h: cells[i].value for h, i in head.items() if i < len(cells)}
        subject, label, target = (_text(val.get(h)) for h in ('Resource', 'Relation', 'Target'))
        if not (subject or label or target) or label in model.FIP_PROPERTIES:   # FIP rows are read-only
            continue
        bad = False
        for h, v, ok in (('Resource', subject, subject in by_key), ('Relation', label, label in model.RELATIONS),
                         ('Target', target, target in by_key)):
            if not ok:
                col = get_column_letter(head.get(h, 0) + 1)
                problem('Relations', f'{col}{n}', h, v, 'missing or not an allowed value')
                bad = True
        evidence, keep = _text(val.get('Evidence')), _text(val.get('Keep')) or 'keep'
        if keep not in LISTS['Keep']:
            problem('Relations', f'{get_column_letter(head["Keep"] + 1)}{n}', 'Keep', keep, 'use keep or remove')
            bad = True
        if bad:
            continue
        rels = by_key[subject].setdefault('qualifiedRelation', [])
        existing = next((q for q in rels if q['relation'] == id_of[target] and q['hadRole'] == label), None)
        if keep == 'remove':
            if existing:
                rels.remove(existing)
            continue
        q = existing or {'relation': id_of[target], 'hadRole': label}
        q.update(evidence=evidence or q.get('evidence') or 'curator', source=_text(val.get('Source')),
                 reviewedBy=_text(val.get('Reviewed by')), note=_text(val.get('Note')))
        if existing is None:
            rels.append(q)

    model.normalise(new)
    errors, _ = model.check(new)
    for e in errors:
        key = e.split(':', 1)[0].strip("'")
        n = row_of.get(key)
        problem('Resources', f'A{n}' if n else '', '', key, e)
    if problems:
        return None, [], problems, notes, {}
    return new, model.diff(doc, new), [], notes, reviewer
