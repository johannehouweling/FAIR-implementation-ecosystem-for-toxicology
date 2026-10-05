"""The dataset of record: vocabularies, JSON-LD context, lane rule, load/save, validation and change log.

Every command reads and writes `data/fair-tox-ecosystem.jsonld` through this module, so every write is normalised,
validated and (for curated fields) logged in `data/changes.csv`. Paths are relative to the repository root, which is
where the commands are run.
"""
import copy
import csv
import datetime as dt
import hashlib
import json
import os
import re
import tempfile

from fairtox import __version__

DATASET = 'data/fair-tox-ecosystem.jsonld'
CHANGES = 'data/changes.csv'
BASE = 'https://w3id.org/fair-tox/dataset'
TERMS = 'https://w3id.org/fair-tox/terms#'
COLLECTION_ID = 3496
COLLECTION_DOI = 'https://doi.org/10.25504/FAIRsharing.f60a10'
FAIRSHARING_CREDIT = ('Contains information from FAIRsharing (https://fairsharing.org), licensed CC BY-SA 4.0 '
                      '(https://creativecommons.org/licenses/by-sa/4.0/).')

# ---- controlled vocabularies: value -> definition ------------------------------------------------------------------

DECISION = {
    'include': 'Meets all inclusion criteria (I1-I5 in docs/inclusion-criteria.md).',
    'exclude': 'Fails a criterion; the exclusion reason says which.',
    'undecided': 'Not yet screened, or left for the co-authors to decide.',
}
EXCLUSION = {
    'E1': 'Organisation, project, initiative, consortium, community or event; its named product is listed instead.',
    'E2': 'Principle, framework or concept without a reusable artefact, or a publication only.',
    'E3': 'Unnamed or not identifiable (no homepage or DOI).',
    'E4': 'Never publicly available.',
    'E5': 'No documented toxicology use.',
    'E6': 'Duplicate, version or component of another row (see Covered by).',
    'E7': 'Outside chemical toxicology, such as toxinology or clinical adverse-event grading.',
    'E8': 'Test method or guideline that standardises an experiment rather than data or metadata.',
}
# FAIRsharing registry and record type (id) behind each type label; Tool is ours, FAIRsharing registers no software.
TYPES = {
    'Standard: model/format': ('Standard', 'model_and_format', 4, 'Data or metadata model, schema, exchange format.'),
    'Standard: terminology artefact': ('Standard', 'terminology_artefact', 6,
                                       'Ontology, controlled vocabulary, thesaurus or glossary.'),
    'Standard: reporting guideline': ('Standard', 'reporting_guideline', 7,
                                      'Minimum information checklist or reporting template.'),
    'Standard: identifier schema': ('Standard', 'identifier_schema', 8, 'Identifier scheme or resolver.'),
    'Standard: principle': ('Standard', 'principle', 17, 'Published set of principles with a reusable artefact.'),
    'Database: repository': ('Database', 'repository', 1, 'Archive that accepts data deposits.'),
    'Database: knowledgebase': ('Database', 'knowledgebase', 2, 'Curated knowledge resource or data portal.'),
    'Database: knowledgebase and repository': ('Database', 'knowledgebase_and_repository', 3,
                                               'Both a curated knowledge resource and an archive.'),
    'Policy: journal': ('Policy', 'journal', 9, 'Data policy of a journal.'),
    'Policy: journal publisher': ('Policy', 'journal_publisher', 10, 'Data policy of a publisher.'),
    'Policy: society': ('Policy', 'society', 11, 'Policy or guidance of a learned society.'),
    'Policy: funder': ('Policy', 'funder', 12, 'Data policy of a funder.'),
    'Policy: project': ('Policy', 'project', 13, 'Policy or guidance issued by a project.'),
    'Policy: institution': ('Policy', 'institution', 14,
                            'Policy or guidance issued by an institution or agency, such as OECD guidance.'),
    'Collection': ('Collection', 'collection', 15, 'Curated collection of FAIR-enabling resources.'),
    'Tool': ('Tool', None, None, 'Software or service; FAIRsharing does not register these.'),
}
SCOPE = {
    'FAIR': 'Generic FAIR infrastructure, not specific to a research domain.',
    'Life Sciences': 'Generic life-science infrastructure that toxicology uses.',
    'Toxicology': 'Made for toxicology.',
    'Toxicology building on FAIR': 'A toxicology-specific instance of a FAIR resource, such as a toxicology FAIR '
                                   'Implementation Profile or the RDMkit toxicology page.',
}
STAKEHOLDER = {
    'Wet-lab research': 'Made by experimental (wet-lab) researchers, mostly academic.',
    'In silico research': 'Made by computational researchers: modellers, AOP, PBK, QSAR and nano-informatics.',
    'Regulator': 'Made by a regulatory agency or intergovernmental body, such as OECD, EFSA, ECHA or US EPA.',
}
PHASE_OF = {'Wet-lab research': 'Data Generation', 'In silico research': 'Data Integration',
            'Regulator': 'Application (Regulatory Use)'}
PHASES = {
    'Data Generation': 'Toxicology lifecycle phase of resources made by wet-lab research.',
    'Data Integration': 'Toxicology lifecycle phase of resources made by in silico research.',
    'Application (Regulatory Use)': 'Toxicology lifecycle phase of resources made by regulators.',
}
LANE_DEF = {
    'FAIR infrastructure': 'Generic FAIR resources, and toxicology resources that build on them.',
    'Life Sciences infrastructure': 'Generic life-science resources that toxicology uses.',
    'Data Generation': 'Toxicology infrastructure made by wet-lab research.',
    'Tools & Integration': 'Toxicology infrastructure made by in silico research.',
    'Application (regulatory)': 'Toxicology infrastructure made by regulators.',
}
LANES = list(LANE_DEF)
TOX_LANES = LANES[2:]
LANE_OF_PHASE = dict(zip(PHASES, TOX_LANES))
SUBDOMAINS = {
    'in vitro toxicology': 'Data generation (manuscript Figure 2 caption and section III).',
    'nanotoxicology': 'Data generation.',
    'exposome': 'Data generation.',
    'eco-toxicology': 'Data generation.',
    'toxicogenomics': 'Integration and tools.',
    'AOP-based mechanistic knowledge': 'Integration and tools.',
    'computational and predictive toxicology': 'Integration and tools.',
    'regulatory toxicology': 'Application.',
}
# The lane each sub-domain belongs to in the manuscript (Figure 2 caption): used to group the dashboard filters.
SUBDOMAIN_LANE = {s: ('Data Generation' if i < 4 else 'Tools & Integration' if i < 7 else 'Application (regulatory)')
                  for i, s in enumerate(SUBDOMAINS)}
DATE_BASIS = {
    'publication': 'Online publication of the paper that first describes the resource.',
    'release': 'First public release or launch.',
    'adoption': 'Official adoption or publication of guidance or policy.',
    'FAIRsharing year': "FAIRsharing's year of creation, used only when nothing better was found.",
}
MAINTAINED = {
    'active': 'Maintained and available.',
    'discontinued': 'No longer maintained or available (shown with a dagger).',
    'in development': 'Not yet released in a stable form.',
    'unknown': 'Status could not be established.',
}
MANUSCRIPT = {
    'cited': 'Named in the manuscript text with a reference.',
    'named': 'Named in the manuscript text without a reference.',
    'comment only': 'Named only in a comment or to-do note of the manuscript.',
    'absent': 'Not in the manuscript.',
}
MATCH = {
    'confirmed': 'The FAIRsharing record is this resource.',
    'to check': 'A FAIRsharing record was proposed and needs a curator.',
    'no record': 'FAIRsharing has no record for this resource.',
}
# The FAIRsharing record-association labels used here (id, lineage, definition). Read "subject label target".
RELATIONS = {
    'implements': (1, True, 'The database implements the standard.'),
    'extends': (8, True, 'The subject builds on and extends the target.'),
    'profiles': (7, True, 'The standard is a profile of the target standard.'),
    'recommends': (11, True, 'The policy recommends the target.'),
    'deprecates': (9, True, 'The subject replaces the target.'),
    'related_to': (4, False, 'The resources are related without one building on the other.'),
}
# Registry pairs FAIRsharing allows per label (GET https://api.fairsharing.org/record_associations/allowed, 5 Oct 2026).
ALLOWED = {
    'implements': {('Database', 'Standard')},
    'extends': {('Database', 'Database'), ('Standard', 'Standard'), ('Policy', 'Policy')},
    'profiles': {('Standard', 'Standard')},
    'recommends': {('Policy', 'Database'), ('Policy', 'Standard'), ('Policy', 'Collection')},
    'deprecates': {('Database', 'Database'), ('Standard', 'Standard'), ('Policy', 'Policy'),
                   ('Collection', 'Collection')},
    'related_to': {('Database', 'Database'), ('Database', 'Standard'), ('Standard', 'Standard'),
                   ('Standard', 'Database'), ('Policy', 'Policy')},
}
EVIDENCE = {
    'manuscript': 'Stated in the manuscript.',
    'FAIRsharing': 'Asserted by FAIRsharing.',
    'literature': 'Stated in the literature or on the resource website.',
    'curator': 'Added by a curator.',
}

VOCABULARIES = {
    'decision': DECISION, 'exclusionReason': EXCLUSION, 'type': {k: v[3] for k, v in TYPES.items()},
    'scope': SCOPE, 'stakeholder': STAKEHOLDER, 'phase': PHASES, 'lane': LANE_DEF,
    'subdomains': SUBDOMAINS, 'dateBasis': DATE_BASIS, 'maintained': MAINTAINED, 'manuscript': MANUSCRIPT,
    'fairsharingMatch': MATCH, 'hadRole': {k: v[2] for k, v in RELATIONS.items()}, 'evidence': EVIDENCE,
}

# ---- JSON-LD shape ---------------------------------------------------------------------------------------------------

CONTEXT = {
    '@base': BASE, '@vocab': TERMS,
    'schema': 'https://schema.org/', 'dcat': 'http://www.w3.org/ns/dcat#', 'dct': 'http://purl.org/dc/terms/',
    'name': 'schema:name', 'alternateName': {'@id': 'schema:alternateName', '@container': '@set'},
    'description': 'schema:description', 'url': {'@id': 'schema:url', '@type': '@id'},
    'datePublished': 'schema:datePublished', 'creator': 'schema:creator', 'version': 'schema:version',
    'dateModified': 'schema:dateModified', 'license': {'@id': 'schema:license', '@type': '@id'},
    'creditText': 'schema:creditText', 'isBasedOn': {'@id': 'schema:isBasedOn', '@type': '@id'},
    'hasPart': {'@id': 'schema:hasPart', '@container': '@set'},
    'subdomains': {'@container': '@set'}, 'dateSource': {'@type': '@id'},
    'qualifiedRelation': {'@id': 'dcat:qualifiedRelation', '@container': '@set'},
    'relation': {'@id': 'dct:relation', '@type': '@id'}, 'hadRole': {'@id': 'dcat:hadRole', '@type': '@vocab'},
    'sources': {'@type': '@json'}, 'vocabularies': {'@type': '@json'}, 'fairsharing': {'@type': '@json'},
}
# Curated fields, in file order; edited in the Sheet. '@id' and 'phase' are derived, 'fairsharing' is fetched.
CURATED = ['key', 'name', 'alternateName', 'decision', 'exclusionReason', 'coveredBy', 'type', 'scope', 'stakeholder',
           'subdomains', 'datePublished', 'dateBasis', 'dateSource', 'creator', 'url', 'description', 'maintained',
           'manuscript', 'manuscriptEvidence', 'fairsharingRecord', 'fairsharingMatch', 'reviewedBy', 'note']
FIELD_ORDER = ['@id'] + CURATED[:9] + ['phase'] + CURATED[9:] + ['qualifiedRelation', 'fairsharing']
RELATION_ORDER = ['relation', 'hadRole', 'evidence', 'source', 'reviewedBy', 'note']
LIST_FIELDS = {'alternateName', 'subdomains'}
KEY_RE = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
DATE_RE = re.compile(r'^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$')
FS_CODE_RE = re.compile(r'FAIRsharing\.[A-Za-z0-9]+')


def new_document(resources=()):
    return {
        '@context': CONTEXT, '@id': '', '@type': 'schema:Dataset',
        'name': 'FAIR implementation ecosystem for toxicology',
        'description': 'FAIR-enabling resources used in toxicology: from the ELIXIR Toxicology Community paper on ten '
                       'years of FAIR in toxicology and from the FAIRsharing Toxicology collection, with first '
                       'publication dates, FAIRsharing types, lifecycle phases, sub-domains and relations.',
        'version': __version__, 'dateModified': '', 'license': 'https://creativecommons.org/licenses/by-sa/4.0/',
        'creator': 'ELIXIR Toxicology Community', 'creditText': FAIRSHARING_CREDIT, 'isBasedOn': [COLLECTION_DOI],
        'sources': {}, 'vocabularies': VOCABULARIES, 'hasPart': list(resources),
    }


# ---- derived values --------------------------------------------------------------------------------------------------

def lane(r):
    """Dashboard lane of a resource: where it comes from (display only, never stored)."""
    if r.get('scope') in ('FAIR', 'Toxicology building on FAIR'):
        return 'FAIR infrastructure'
    if r.get('scope') == 'Life Sciences':
        return 'Life Sciences infrastructure'
    return LANE_OF_PHASE.get(PHASE_OF.get(r.get('stakeholder')), '')


def registry(r):
    t = TYPES.get(r.get('type'))
    return t[0] if t else None


def fs_ref(value):
    """Normalise a FAIRsharing reference (DOI, URL, code or numeric id) to 'FAIRsharing.xxx' or a numeric string."""
    value = str(value or '').strip()
    m = FS_CODE_RE.search(value)
    if m:
        return m.group(0)
    m = re.fullmatch(r'(?:https?://(?:www\.)?fairsharing\.org/(?:fairsharing_records/)?)?(\d+)/?', value)
    return m.group(1) if m else value


def slug(text, taken=()):
    """A new key from a name or abbreviation, unique among `taken`."""
    base = re.sub(r'[^a-z0-9]+', '_', str(text).lower()).strip('_')[:30].strip('_') or 'resource'
    key, n = base, 2
    while key in taken:
        key, n = f'{base}_{n}', n + 1
    return key


def iri_of(r):
    code = fs_ref(r.get('fairsharingRecord'))
    if r.get('fairsharingMatch') == 'confirmed':
        if code.startswith('FAIRsharing.'):
            return 'https://doi.org/10.25504/' + code
        doi = (r.get('fairsharing') or {}).get('doi')
        if doi:
            return 'https://doi.org/' + doi
    return '#' + r['key']


def normalise(doc):
    """Derive @id and phase, order fields, sort resources and relations, keep relation targets in step with @ids."""
    old_ids = {r.get('@id'): r['key'] for r in doc['hasPart']}
    for r in doc['hasPart']:
        if r.get('fairsharingRecord'):
            r['fairsharingRecord'] = fs_ref(r['fairsharingRecord'])
        r['@id'] = iri_of(r)
        if r.get('scope') == 'Toxicology' and r.get('stakeholder') in PHASE_OF:
            r['phase'] = PHASE_OF[r['stakeholder']]
        else:
            r.pop('phase', None)
    new_ids = {r['key']: r['@id'] for r in doc['hasPart']}
    for r in doc['hasPart']:
        for q in r.get('qualifiedRelation', []):
            key = old_ids.get(q['relation'], q['relation'].lstrip('#'))
            q['relation'] = new_ids.get(key, q['relation'])
    doc['hasPart'] = sorted((_ordered(r) for r in doc['hasPart']), key=lambda r: r['key'])
    doc['vocabularies'] = VOCABULARIES
    doc['version'] = __version__
    return doc


def _ordered(r):
    out = {k: r[k] for k in FIELD_ORDER if r.get(k) not in (None, '', [], {})}
    out.update({k: v for k, v in r.items() if k not in out and v not in (None, '', [], {})})
    if 'qualifiedRelation' in out:
        rels = [{k: q[k] for k in RELATION_ORDER if q.get(k) not in (None, '')} for q in out['qualifiedRelation']]
        out['qualifiedRelation'] = sorted(rels, key=lambda q: (q['relation'], q['hadRole']))
    return out


# ---- validation ------------------------------------------------------------------------------------------------------

def check(doc):
    """Return (errors, warnings). Errors block a save; warnings fail only `fairtox validate --strict`."""
    errors, warnings = [], []
    rs = doc.get('hasPart', [])
    keys = [r.get('key') for r in rs]
    by_key = {r.get('key'): r for r in rs}
    by_id = {r.get('@id'): r for r in rs}
    for k in {k for k in keys if keys.count(k) > 1}:
        errors.append(f'{k}: duplicate key')
    today = dt.date.today()
    for r in rs:
        k = r.get('key')
        e = errors.append
        if not isinstance(k, str) or not KEY_RE.match(k):
            e(f'{k!r}: key must be lowercase letters, digits, _ or -')
            continue
        if not r.get('name'):
            e(f'{k}: name is empty')
        for field, vocab in (('decision', DECISION), ('type', TYPES), ('scope', SCOPE), ('stakeholder', STAKEHOLDER),
                             ('dateBasis', DATE_BASIS), ('maintained', MAINTAINED), ('manuscript', MANUSCRIPT),
                             ('fairsharingMatch', MATCH), ('exclusionReason', EXCLUSION)):
            if r.get(field) not in (None, '') and r[field] not in vocab:
                e(f'{k}: {field} {r[field]!r} is not an allowed value')
        if r.get('decision') not in DECISION:
            e(f'{k}: decision is required')
        if (r.get('decision') == 'exclude') != bool(r.get('exclusionReason')):
            e(f'{k}: an exclusion reason is required exactly when the decision is exclude')
        if r.get('exclusionReason') == 'E6' and r.get('coveredBy') not in by_key:
            e(f'{k}: exclusion reason E6 needs Covered by naming another row')
        if r.get('coveredBy') and (r['coveredBy'] not in by_key or r['coveredBy'] == k):
            e(f'{k}: covered by {r["coveredBy"]!r} is not another row')
        if (r.get('scope') == 'Toxicology') != bool(r.get('stakeholder')):
            e(f'{k}: a stakeholder is required exactly when the scope is Toxicology')
        for s in r.get('subdomains', []):
            if s not in SUBDOMAINS:
                e(f'{k}: sub-domain {s!r} is not an allowed value')
        for field in LIST_FIELDS:
            if not isinstance(r.get(field, []), list):
                e(f'{k}: {field} must be a list')
        d = r.get('datePublished')
        if d:
            m = DATE_RE.match(str(d))
            try:
                ok = bool(m) and 1900 <= int(m.group(1)) <= today.year and \
                    dt.date(int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1)) <= today
            except ValueError:
                ok = False
            if not ok:
                e(f'{k}: first published {d!r} must be YYYY, YYYY-MM or YYYY-MM-DD and not in the future')
        for field in ('url', 'dateSource'):
            if r.get(field) and not re.match(r'^https?://\S+$', r[field]):
                e(f'{k}: {field} {r[field]!r} must be an http(s) URL')
        seen = set()
        for q in r.get('qualifiedRelation', []):
            t = by_id.get(q.get('relation'))
            role = q.get('hadRole')
            if t is None:
                e(f'{k}: relation target {q.get("relation")!r} is not in the dataset')
                continue
            if t is r:
                e(f'{k}: relation to itself')
            if role not in RELATIONS:
                e(f'{k}: relation {role!r} is not an allowed label')
            if q.get('evidence') not in EVIDENCE:
                e(f'{k}: relation evidence {q.get("evidence")!r} is not an allowed value')
            if (t['key'], role) in seen:
                e(f'{k}: duplicate relation {role} {t["key"]}')
            seen.add((t['key'], role))
            if role in RELATIONS and RELATIONS[role][1] and q.get('evidence') != 'FAIRsharing' and \
                    _year(r) and _year(t) and _year(r) < _year(t):
                warnings.append(f'{k}: {role} {t["key"]} points to a resource first published later')
            if role in ALLOWED and (registry(r), registry(t)) not in ALLOWED[role]:
                warnings.append(f'{k}: {role} {t["key"]} cannot be entered in FAIRsharing '
                                f'({registry(r)} to {registry(t)})')
        if r.get('decision') == 'include':
            missing = [f for f in ('datePublished', 'dateSource', 'url', 'type', 'scope') if not r.get(f)]
            if r.get('fairsharingMatch') != 'confirmed' and not r.get('description'):
                missing.append('description')
            if missing:
                warnings.append(f'{k}: included but missing {", ".join(missing)}')
        fy = (r.get('fairsharing') or {}).get('yearCreation')
        if isinstance(fy, int) and _year(r) and abs(fy - _year(r)) > 1:
            warnings.append(f'{k}: first published {_year(r)}, FAIRsharing year of creation {fy}')
        if r.get('fairsharingMatch') == 'to check':
            warnings.append(f'{k}: FAIRsharing match still to check')
    return errors, warnings


def _year(r):
    m = DATE_RE.match(str(r.get('datePublished') or ''))
    return int(m.group(1)) if m else None


# ---- load, save, change log ------------------------------------------------------------------------------------------

def load(path=DATASET):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def dumps(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + '\n'


def _stable(doc):
    """The document without the fields that change on every run, to decide whether a save changes anything."""
    d = copy.deepcopy(doc)
    d.pop('dateModified', None)
    for s in d.get('sources', {}).values():
        if isinstance(s, dict):
            s.pop('retrieved', None)
    for r in d.get('hasPart', []):
        (r.get('fairsharing') or {}).pop('retrieved', None)
    return d


def save(doc, path=DATASET):
    """Normalise, validate and write atomically. Returns False when nothing but timestamps would change."""
    doc = normalise(doc)
    errors, _ = check(doc)
    if errors:
        raise ValueError('dataset not saved:\n  ' + '\n  '.join(errors))
    if os.path.exists(path) and _stable(load(path)) == _stable(doc):
        return False
    doc['dateModified'] = dt.date.today().isoformat()
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(dumps(doc))
    os.replace(tmp, path)
    return True


def row_hash(r):
    """Short fingerprint of a resource's curated fields. The Sheet carries it per row, so ingest can refuse an edit
    to a row that changed in the dataset after the Sheet was built, while rows nobody touched merge cleanly."""
    return hashlib.sha256(json.dumps([r.get(k) for k in CURATED], sort_keys=True).encode()).hexdigest()[:10]


def relation_rows(doc):
    """Relations as flat rows: subject key, label, target key, evidence, source, reviewedBy, note."""
    key_of = {r['@id']: r['key'] for r in doc['hasPart']}
    return [{'subject': r['key'], 'hadRole': q['hadRole'], 'target': key_of.get(q['relation'], q['relation']),
             'evidence': q.get('evidence', ''), 'source': q.get('source', ''), 'reviewedBy': q.get('reviewedBy', ''),
             'note': q.get('note', '')}
            for r in doc['hasPart'] for q in r.get('qualifiedRelation', [])]


def diff(old, new):
    """Field-level differences in curated fields and relations: (key, field, old, new)."""
    out = []
    a = {r['key']: r for r in old['hasPart']}
    b = {r['key']: r for r in new['hasPart']}
    for k in sorted(a.keys() - b.keys()):
        out.append((k, '(row)', a[k].get('name', ''), '(removed)'))
    for k in sorted(b.keys() - a.keys()):
        out.append((k, '(row)', '(new)', b[k].get('name', '')))
    for k in sorted(a.keys() & b.keys()):
        for f in CURATED[1:]:
            x, y = _text(a[k].get(f)), _text(b[k].get(f))
            if x != y:
                out.append((k, f, x, y))
    ra = {(x['subject'], x['hadRole'], x['target']): x for x in relation_rows(old)}
    rb = {(x['subject'], x['hadRole'], x['target']): x for x in relation_rows(new)}
    for t in sorted(ra.keys() - rb.keys()):
        out.append((t[0], 'relation', f'{t[1]} {t[2]}', '(removed)'))
    for t in sorted(rb.keys() - ra.keys()):
        out.append((t[0], 'relation', '(new)', f'{t[1]} {t[2]}'))
    for t in sorted(ra.keys() & rb.keys()):
        for f in ('evidence', 'source', 'reviewedBy', 'note'):
            if ra[t][f] != rb[t][f]:
                out.append((t[0], f'relation {t[1]} {t[2]} {f}', ra[t][f], rb[t][f]))
    return out


def _text(v):
    return '; '.join(v) if isinstance(v, list) else ('' if v is None else str(v))


def log_changes(changes, round_name, source, by=None, path=CHANGES):
    """Append (key, field, old, new) rows to the change log; `by` maps key -> curator initials."""
    if not changes:
        return
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    today = dt.date.today().isoformat()
    with open(path, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['date', 'round', 'key', 'field', 'old', 'new', 'by', 'source'])
        for key, field, old, new_value in changes:
            w.writerow([today, round_name, key, field, old, new_value, (by or {}).get(key, ''), source])
