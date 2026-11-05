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
            for i in sorted(model.fsr_offered(), key=lambda i: (group(i).casefold(), t[i][0].casefold()))}


LISTS = {
    'Decision': model.DECISION, 'Exclusion reason': model.EXCLUSION,
    'FAIRsharing type': model.VOCABULARIES['fairsharingType'],
    'Origin': model.ORIGIN, 'Phase': model.PHASES, 'Sub-domains': model.SUBDOMAINS, 'Date basis': model.DATE_BASIS,
    'Maintained': model.MAINTAINED, 'In manuscript': model.MANUSCRIPT, 'FAIRsharing match': model.MATCH,
    'Relation': {k: v[2] for k, v in model.RELATIONS.items()}, 'Evidence': model.EVIDENCE,
    'Keep': {'keep': 'Keep this relation.', 'remove': 'Remove this relation.'},
    'Mark': {'x': 'Applies.'}, 'FSR type': _fsr_list(), 'FIP relation': model.FIP_PROPERTIES,
}
CREATOR_HEAD = {s: f'Made by {s.lower()}' for s in model.STAKEHOLDER}
ETC_HEAD = {d: f'ETC: {d}' for d in model.ETC_DOCUMENTS}
MARKED = ('x', 'true')                                      # how a mark reads back: an x, or a ticked box
GREY_NOTE = 'Grey, not read back: '                         # every grey column's note opens with what grey means
MULTI = {'span': model.PHASES, 'subdomains': model.SUBDOMAINS,   # multi-select columns: field -> its list, in order
         'fsrType': [FSR_LABEL[i] for i in model.fsr_offered()]}   # an FSR type by its label
# (header, dataset field, kind, width, header note). Kinds: key, text, several (separated by ";"), date, list:<List>,
# keys, mark, creator, and the grey kinds lane, fslink, static, version, which are computed or imported and ignored on
# import.
# The Resources tab puts what curators check first, in the order of the curation steps; the context follows, folded.
TASK_COLUMNS = [
    ('Key', 'key', 'key', 16, 'Stable identifier, never changed. For a new row, type a short key: lowercase letters, '
     'digits, _ or -.'),
    ('Name', 'name', 'text', 36, 'Full name of the resource.'),
    ('URL', 'url', 'text', 32, 'Main web address.'),
    ('Reviewed by', 'reviewedBy', 'text', 12, 'Your initials once you have checked the whole row: this confirms it.'),
    ('Sub-domains', 'subdomains', 'list:Sub-domains', 30, 'The toxicology sub-domains the resource belongs to: choose '
     'each one that applies.'),
    ('Source', None, 'static', 30, GREY_NOTE + 'where the resource is found: the manuscript draft, the FAIRsharing '
     "Toxicology collection, a toxicology FIP, a co-author's repository inventory, or added by a co-author in this "
     'sheet. It tells you why the row is here.'),
    ('Decision', 'decision', 'list:Decision', 12, 'include, exclude or undecided.'),
    ('Exclusion reason', 'exclusionReason', 'list:Exclusion reason', 10,
     'Required when Decision is exclude. Codes E1-E8 are defined on the Instructions tab.'),
    ('Covered by', 'coveredBy', 'keys', 14, 'For exclusion reason E6: the key of the row that covers this one.'),
    ('FSR type', 'fsrType', 'list:FSR type', 28, 'What kind of FAIR resource this is: choose each one that applies. The '
     'Instructions tab says how to choose.'),
    ('FAIRsharing type', 'fairsharingType', 'list:FAIRsharing type', 32,
     'FAIRsharing registry and record type, or Tool.'),
    ('Origin', 'origin', 'list:Origin', 18, 'Where the resource comes from: Generic, Life Sciences or Toxicology.'),
    ('FAIRsharing subjects', None, 'static', 24, GREY_NOTE + "FAIRsharing's subjects of the record, read when the "
     'sheet is made. Compare them with Origin and correct Origin if they disagree.'),
    ('Phase', 'span', 'list:Phase', 26,
     'Every phase it acts on: choose each one that applies. The earliest sets the lane. Only for origin Toxicology.'),
    ('FAIRsharing domains', None, 'static', 24, GREY_NOTE + "FAIRsharing's domains of the record, read when the "
     'sheet is made. Compare them with Phase and correct Phase if they disagree.'),
    *[(CREATOR_HEAD[s], s, 'creator', 12, f'Mark x when {s.lower()} helped create the resource. Only for origin '
       'Toxicology; several may apply.') for s in model.STAKEHOLDER],
    ('Creator', 'creator', 'text', 26, 'Organisation(s) that made the resource.'),
    ('Contact', 'contactPoint', 'several', 26, "Who to contact about the resource: a person's ORCID or an organisation's "
     'ROR, as a link; several separated by ";".'),
    ('First published', 'datePublished', 'date', 14,
     'When the resource first became public: YYYY, YYYY-MM or YYYY-MM-DD.'),
    ('Date basis', 'dateBasis', 'list:Date basis', 16, 'What the date refers to. The Lists tab explains each choice.'),
    ('Citation', 'dateSource', 'text', 32, 'DOI or web page that shows the date.'),
    ('Description', 'description', 'text', 50, 'One to three sentences. Needed to register it in FAIRsharing.'),
    ('Maintained', 'maintained', 'list:Maintained', 14, 'active, discontinued, in development or unknown.'),
    *[(ETC_HEAD[d], d, 'etc', 10, 'Tick when this ELIXIR Toxicology Community document mentions the resource: '
       + text) for d, text in model.ETC_DOCUMENTS.items()],
    ('Note', 'note', 'text', 44, 'Anything the next curator should know.'),
]
CONTEXT_COLUMNS = [
    ('Identifier', None, 'static', 34, GREY_NOTE + "the resource's address in the published dataset: a community's "
     'FIC nanopublication, else the FAIRsharing DOI, else an address of this dataset.'),
    ('FIP identifiers', None, 'static', 34, GREY_NOTE + 'the addresses under which the toxicology FIPs declare the '
     'resource, when they differ from its Identifier. They show that a FIP means this resource.'),
    ('FAIRsharing record', 'fairsharingRecord', 'text', 20, 'FAIRsharing.xxxxxx code or numeric record id.'),
    ('FAIRsharing match', 'fairsharingMatch', 'list:FAIRsharing match', 14,
     'confirmed when the FAIRsharing record is this resource.'),
    ('FAIRsharing link', None, 'fslink', 10, GREY_NOTE + 'opens the FAIRsharing record named in FAIRsharing record, '
     'to check that it is this resource.'),
    ('FAIRsharing name, type, status', None, 'static', 34, GREY_NOTE + 'the name, record type and status FAIRsharing '
     'gives the record. Compare them with Name, FAIRsharing type and Maintained.'),
    ('FAIRsharing year', None, 'static', 10, GREY_NOTE + "FAIRsharing's year of creation of the record. Compare it "
     'with First published; a difference of more than a year is worth a look.'),
    ('Class', None, 'static', 16, GREY_NOTE + 'follows from FSR type: FAIR-Enabling Resource when one of the types '
     'chosen is one, else FAIR Supporting Resource. To change it, change FSR type.'),
    ('Principles', None, 'static', 12, GREY_NOTE + 'the FAIR principles of the FIP questions the resource is declared '
     'for. They come from the FIPs, not from this sheet.'),
    ('Declared in', None, 'static', 30, GREY_NOTE + 'the toxicology FIPs that declare the resource, with the '
     'questions. The grey rows on the Relations tab list the same declarations.'),
    ('Builds on FAIR', None, 'static', 10, GREY_NOTE + 'yes when the Relations tab says the resource implements, '
     'extends or profiles a Generic resource. To change it, edit the Relations tab.'),
    ('Lane', None, 'lane', 26, GREY_NOTE + 'where the dashboard draws the resource, from Origin and the earliest '
     'Phase. To change it, change Origin or Phase.'),
    ('Warnings', None, 'static', 44, GREY_NOTE + 'checks that will need attention before release, found when the '
     'sheet was made. Fix the white cells they point at.'),
    ('In manuscript', 'manuscript', 'list:In manuscript', 14, 'cited, named, comment only or absent.'),
    ('Manuscript evidence', 'manuscriptEvidence', 'text', 26, 'Section and line numbers in the frozen draft.'),
    ('Aliases', 'alternateName', 'several', 18,
     'Abbreviations and other names, separated by ";". The first one is shown in the figure.'),
    ('Row version', None, 'version', 12, GREY_NOTE + 'a fingerprint of the row when the sheet was made, which detects '
     'rows that changed elsewhere since. Do not edit it: an edited version makes the row wait.'),
]
RESOURCE_COLUMNS = TASK_COLUMNS + CONTEXT_COLUMNS
RELATION_COLUMNS = [
    ('Resource', 'subject', 'keys', 16, 'Key of the resource that builds on or relates to the target.'),
    ('Relation', 'hadRole', 'list:Relation', 14, 'How the resource relates to the target, read from left to right: '
     '"CTD implements ExO". A relation fits only certain kinds of resource; a line that does not fit waits. On a grey '
     'row, what a FIP declares.'),
    ('Target', 'target', 'keys', 16, 'Key of the earlier or related resource.'),
    ('Vocabulary', None, 'static', 12, GREY_NOTE + 'where the relation label comes from: FAIRsharing on the white '
     'lines, a FIP on the grey ones.'),
    ('Reads as', None, 'reads', 60, GREY_NOTE + 'the line as a sentence, Resource, Relation, Target, to check that '
     'you have the direction right.'),
    ('Evidence', 'evidence', 'list:Evidence', 13, 'Where the relation is stated.'),
    ('Source', 'source', 'text', 34, 'Line numbers, DOI or URL.'),
    ('Question', 'question', 'static', 10, GREY_NOTE + 'on a grey line, the FIP question the declaration answers, '
     'such as F1-D.'),
    ('Use', 'use', 'static', 12, GREY_NOTE + 'on a grey line, what the FIP declares: current use, planned use, '
     'planned development or planned replacement.'),
    ('Keep', None, 'list:Keep', 9, 'Set to remove to drop the relation.'),
    ('Enterable in FAIRsharing', None, 'static', 14, GREY_NOTE + 'whether FAIRsharing allows this relation between '
     'these two record types. A no is fine here; it only means the relation cannot be entered in FAIRsharing.'),
    ('Reviewed by', 'reviewedBy', 'text', 12, 'Your initials once you have checked the relation: this confirms it.'),
    ('Note', 'note', 'text', 40, ''),
    ('Line version', None, 'version', 12, GREY_NOTE + 'a fingerprint of the line when the sheet was made, which '
     'detects relations that changed elsewhere since. Do not edit it: an edited version makes the line wait.'),
]
GREY_KINDS = {'lane', 'fslink', 'static', 'version', 'reads'}
NOT_INITIALS = 'initials only, in one word; a remark goes in Note'
FOLDED = tuple(h for h, *_ in CONTEXT_COLUMNS)   # context, not tasks: grouped and collapsed
INSTRUCTIONS = [
    'Edit the white cells only. Grey is read-only: computed, or read from FAIRsharing and the FIPs, and ignored when '
    'the sheet is read back. You cannot break anything: the sheet is read back three times a day, every edit is '
    'checked, and a row with a problem waits here.',
    'Find your rows on the Resources tab: filter Sub-domains, or filter Reviewed by on blanks. Choose each sub-domain '
    'that applies.',
    'Check a row left to right up to Note; the folded context after Note opens with the + above the column letters. '
    'A value is a proposal until a co-author checks its row; Note says where it comes from.',
    'Decision: include, exclude or undecided. Never delete a row; to drop a resource, set Decision to exclude and '
    'choose an Exclusion reason (E1-E8, below). For E6, name the covering row in Covered by.',
    'FSR type: each type that applies: those a toxicology FIP gives the resource, otherwise the best fit (a database is '
    'a registry). Class, Principles and Declared in follow from it. FAIR Implementation Community only for a community '
    'with its own FIC nanopublication, and with no other type; any other community is E1.',
    'Phase: every phase the resource acts on; the earliest sets its lane. Judge by what it is used for, not by who '
    'made it. Who made it goes in the Made by columns: x in each that applies.',
    'First published: YYYY, YYYY-MM or YYYY-MM-DD; the DOI or page that shows it in Citation.',
    'Checked the whole row and fixed what is wrong? Put your initials in Reviewed by. To change a row someone else '
    'signed, check it again and sign it yourself, or empty Reviewed by.',
    'New resource: a row at the bottom of the Resources tab, with a short key of your own (lowercase letters, digits, '
    '_ or -); fill it in and sign it.',
    'Relations tab: a line reads Resource, Relation, Target ("CTD implements ExO"). Edit a line to change it; never '
    'delete one: set Keep to remove. Add new lines at the bottom and sign them in Reviewed by. An unsigned copy of a '
    'signed line is ignored. The grey lines are what the FIPs declare, read-only. Builds on FAIR on the Resources tab '
    'follows from this tab.',
]
CRITERIA_TEXT = [
    'I1 It is a resource, not an organisation, project, community, event or publication, except a FAIR Implementation '
    'Community identified by its FIC nanopublication.',
    'I2 It is named and identifiable (homepage or DOI).',
    'I3 It is or was publicly available.',
    'I4 Its use in toxicology is documented: in the manuscript, in the FAIRsharing Toxicology collection, in a '
    'toxicology FIP, in an ELIXIR Toxicology Community document, or by a co-author who added it.',
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
    elif kind == 'creator':
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


ORIGIN_HEAD = {'Toxicology': 'Toxicology', 'Life Sciences': 'Life sciences', 'Generic': 'Generic'}


def _principles(ws):
    """The Principles tab: per FAIR principle and origin, the included FAIR-enabling resources one of whose FSR types
    enables the principle in the FIP ontology, without those whose sub-domains are all outside the manuscript's scope,
    as in the figure. The counts are formulas over the Resources tab, so they follow every edit."""
    col = {h: get_column_letter(i) for i, (h, *_) in enumerate(RESOURCE_COLUMNS, 1)}
    rng = lambda h: f'Resources!${col[h]}$2:${col[h]}'
    one_of = lambda names: '(' + '|'.join(re.sub(r'([.^$*+?()\[\]{}|\\])', r'\\\1', n) for n in names) + ')'
    out = one_of(model.OUTSIDE_MANUSCRIPT_SCOPE)
    ws.append(['Principle', 'FSR type', *ORIGIN_HEAD.values()])
    for c in ws[1]:
        c.font, c.fill = BOLD, HEAD
    for group, principles in model.PRINCIPLES.items():
        ws.append([group])
        ws.cell(row=ws.max_row, column=1).font = BOLD
        for p in principles:
            types = sorted(FSR_LABEL[t] for t, (all_, _) in model.enables().items() if p in all_)
            named = sorted(FSR_LABEL[t] for t, (_, own) in model.enables().items() if own == {p})   # its own type
            ws.append([p, ', '.join(named)] + [
                f'=SUMPRODUCT(({rng("Decision")}="include")*({rng("Origin")}="{origin}")'
                f'*REGEXMATCH({rng("FSR type")},"(^|[,;] *){one_of(types)}( *[,;]|$)")'
                f'*(REGEXMATCH({rng("Sub-domains")},"^{out}( *[,;] *{out})*$")=FALSE))' for origin in ORIGIN_HEAD])
            for c in ws[ws.max_row][2:]:
                c.fill = GREY
    ws.append([])
    ws.append([f'Grey, not read back: counted from the Resources tab. A resource counts under each principle that one '
               f'of its FSR types enables in the FIP ontology ({model.fip_ontology_version()}); resources whose '
               f'sub-domains are all {" or ".join(model.OUTSIDE_MANUSCRIPT_SCOPE)} are left out, as in the figure.'])
    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 42
    for letter in 'CDE':
        ws.column_dimensions[letter].width = 14
    ws.freeze_panes = 'A2'


def _sort_key(r):
    lanes = model.LANES + ['']
    return (r.get('decision') == 'exclude', lanes.index(model.lane(r)), r['name'].lower())


def build(doc, path, added=()):
    """Write the curation workbook for the dataset with FAIRsharing and the FIP declarations added (fairsharing.enrich,
    fip.enrich). added holds the keys of the rows that co-authors added in the sheet."""
    doc = model.normalise(copy.deepcopy(doc))
    _, warnings = model.check(doc)
    warn = {}
    for w in warnings:
        k, _, text = w.partition(': ')
        warn.setdefault(k, []).append(text)
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
    community = {r['declared-by']: r['key'] for r in doc['hasPart'] if r.get('declared-by')}   # FIC @id -> FIP key
    inventory = set(doc.get('sources', {}).get('inventory', {}).get('resources', []))   # a co-author's repository list
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
            if kind in GREY_KINDS or (kind == 'key' and r is not None):    # a new row's key is typed in
                c.fill = GREY
            if kind == 'date':
                c.number_format = '@'
            if kind == 'lane':                              # the earliest phase chosen in Phase
                s, k = f'{col_of["Origin"]}{n}', f'{col_of["Phase"]}{n}'
                first = ''.join(f'IF(ISNUMBER(FIND("{p}",{k})),"{p}",' for p in model.PHASES) + '""' + ')' * len(model.PHASES)
                c.value = (f'=IF({s}="Generic","Generic infrastructure",'
                           f'IF({s}="Life Sciences","Life sciences infrastructure",IF({s}="Toxicology",{first},"")))')
                continue
            if kind == 'fslink':
                f = f'{col_of["FAIRsharing record"]}{n}'
                c.value = (f'=IF({f}="","",HYPERLINK(IF(LEFT({f},12)="FAIRsharing.","https://doi.org/10.25504/"&{f},'
                           f'"https://fairsharing.org/"&{f}),"open"))')
                continue
            if r is None:
                continue
            fs = r.get('fairsharing') or {}
            if kind == 'creator':
                c.value = 'x' if field in r.get('creatorType', []) else None
            elif field in MULTI:                            # every value, joined as Sheets joins a multi-select
                c.value = ', '.join(FSR_LABEL.get(x, x) for x in r.get(field, [])) or None   # FSR types by label
            elif kind == 'etc':
                c.value = field in r.get('mentionedIn', [])
            elif head == 'Source':                          # where the resource is found, in a fixed order
                fips_of = set(declared.get(r['key'], {})) | ({community[r['@id']]} if r['@id'] in community else set())
                c.value = '; '.join((['Manuscript draft'] if r.get('manuscript', 'absent') != 'absent' else [])
                                    + ([site.COLLECTION] if fs.get('inCollection') else [])
                                    + sorted(site.label(by_key[k]) for k in fips_of)
                                    + (['Co-author repository inventory'] if r['key'] in inventory else
                                       ['Co-author addition'] if r['key'] in added else [])) or None
            elif head == 'Class':
                c.value = FSR_LABEL.get(r.get('fsrCategory'))
            elif head == 'Principles':
                c.value = ', '.join(r.get('principles', [])) or None
            elif head == 'Declared in':
                c.value = '; '.join(f'{site.label(by_key[k])} ({", ".join(sorted(q))})'
                                    for k, q in declared.get(r['key'], {}).items()) or None
            elif head == 'Builds on FAIR':
                c.value = 'yes' if r.get('buildsOnFair') else None
            elif kind == 'several':
                c.value = '; '.join(r.get(field, [])) or None
            elif kind == 'version':
                c.value = model.row_hash(r)
            elif field in ('datePublished', 'dateBasis'):   # the date and its basis, whichever field holds it
                c.value = model.first_date(r)[field == 'dateBasis'] or None
            elif head == 'Identifier':
                c.value = r.get('identifier')
            elif head == 'FIP identifiers':
                c.value = '; '.join(r.get('fsr', [])) or None
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
            elif kind == 'version' and not fixed:
                c.value = model.relation_hash(x)
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
            'fip': 'FIP declarations: the grey rows on the Relations tab, and Principles and Declared in.',
            'inventory': 'Repositories listed by a co-author, added as rows; the Source column names them.'}
    for name, s in doc.get('sources', {}).items():
        for title, v in ({f'{name} {k}': v for k, v in s.items()} if name == 'fip' else {name: s}).items():  # per FIP
            details = '; '.join(f'{k}: {", ".join(x) if isinstance(x, list) else x}' for k, x in v.items()) \
                if isinstance(v, dict) else str(v)
            src.append([title, details, used.get(name, '')])
    src.column_dimensions['A'].width = 16
    src.column_dimensions['B'].width = 100
    src.column_dimensions['C'].width = 70
    _principles(wb.create_sheet('Principles'))
    wb.save(path)
    return len(rows), len(rels)


# ---- reading a curated workbook back ---------------------------------------------------------------------------------

def _text(v):
    if v is None or v is False:                             # an unticked box is empty
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


def _owner(message):
    """What a check message names: (key, label, target) for a message about a relation, else a row's key."""
    key, _, rest = message.partition(': ')
    label, _, target = rest.partition(' ')
    if label in model.RELATIONS:
        return key, label, target.split(' ', 1)[0]
    return key.strip("'")


def ingest(doc, path, force=False, read_back=(), refused=None):
    """Read a curated workbook. Returns (new_doc, changes, problems, notes, reviewers). A row or relation with a problem
    waits, with the relations of a waiting row, and is listed in problems; the rest is read back. new_doc is None only
    when the workbook cannot be read, or when an error remains that no row or relation of the sheet causes. Problems
    are dicts with sheet, cell, column, value, problem; reviewers maps key -> Reviewed by, and a relation change
    carries its own Reviewed by as a fifth item. read_back holds the keys, and the (subject, label, target) of the
    relations, whose latest logged change came from reading this sheet back: their row or line version may be older
    than the dataset, which still equals what the sheet showed. refused maps what the check found an error or a new warning in (a key, or
    (subject, label, target) for a relation) to the check's message; the sheet is then read again without it."""
    refused = refused or {}
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
    seen, row_of, reviewer, waiting, twice = set(), {}, {}, set(), {}
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
            if not field or kind in ('key', 'creator', 'etc'):
                continue
            v = val.get(h)
            if kind == 'several':
                parsed[field] = [a.strip() for a in _text(v).split(';') if a.strip()]
            elif kind == 'date':
                parsed[field] = _text(v)
                if isinstance(v, (dt.datetime, dt.date)):
                    notes.append(f'Resources!{where[h]}: a date was converted by the spreadsheet; check its precision')
            elif field in MULTI:                            # every value chosen, in the order clicked
                chosen = [p.strip() for p in _text(v).split(',') if p.strip()]
                wrong = [p for p in chosen if p not in MULTI[field]]
                if wrong:
                    problem('Resources', where[h], h, v, f'{wrong[0]!r} is not one of the allowed values')
                    bad = True
                parsed[field] = [p for p in MULTI[field] if p in chosen]
                if field == 'span':                         # the earliest phase is the phase
                    parsed['phase'] = (parsed['span'] or [''])[0]
                elif field == 'fsrType':                    # FSR types, back to their IRIs
                    parsed[field] = [FSR_IRI[p] for p in parsed[field]]
            elif kind.startswith('list:'):
                t = _text(v)
                if kind == 'list:Exclusion reason':
                    t = t.split()[0] if t else ''
                if t and t not in LISTS[kind[5:]]:
                    problem('Resources', where[h], h, v, f'{t!r} is not one of the allowed values')
                    bad = True
                parsed[field] = t
            elif field in ('url', 'dateSource'):
                parsed[field] = _url(v)
            else:
                parsed[field] = _text(v)
        parsed['creatorType'] = [s for s in model.STAKEHOLDER if _text(val.get(CREATOR_HEAD[s])).lower() in MARKED]
        parsed['mentionedIn'] = [d for d in model.ETC_DOCUMENTS if _text(val.get(ETC_HEAD[d])).lower() in MARKED]
        for mark in [*CREATOR_HEAD.values(), *ETC_HEAD.values()]:
            t = _text(val.get(mark)).lower()
            if t and t not in MARKED:
                problem('Resources', where.get(mark, ''), mark, val.get(mark), 'mark with x or leave it empty')
                bad = True
        if parsed['reviewedBy'] and not parsed['reviewedBy'].isalpha():
            problem('Resources', where['Reviewed by'], 'Reviewed by', parsed['reviewedBy'], NOT_INITIALS)
            bad = True
        if not parsed['name']:
            problem('Resources', where['Name'], 'Name', '', 'every row needs a name')
            if key:
                waiting.add(key)
            continue
        if key and key in seen:                             # both lines wait
            problem('Resources', where['Key'], 'Key', key, 'this key appears twice')
            twice[key] = 'this key appears twice'
            continue
        if key and key not in rows:
            if version:
                problem('Resources', where['Key'], 'Key', key, 'unknown key: restore the original key or, for a new '
                        'resource copied from another line, empty its Row version (folded, last column)')
                continue
            if not model.KEY_RE.match(key):
                problem('Resources', where['Key'], 'Key', key, 'a new key may only use a-z, 0-9, _ and -')
                continue
        if not key:                                         # a row read back before is found again by its name
            key = next((k for k, r in rows.items() if k not in seen and r.get('name') == parsed['name']), '')
        if not key:
            key = model.slug((parsed['alternateName'] or [parsed['name']])[0], set(rows) | seen)
            notes.append(f'Resources row {n}: new resource {parsed["name"]!r} gets key {key!r}')
        seen.add(key)
        row_of[key] = n
        if bad or key in refused:
            waiting.add(key)
            continue
        old = rows.get(key)
        if old is None or not version:                      # a row added in the sheet keeps its defaults
            parsed['decision'] = parsed.get('decision') or (old or {}).get('decision') or 'undecided'
            parsed['manuscript'] = parsed.get('manuscript') or (old or {}).get('manuscript') or 'absent'
        if old is None:
            rows[key] = {'key': key, **parsed}
            new['hasPart'].append(rows[key])
        else:
            date, basis = model.first_date(old)                  # the sheet's form of the date
            seen_as = {**old, 'datePublished': date, 'dateBasis': basis}
            changed = any(model._text(seen_as.get(f)) != model._text(parsed.get(f)) for f in parsed)
            if changed and version != current.get(key) and key not in read_back and not force:
                problem('Resources', where['Key'], 'Key', key,
                        'this row changed in the dataset after the sheet was made; it waits until the sheet shows the '
                        'change')
                waiting.add(key)
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
    missing = [h for h, _, k, *_ in RELATION_COLUMNS if k not in GREY_KINDS and h not in head]
    if missing:
        problem('Relations', '1', ', '.join(missing), '', 'columns missing; do not rename or delete columns')
        return None, [], problems, notes, {}
    base = {(x['subject'], x['hadRole'], x['target']): x for x in model.relation_rows(doc)}
    shown = {model.relation_hash(x): t for t, x in base.items()}       # a line's version: the relation it showed
    on_sheet = {tuple(_text(c[head[h]].value) if head[h] < len(c) else '' for h in ('Resource', 'Relation', 'Target'))
                for c in ws.iter_rows(min_row=2)}
    lines = {}                                              # each relation's lines: (row, signed)
    for c in ws.iter_rows(min_row=2):
        t = tuple(_text(c[head[h]].value) if head[h] < len(c) else '' for h in ('Resource', 'Relation', 'Target'))
        if any(t) and t[1] not in model.FIP_PROPERTIES:
            lines.setdefault(t, []).append((c[0].row, bool(_text(c[head['Reviewed by']].value))))
    copies = {}                                             # of several lines, the one signed line decides
    for ls in lines.values():
        signed = [n for n, s in ls if s]
        if len(ls) > 1 and len(signed) == 1:
            copies.update({n: signed[0] for n, s in ls if not s})
    rel_row, rel_by, moved = {}, {}, set()
    for cells in ws.iter_rows(min_row=2):
        n = cells[0].row
        val = {h: cells[i].value for h, i in head.items() if i < len(cells)}
        subject, label, target = (_text(val.get(h)) for h in ('Resource', 'Relation', 'Target'))
        if not (subject or label or target) or label in model.FIP_PROPERTIES:   # FIP rows are read-only
            continue
        if n in copies:
            notes.append(f'Relations!A{n}: an unsigned copy of the signed line {copies[n]}, ignored')
            continue
        if (subject, label, target) in rel_row:                                 # both lines wait
            problem('Relations', f'A{n}', '', f'{subject} {label} {target}', 'this relation appears twice')
            twice[subject, label, target] = 'this relation appears twice'
            continue
        rel_row[subject, label, target] = n
        if subject in waiting or (subject, label, target) in refused:          # waits with its row, or for a fix
            continue
        bad, evidence, reviewed = False, _text(val.get('Evidence')), _text(val.get('Reviewed by'))
        for h, v, ok in (('Resource', subject, subject in by_key), ('Relation', label, label in model.RELATIONS),
                         ('Target', target, target in by_key and target != subject),
                         ('Evidence', evidence, evidence in ('', *model.EVIDENCE)),
                         ('Reviewed by', reviewed, not reviewed or reviewed.isalpha())):
            if not ok:
                col = get_column_letter(head.get(h, 0) + 1)
                problem('Relations', f'{col}{n}', h, v,
                        NOT_INITIALS if h == 'Reviewed by' else 'missing or not an allowed value')
                bad = True
        keep = _text(val.get('Keep')) or 'keep'
        if keep not in LISTS['Keep']:
            problem('Relations', f'{get_column_letter(head["Keep"] + 1)}{n}', 'Keep', keep, 'use keep or remove')
            bad = True
        if bad:
            continue
        triple, version, source, note = (subject, label, target), _text(val.get('Line version')), \
            _text(val.get('Source')), _text(val.get('Note'))
        was, old = shown.get(version), base.get(triple)
        if was and was != triple and was in on_sheet:          # an edited copy of a line still there: a new relation
            was = version = ''
        if version and not was and old is None and (triple in read_back or version != model.relation_hash(
                {'subject': subject, 'hadRole': label, 'target': target, 'evidence': evidence, 'source': source,
                 'reviewedBy': reviewed, 'note': note})):    # edited again: the relation its last read-back made
            last = [t for t in base if t[0] == subject and t in read_back and t not in on_sheet]
            was = last[0] if len(last) == 1 else None
        if keep == 'remove':
            edits = old is not None
        else:
            edits = old is None or (evidence or old['evidence'] or 'curator', source, reviewed, note) != (
                old['evidence'], old['source'], old['reviewedBy'], old['note'])
        if version and (not was or was != triple and old is not None) and edits and triple not in read_back \
                and not force:                                 # changed elsewhere, or named a relation added since
            if was:
                moved.add(was)
            problem('Relations', f'A{n}', '', ' '.join(triple), 'this relation changed in the dataset after the sheet '
                    'was made; it waits until the sheet shows the change (for a new relation copied from another '
                    'line, empty its Line version, last column)')
            continue
        if was and was != triple:                              # Resource, Relation or Target edited: it replaces
            if was[0] in waiting:
                continue
            moved.add(was)
            rel_by[was] = reviewed
            gone = by_key[was[0]].get('qualifiedRelation', [])
            gone[:] = [q for q in gone if (q['hadRole'], q['relation']) != (was[1], id_of[was[2]])]
        rel_by[triple] = reviewed
        rels = by_key[subject].setdefault('qualifiedRelation', [])
        existing = next((q for q in rels if q['relation'] == id_of[target] and q['hadRole'] == label), None)
        if keep == 'remove':
            if existing:
                rels.remove(existing)
            continue
        q = existing or {'relation': id_of[target], 'hadRole': label}
        q.update(evidence=evidence or q.get('evidence') or 'curator', source=source, reviewedBy=reviewed, note=note)
        if existing is None:
            rels.append(q)
    absent = sorted(set(base) - on_sheet - moved)
    if absent:
        notes.append(f'{len(absent)} relations are not in the sheet and were left unchanged: '
                     f'{", ".join(" ".join(t) for t in absent[:12])}{" ..." if len(absent) > 12 else ""}; '
                     'to drop one, keep its line and set Keep to remove')

    # Never worse than the dataset: a new error or warning holds back the row or relation it names; when holding back
    # the relation does not help, the row whose date or type moved.
    model.normalise(new)
    errors, warnings = model.check(new)
    before = set(model.check(doc)[1])
    was, now = ({r['key']: (model._year(r), r.get('fairsharingType'), r.get('fsrType')) for r in d['hasPart']}
                for d in (doc, new))
    blamed = dict(twice)
    for m in errors + [w for w in warnings if w not in before]:
        o = _owner(m)
        if isinstance(o, tuple) and o in refused:
            o = next((k for k in (o[0], o[2]) if k in was and was[k] != now.get(k)), o)
        if o in row_of or o in rel_row:
            blamed.setdefault(o, m)
    if blamed.keys() - refused.keys():
        return ingest(doc, path, force, read_back, {**blamed, **refused})
    if errors:                                              # one that no row or relation of the sheet causes
        for e in errors:
            problem('Resources', '', '', '', e)
        return None, [], problems, notes, {}
    for o, m in refused.items():
        if isinstance(o, tuple):
            problem('Relations', f'A{rel_row[o]}', '', ' '.join(o), m)
        else:
            problem('Resources', f'A{row_of[o]}', '', o, m)

    def credit(c):                                          # a relation change goes under its own Reviewed by
        if not c[1].startswith('relation'):
            return c
        return (*c, rel_by.get((c[0], *model.relation_of(*c[1:4])), ''))
    return new, [credit(c) for c in model.diff(doc, new)], problems, notes, reviewer
