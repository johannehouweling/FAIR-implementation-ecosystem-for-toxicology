"""The dataset of record: vocabularies, JSON-LD context, lane rule, load/save, validation and change log.

Every command reads and writes `data/fair-tox-ecosystem.jsonld` through this module, so every write is normalised,
validated and (for curated fields) logged in `data/changes.csv`. Paths are relative to the repository root, which is
where the commands are run.
"""
import copy
import csv
import datetime as dt
import functools
import hashlib
import json
import os
import re
import tempfile
import warnings

import rdflib

from fairtox import __version__

DATASET = 'data/fair-tox-ecosystem.jsonld'
CHANGES = 'data/changes.csv'
BASE = 'https://w3id.org/fair-tox/dataset'
TERMS = 'https://w3id.org/fair-tox/terms#'
FIP = 'https://w3id.org/fair/fip/terms/'
# The pinned FIP ontology https://w3id.org/fair/fip/terms/FIP-Ontology: its TriG download from Nanodash, 2026-10-08.
FIP_ONTOLOGY = 'data/raw/fip/fip-ontology.trig'
NANOPUB_RE = re.compile(r'^https?://(w3id|purl)\.org/np/')
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
    'Generic': 'Infrastructure not specific to a research domain, including FAIR resources such as the FIP.',
    'Life Sciences': 'Generic life-science infrastructure that toxicology uses.',
    'Toxicology': 'Made for toxicology, including toxicology instances of generic resources.',
}
# Who created a toxicology resource; several may apply. Information, plotted as an alternative lane layout.
STAKEHOLDER = {
    'Wet-lab research': 'Made by experimental (wet-lab) researchers, mostly academic.',
    'In silico research': 'Made by computational researchers: modellers, AOP, PBK, QSAR, informatics and data '
                          'stewards.',
    'Regulator': 'Made by a regulatory agency or intergovernmental body, such as OECD, EFSA, ECHA or US EPA.',
}
# The lifecycle phase of a toxicology resource: the phase it acts on; if several, the earliest at which it must be
# applied. Every phase it acts on is recorded as its span.
PHASES = {
    'Data generation': 'Planning, producing and depositing primary records: datasets, protocols, method descriptions '
                       'and the publications reporting them.',
    'Data integration': 'Integrating and synthesising those records into secondary resources and evidence: curated '
                        'databases, knowledge bases, ontologies, pathway networks and models.',
    'Regulatory assessment': 'Assessing records and secondary resources for reliability and relevance in a regulatory '
                             'context and integrating them into weight of evidence and decisions.',
}
LANE_DEF = {
    'Generic infrastructure': 'Resources not specific to a research domain.',
    'Life Sciences infrastructure': 'Generic life-science resources that toxicology uses.',
    'Data generation': 'Toxicology resources in the data generation phase.',
    'Data integration': 'Toxicology resources in the data integration phase.',
    'Regulatory assessment': 'Toxicology resources in the regulatory assessment phase.',
}
LANES = list(LANE_DEF)
TOX_LANES = LANES[2:]
LANE_OF_PHASE = dict(zip(PHASES, TOX_LANES))
# The alternative layout of the toxicology lanes: by creator type, with one lane for resources made jointly.
CREATOR_LANE_DEF = {
    'Made by wet-lab research': 'Toxicology resources made by wet-lab research only.',
    'Made by in silico research': 'Toxicology resources made by in silico research only.',
    'Made by regulators': 'Toxicology resources made by regulators only.',
    'Made jointly': 'Toxicology resources made by two or more creator types together.',
}
CREATOR_LANE_OF = dict(zip(STAKEHOLDER, CREATOR_LANE_DEF))
# Relation labels that make a toxicology resource count as building on FAIR when they point to a FAIR resource.
BUILDS_ON = ('implements', 'extends', 'profiles', 'recommends')
FAIR_PUBLISHED = 2016   # the FAIR guiding principles: only later resources can build on FAIR
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
SUBDOMAIN_LANE = {s: ('Data generation' if i < 4 else 'Data integration' if i < 7 else 'Regulatory assessment')
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
# FIP ontology properties, used as is: a FIP row is declared-by its community, and each FIP Declaration added to it
# when the site is built (dct:hasPart) declares-...-of a target. Not lineage and not enterable in FAIRsharing.
FIP_PROPERTIES = {
    'declares-current-use-of': 'The FIP declares that its community uses the target.',
    'declares-planned-use-of': 'The FIP declares that its community plans to use the target.',
    'declares-planned-development-of': 'The FIP declares that its community plans to develop the target.',
    'declares-planned-replacement-of': 'The FIP declares that its community plans to replace the target.',
    'declared-by': 'The FIP is declared by the target, a FAIR Implementation Community.',
}
EVIDENCE = {
    'manuscript': 'Stated in the manuscript.',
    'FAIRsharing': 'Asserted by FAIRsharing.',
    'literature': 'Stated in the literature or on the resource website.',
    'curator': 'Added by a curator.',
    'FIP': 'Declared in a FAIR Implementation Profile.',
}
# FSR types (fsrType): every class under FAIR Supporting Resource in the pinned FIP ontology (see fsr_types), or our
# own value Digital object for a resource that is not a FAIR Supporting Resource, such as a dataset or a model.
FSR, FER, FIC = FIP + 'FAIR-Supporting-Resource', FIP + 'FAIR-Enabling-Resource', FIP + 'FAIR-Implementation-Community'
DIGITAL_OBJECT = TERMS + 'DigitalObject'

VOCABULARIES = {
    'decision': DECISION, 'exclusionReason': EXCLUSION, 'type': {k: v[3] for k, v in TYPES.items()},
    'scope': SCOPE, 'phase': PHASES, 'stakeholders': STAKEHOLDER, 'lane': LANE_DEF, 'creatorLane': CREATOR_LANE_DEF,
    'subdomains': SUBDOMAINS, 'dateBasis': DATE_BASIS, 'maintained': MAINTAINED, 'manuscript': MANUSCRIPT,
    'fairsharingMatch': MATCH, 'hadRole': {k: v[2] for k, v in RELATIONS.items()}, 'declaration': FIP_PROPERTIES,
    'evidence': EVIDENCE,
}

# ---- JSON-LD shape ---------------------------------------------------------------------------------------------------

CONTEXT = {
    '@base': BASE, '@vocab': TERMS,
    'schema': 'https://schema.org/', 'dcat': 'http://www.w3.org/ns/dcat#', 'dct': 'http://purl.org/dc/terms/',
    'skos': 'http://www.w3.org/2004/02/skos/core#', 'pav': 'http://purl.org/pav/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'fip': FIP,
    'name': 'schema:name', 'alternateName': {'@id': 'schema:alternateName', '@container': '@set'},
    'description': 'schema:description', 'url': {'@id': 'schema:url', '@type': '@id'},
    'datePublished': 'schema:datePublished', 'creator': 'schema:creator', 'version': 'schema:version',
    'dateModified': 'schema:dateModified', 'license': {'@id': 'schema:license', '@type': '@id'},
    'creditText': 'schema:creditText', 'isBasedOn': {'@id': 'schema:isBasedOn', '@type': '@id'},
    'hasPart': {'@id': 'schema:hasPart', '@container': '@set'},
    'key': 'dct:identifier', 'type': 'dct:type', 'subdomains': {'@id': 'dct:subject', '@container': '@set'},
    'maintained': 'schema:creativeWorkStatus', 'reviewedBy': 'pav:curatedBy', 'note': 'skos:editorialNote',
    'source': 'dct:source', 'fsrType': {'@id': 'rdf:type', '@type': '@id', '@container': '@set'},
    'stakeholders': {'@container': '@set'}, 'span': {'@container': '@set'}, 'dateSource': {'@type': '@id'},
    'qualifiedRelation': {'@id': 'dcat:qualifiedRelation', '@container': '@set'},
    'relation': {'@id': 'dct:relation', '@type': '@id'}, 'hadRole': {'@id': 'dcat:hadRole', '@type': '@vocab'},
    'fipDeclaration': {'@id': 'dct:hasPart', '@container': '@set'},
    'question': {'@id': 'fip:refers-to-question', '@type': '@id'}, 'considerations': 'fip:considerations',
    **{p: {'@id': 'fip:' + p, '@type': '@id'} for p in FIP_PROPERTIES},
    'fsr': {'@id': 'skos:exactMatch', '@type': '@id', '@container': '@set'},
    # Kept in the file for people and the dashboard, but not part of the graph: derived fields, the sources and
    # vocabularies, and the published FAIRsharing block (sources are linked through isBasedOn, terms by their IRIs).
    **dict.fromkeys(['buildsOnFair', 'fsrCategory', 'fsrParent', 'declaredIn', 'principles', 'principle', 'sources',
                     'vocabularies', 'fairsharing']),
}
# Curated fields, in file order; edited in the Sheet. '@id', 'buildsOnFair', 'fsrCategory', 'fsrParent', 'declaredIn'
# and 'principles' are derived, 'fsr' (a declared resource's IRIs in the FIPs) is imported; 'declared-by' and
# 'fipDeclaration' exist only in the built site, 'fairsharing' only in the site, the sheet and the submission export.
CURATED = ['key', 'name', 'alternateName', 'decision', 'exclusionReason', 'coveredBy', 'type', 'fsrType', 'scope',
           'phase', 'span', 'stakeholders', 'subdomains', 'datePublished', 'dateBasis', 'dateSource', 'creator', 'url',
           'description', 'maintained', 'manuscript', 'manuscriptEvidence', 'fairsharingRecord', 'fairsharingMatch',
           'reviewedBy', 'note']
FIELD_ORDER = ['@id'] + CURATED + ['buildsOnFair', 'fsrCategory', 'fsrParent', 'declaredIn', 'principles', 'fsr',
                                   'qualifiedRelation', 'declared-by', 'fipDeclaration', 'fairsharing']
RELATION_ORDER = ['relation', 'hadRole', 'evidence', 'source', 'reviewedBy', 'note']
LIST_FIELDS = {'alternateName', 'subdomains', 'stakeholders', 'fsrType', 'span'}
KEY_RE = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
DATE_RE = re.compile(r'^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$')
FS_CODE_RE = re.compile(r'FAIRsharing\.[A-Za-z0-9]+')


def new_document(resources=()):
    return {
        '@context': CONTEXT, '@id': '', '@type': 'schema:Dataset',
        'name': 'FAIR implementation ecosystem for toxicology',
        'description': 'FAIR-enabling resources used in toxicology (standards, databases, policies and tools), curated '
                       'by the ELIXIR Toxicology Community together with the FAIRsharing Toxicology collection, with '
                       'first publication dates, FAIRsharing types, lifecycle phases, sub-domains and relations.',
        'version': __version__, 'dateModified': '', 'license': 'https://creativecommons.org/licenses/by-sa/4.0/',
        'creator': 'ELIXIR Toxicology Community', 'creditText': FAIRSHARING_CREDIT, 'isBasedOn': [COLLECTION_DOI],
        'sources': {}, 'vocabularies': VOCABULARIES, 'hasPart': list(resources),
    }


# ---- derived values --------------------------------------------------------------------------------------------------

def lane(r):
    """Dashboard lane by intended use (display only, never stored): generic and life-science resources have
    their own lanes; a toxicology resource sits in the lane of its phase."""
    if r.get('scope') == 'Generic':
        return 'Generic infrastructure'
    if r.get('scope') == 'Life Sciences':
        return 'Life Sciences infrastructure'
    return LANE_OF_PHASE.get(r.get('phase'), '')


def creator_lane(r):
    """Dashboard lane by creator: the toxicology lanes follow the creator types, 'Made jointly' for several."""
    if r.get('scope') != 'Toxicology':
        return lane(r)
    types = r.get('stakeholders') or []
    if len(types) > 1:
        return 'Made jointly'
    return CREATOR_LANE_OF.get(types[0], '') if types else ''


def registry(r):
    t = TYPES.get(r.get('type'))
    return t[0] if t else None


@functools.cache
def fsr_types():
    """Every class under FAIR Supporting Resource in the pinned FIP ontology: IRI -> (label, direct FSR subclass, FER).
    FAIR-Enabling Resource does not count as a direct FSR subclass here: an FER type keeps its other one, such as
    FAIR specification."""
    sub, fsr, fer = rdflib.RDFS.subClassOf, rdflib.URIRef(FSR), rdflib.URIRef(FER)
    out = {}
    with warnings.catch_warnings(action='ignore', category=DeprecationWarning):   # rdflib 7 warns about its own code
        g = rdflib.Dataset(default_union=True).parse(FIP_ONTOLOGY, format='trig')
        direct = set(g.subjects(sub, fsr)) - {fer}
        for c in set(g.transitive_subjects(sub, fsr)) - {fsr}:
            up = set(g.transitive_objects(c, sub)) - {c}
            out[str(c)] = (str(g.value(c, rdflib.RDFS.label)), str(next(iter(up & direct), c)), c == fer or fer in up)
    return out


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
    words = [w for w in re.split(r'[^a-z0-9]+', str(text).lower()) if w]
    base = ''
    for w in words:                                   # whole words only, at most 32 characters
        if base and len(base) + 1 + len(w) > 32:
            break
        base = f'{base}_{w}' if base else w[:32]
    base = base or 'resource'
    key, n = base, 2
    while key in taken:
        key, n = f'{base}_{n}', n + 1
    return key


def iri_of(r):
    if FIC in r.get('fsrType', []) and NANOPUB_RE.match(r.get('@id') or ''):
        return r['@id']                                     # a FIC is identified by its FIC nanopublication
    code = fs_ref(r.get('fairsharingRecord'))
    if r.get('fairsharingMatch') == 'confirmed' and code.startswith('FAIRsharing.'):
        return 'https://doi.org/10.25504/' + code
    return '#' + r['key']


def normalise(doc):
    """Derive @id, buildsOnFair and the FSR and FIP fields, order fields, sort resources and relations, keep relation
    targets in step with @ids."""
    old_ids = {r.get('@id'): r['key'] for r in doc['hasPart']}
    for r in doc['hasPart']:
        for f in CURATED:                                   # no stray spaces in curated text
            if isinstance(r.get(f), str):
                r[f] = r[f].strip()
            elif isinstance(r.get(f), list):
                r[f] = [x.strip() if isinstance(x, str) else x for x in r[f]]
        for f, vocab in (('subdomains', SUBDOMAINS), ('stakeholders', STAKEHOLDER), ('span', PHASES)):
            if r.get(f):                                    # one canonical order, so round trips are exact
                known = [x for x in vocab if x in r[f]]
                r[f] = known + [x for x in r[f] if x not in vocab]
        if r.get('fairsharingRecord'):
            r['fairsharingRecord'] = fs_ref(r['fairsharingRecord'])
        r['@id'] = iri_of(r)
    new_ids = {r['key']: r['@id'] for r in doc['hasPart']}
    target = lambda v: new_ids.get(old_ids.get(v, v.lstrip('#')), v)
    declared = {}                                           # target @id -> [(FIP @id, principle)]
    for r in doc['hasPart']:
        for q in r.get('qualifiedRelation', []):
            q['relation'] = target(q['relation'])
        for d in r.get('fipDeclaration', []):
            for p in FIP_PROPERTIES.keys() & d.keys():
                declared.setdefault(d[p], []).append((r['@id'], d.get('principle')))
    by_id = {r['@id']: r for r in doc['hasPart']}
    for r in doc['hasPart']:                                # derived: a toxicology resource building on FAIR
        fair = r.get('scope') == 'Toxicology' and (_year(r) or 0) >= FAIR_PUBLISHED and any(
            q.get('hadRole') in BUILDS_ON and (by_id.get(q['relation']) or {}).get('scope') == 'Generic'
            for q in r.get('qualifiedRelation', []))
        if fair:
            r['buildsOnFair'] = True
        else:
            r.pop('buildsOnFair', None)
        types = [fsr_types()[t] for t in r.get('fsrType', []) if t in fsr_types()]
        r['fsrParent'] = types[0][1] if types else ''
        if types:                                           # an FER when either type is one
            r['fsrCategory'] = FER if any(t[2] for t in types) else FSR
        else:
            r['fsrCategory'] = DIGITAL_OBJECT if r.get('fsrType') == [DIGITAL_OBJECT] else ''
        r['declaredIn'] = sorted({fip for fip, _ in declared.get(r['@id'], [])})
        r['principles'] = sorted({p for _, p in declared.get(r['@id'], []) if p})
    doc['hasPart'] = sorted((_ordered(r) for r in doc['hasPart']), key=lambda r: r['key'])
    doc['@context'] = CONTEXT
    doc['vocabularies'] = VOCABULARIES
    doc['version'] = __version__
    doc['description'] = new_document()['description']
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
        for field, vocab in (('decision', DECISION), ('type', TYPES), ('scope', SCOPE), ('phase', PHASES),
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
        if r.get('decision') != 'exclude' and FIC not in r.get('fsrType', []):   # excluded rows and communities
            if (r.get('scope') == 'Toxicology') != bool(r.get('phase')):            # are not plotted
                e(f'{k}: a phase is required exactly when the scope is Toxicology')
            if (r.get('scope') == 'Toxicology') != bool(r.get('stakeholders')):
                e(f'{k}: at least one creator type is required exactly when the scope is Toxicology')
        for s in r.get('stakeholders', []) if isinstance(r.get('stakeholders'), list) else []:
            if s not in STAKEHOLDER:
                e(f'{k}: creator type {s!r} is not an allowed value')
        for s in r.get('subdomains', []):
            if s not in SUBDOMAINS:
                e(f'{k}: sub-domain {s!r} is not an allowed value')
        span = r.get('span') or []
        for s in span:
            if s not in PHASES:
                e(f'{k}: span {s!r} is not a phase')
        if (span or r.get('phase')) and next((p for p in PHASES if p in span), None) != r.get('phase'):
            e(f'{k}: the span must contain the phase as its earliest phase')
        types = r.get('fsrType') or []
        parents = {fsr_types()[t][1] for t in types if t in fsr_types()}
        for t in types:
            if t not in fsr_types() and t != DIGITAL_OBJECT:
                e(f'{k}: FSR type {t!r} is not an allowed value')
        if len(types) > 2 or (DIGITAL_OBJECT in types and len(types) > 1):
            e(f'{k}: at most two FSR types, or Digital object alone')
        elif len(parents) > 1:
            e(f'{k}: a second FSR type must share the direct FSR subclass of the first')
        if FIC in parents and not NANOPUB_RE.match(r.get('@id') or ''):
            e(f'{k}: FAIR Implementation Community needs its FIC nanopublication as @id')
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
            missing = [f for f in ('datePublished', 'dateSource', 'url', 'type', 'fsrType', 'scope') if not r.get(f)]
            if r.get('fairsharingMatch') != 'confirmed' and not r.get('description'):
                missing.append('description')
            if missing:
                warnings.append(f'{k}: included but missing {", ".join(missing)}')
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
    """The document without dateModified, to decide whether a save changes anything."""
    d = copy.deepcopy(doc)
    d.pop('dateModified', None)
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
