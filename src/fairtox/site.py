"""Build the static dashboard: index.html with the data embedded, plus the dataset and CSV downloads, and the
vocabulary (terms.ttl, terms.jsonld) and JSON-LD context (context.jsonld) that the dataset's own IRIs resolve to.

The build, deployed to GitHub Pages, holds the included resources only, without curation fields.
"""
import copy
import csv
import hashlib
import io
import json
import re
from importlib.resources import files
from pathlib import Path

from fairtox import fip, model

REPO = 'https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology'          # private
# CI deploys the public build to this public repository, which serves it on GitHub Pages
PUBLIC_REPO = 'https://github.com/johannehouweling/FAIR-implementation-ecosystem-toxicology-timeline'
PAGES = 'https://johannehouweling.github.io/FAIR-implementation-ecosystem-toxicology-timeline/'
CRITERIA = REPO + '/blob/main/docs/inclusion-criteria.md'
NODE_FIELDS = ['key', 'identifier', 'name', 'label', 'abbr', 'aliases', 'year', 'date', 'lane', 'creatorLane', 'phase', 'span',
               'fairsharingType', 'fsrType', 'fsrCategory', 'principles', 'declaredIn', 'declaredBy', 'registry', 'scope',
               'creatorType', 'buildsOnFair', 'subdomains', 'fromCollection', 'sources', 'fairsharing', 'url', 'creator',
               'maintained', 'description', 'dateSource', 'dateBasis']
RELATION_FIELDS = ['subject', 'hadRole', 'target']
# Curation fields and vocabularies that stay out of the build. Relations keep only their label: their evidence and
# source cite the manuscript draft.
PRIVATE = ('decision', 'exclusionReason', 'coveredBy', 'manuscript', 'manuscriptEvidence', 'mentionedIn', 'reviewedBy',
           'note', 'fairsharingMatch')
PRIVATE_VOCABULARIES = ('decision', 'exclusionReason', 'manuscript', 'mentionedIn', 'fairsharingMatch', 'evidence')
# fsrCategory IRI -> label: one box each in the Class filter
CLASSES = {model.FER: 'FAIR-Enabling Resource', model.FSR: 'FAIR Supporting Resource'}
CLASS_DEF = {model.FER: 'Essential to the operationalisation of the FAIR principles: a service, specification or policy '
                        'that puts FAIR into action.',
             model.FSR: 'Any other resource that supports FAIR implementation.'}   # as the criteria define them
COLLECTION = 'FAIRsharing Toxicology collection'   # the collection as a source, named as in the criteria


NOT_A_NAME = re.compile(r'^[a-z]+\d+[a-z]?$|^Issue #|FAIRsharing\.')   # citation keys, issue numbers, record codes
DANGLING = re.compile(r'(?:\s+(?:the|of|on|in|for|and|to|a)|[\s,;:–-])+$', re.I)   # a cut name never ends on these


def clean_alias(r):
    """The first alias when it is a usable short name, else ''."""
    a = (r.get('alternateName') or [''])[0]
    ok = a and a != r['name'] and len(a) <= 28 and re.search(r'[A-Z0-9]', a) and not NOT_A_NAME.search(a)
    return a if ok else ''


def label(r):
    """The figure label: the name when short, else a clean short alias, else the name cut at a word."""
    name = r['name'].strip()
    if len(name) <= 28:
        return name
    if clean_alias(r):
        return clean_alias(r)
    return name if len(name) <= 40 else DANGLING.sub('', name[:40].rsplit(' ', 1)[0]) + '…'


def abbr(r):
    """The short alias shown after the name, unless the name already says it (ignoring case and punctuation)."""
    a, flat = clean_alias(r), lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
    return '' if not a or flat(a) in flat(r['name']) or flat(r['name']) in flat(a) else a


def fairsharing_url(r):
    ref = model.fs_ref(r.get('fairsharingRecord'))
    if r.get('fairsharingMatch') != 'confirmed' or not ref:
        return ''
    return 'https://doi.org/10.25504/' + ref if ref.startswith('FAIRsharing.') else f'https://fairsharing.org/{ref}'


def type_labels():
    """IRI -> label of every FSR type and of the two classes, as the page shows them."""
    return {**{k: v[0] for k, v in model.fsr_types().items()}, **CLASSES}


def nodes_links(doc):
    """Flatten the dataset for the page. Links run from the earlier resource (src, the relation's target) to the
    one that builds on or uses it (dst, the relation's subject), so "CTD implements ExO" is drawn ExO -> CTD. Declarations run
    from a FIP (src) to a resource it declares (dst), with each question and its declaration nanopublication (q)."""
    nodes, key_of = [], {r['@id']: r['key'] for r in doc['hasPart']}
    fsr = type_labels()
    for r in doc['hasPart']:
        fs = r.get('fairsharing') or {}
        date, basis = model.first_date(r)
        nodes.append({
            'key': r['key'], 'identifier': r.get('identifier', ''), 'name': r['name'].strip(), 'label': label(r),
            'abbr': abbr(r), 'aliases': r.get('alternateName', []), 'year': model._year(r),
            'date': date, 'lane': model.lane(r), 'creatorLane': model.creator_lane(r),
            'phase': r.get('phase', ''), 'span': r.get('span', []), 'fairsharingType': r.get('fairsharingType', ''),
            'fsrType': [fsr.get(t, t) for t in r.get('fsrType', [])], 'fsrCategory': fsr.get(r.get('fsrCategory'), ''),
            'principles': r.get('principles', []), 'declaredIn': [key_of[f] for f in r.get('declaredIn', [])],
            'declaredBy': key_of.get(r.get('declared-by'), ''), 'registry': model.registry(r) or '',
            'scope': r.get('scope', ''), 'creatorType': r.get('creatorType', []),
            'buildsOnFair': bool(r.get('buildsOnFair')), 'subdomains': r.get('subdomains', []),
            'fromCollection': bool(fs.get('inCollection')) and r.get('manuscript', 'absent') == 'absent',
            # where it was found, by the sources the criteria screen; the FIPs come below, once every key has a label
            'sources': ([doc['creator']['name']] if r.get('manuscript', 'absent') != 'absent' else [])
                       + ([COLLECTION] if fs.get('inCollection') else []),
            'fairsharing': fairsharing_url(r), 'url': r.get('url', ''), 'creator': r.get('creator', ''),
            'maintained': r.get('maintained', ''), 'description': r.get('description', ''),
            'dateSource': r.get('dateSource', ''), 'dateBasis': basis,
        })
    fips, label_of = {k for n in nodes for k in n['declaredIn']}, {n['key']: n['label'] for n in nodes}
    for n in nodes:   # a FIP is a source of what it declares and of itself; a row no source names was added by the curators
        n['sources'] += [label_of[k] for k in n['declaredIn']] + ([n['label']] if n['key'] in fips else [])
        n['sources'] = n['sources'] or [doc['creator']['name']]
    links = [{'src': x['target'], 'dst': x['subject'], 'label': x['hadRole'], 'lineage': model.RELATIONS[x['hadRole']][1]}
             for x in model.relation_rows(doc)]
    declared = {}
    for r in doc['hasPart']:
        for d in r.get('fipDeclaration', []):
            for p in model.FIP_PROPERTIES.keys() & d.keys():
                declared.setdefault((r['key'], key_of[d[p]]), []).append([fip._q(d['question']), d['@id']])
    return nodes, links, [{'src': s, 'dst': t, 'q': sorted(q)} for (s, t), q in sorted(declared.items())]


def public(doc):
    """The dataset as published: included resources only, without curation fields, unconfirmed FAIRsharing records,
    relation provenance, or relations and FIP declarations to resources that are not included; the curation
    vocabularies and sources go."""
    out = dict(doc)
    out['sources'] = {k: v for k, v in doc.get('sources', {}).items()
                      if k not in ('manuscript', 'previous', 'inventory')}
    out['vocabularies'] = {k: v for k, v in doc.get('vocabularies', {}).items() if k not in PRIVATE_VOCABULARIES}
    keep = [r for r in doc['hasPart'] if r.get('decision') == 'include']
    ids = {r['@id'] for r in keep}
    members = sorted(r['@id'] for r in keep if r.get('fairsharingMatch') == 'confirmed'   # inherited from FAIRsharing:
                     and (r.get('fairsharing') or {}).get('inCollection'))             # the collection's members
    out['hasPart'] = []
    for r in keep:
        p = {k: v for k, v in r.items() if k not in PRIVATE}
        if r.get('fairsharingMatch') != 'confirmed':
            p.pop('fairsharingRecord', None)
            p.pop('fairsharing', None)
        fs = p.get('fairsharing') or {}               # inherited, not curated: FAIRsharing's statements, on its record,
        terms = lambda kind: [{'@id': t['iri'], 'name': t['label']} for t in fs.get(kind, []) if t['iri']]   # IRIs only
        inherited = {'about': terms('subjects'), 'theme': terms('domains')}   # with the terms of scope and span
        if p.get('fairsharingRecord') and any(inherited.values()):
            p['fairsharingRecord'] = {'@id': 'https://fairsharing.org/' + p['fairsharingRecord'],
                                      **{k: v for k, v in inherited.items() if v}}
        p['qualifiedRelation'] = [{'relation': q['relation'], 'hadRole': q['hadRole']}
                                  for q in r.get('qualifiedRelation', []) if q['relation'] in ids]
        p['fipDeclaration'] = [d for d in r.get('fipDeclaration', []) if ids & {d.get(k) for k in model.FIP_PROPERTIES}]
        p['declaredIn'] = [x for x in r.get('declaredIn', []) if x in ids]
        p['declared-by'] = r.get('declared-by') if r.get('declared-by') in ids else None
        if r['@id'] == model.COLLECTION_DOI:
            p['resource'] = members
        if p.get('maintained') == 'unknown':   # nothing is stated when the status could not be established
            del p['maintained']
        out['hasPart'].append({k: v for k, v in p.items() if v not in (None, [])})
    return out


def page_meta(doc):
    return {
        'title': doc['name'], 'version': doc['version'], 'dateModified': doc.get('dateModified', ''),
        'creator': doc['creator']['name'], 'sources': doc.get('sources', {}), 'lanes': model.FIGURE_LANES,
        'toxLanes': model.FIGURE_LANES[2:], 'laneDef': model.LANE_DEF, 'classes': list(CLASSES.values()),
        'classDef': {CLASSES[k]: v for k, v in CLASS_DEF.items()},
        'typeIri': {v: k for k, v in type_labels().items()},   # label -> term, the links in the details
        'principleIri': fip.principles(),   # F1 -> the FAIR principle's term
        'ontologyIri': model.fip_ontology_version_iri(),   # the version read, linked in the About text
        'fairPublished': model.FAIR_PUBLISHED, 'license': doc['license'],   # the figure's marker; the licences
        # the Source filter's options: the curators, the collection, then the FIPs in the dataset
        'sourceList': [doc['creator']['name'], COLLECTION,
                       *sorted(label(r) for r in doc['hasPart'] if r['key'] in doc.get('sources', {}).get('fip', {}))],
        'communities': sorted(v[0] for v in model.fsr_types().values() if v[1] == model.FIC),   # never drawn
        'creatorLanes': list(model.CREATOR_LANE_DEF), 'creatorLaneDef': model.CREATOR_LANE_DEF,
        'subdomains': [[s, model.SUBDOMAIN_LANE[s]] for s in model.SUBDOMAINS],
        'outOfScope': list(model.OUTSIDE_MANUSCRIPT_SCOPE),   # listed, not drawn; the page never names the manuscript
        'relations': {k: {'id': v[0], 'lineage': v[1], 'definition': v[2]} for k, v in model.RELATIONS.items()},
        'vocab': doc.get('vocabularies', model.VOCABULARIES), 'repo': PUBLIC_REPO, 'pages': PAGES,   # source is private
        # field -> term, for the data dictionary; the prefixes (full IRIs) are not fields
        'terms': {f: model.term(f) for f in model.CONTEXT if f[0] != '@' and model.term(f)
                  and not model.term(f).startswith(('http', '@'))},
        # list -> value -> the name of its term of ours, the anchor where the term's IRI lands
        'termAnchors': {name: {v: model.concept(name, v)[len(model.TERMS):] for v in model.VOCABULARIES[name]
                               if v not in model.SAME.get(name, {})} for name in model.TERM_SETS},
        'doi': doc.get('identifier', ''), 'collection': model.COLLECTION_DOI, 'fields': FIELDS,
    }


def schema_org(doc):
    """schema.org Dataset metadata for the page head, so search engines (Google Dataset Search) find the dataset."""
    d = {
        '@context': 'https://schema.org', '@type': 'Dataset', 'name': doc['name'], 'description': doc['description'],
        'url': PAGES, 'version': doc['version'], 'dateModified': doc.get('dateModified', ''),
        'license': doc['license']['@id'], 'creditText': doc['creditText'], 'isBasedOn': doc.get('isBasedOn', []),
        'creator': {'@type': 'Organization', 'name': doc['creator']['name']},
        'keywords': ['FAIR', 'toxicology', 'FAIR supporting resources', 'FAIRsharing', 'research data management'],
        'distribution': [
            {'@type': 'DataDownload', 'encodingFormat': 'application/ld+json',
             'contentUrl': PAGES + 'fair-tox-ecosystem.jsonld'},
            {'@type': 'DataDownload', 'encodingFormat': 'text/csv', 'contentUrl': PAGES + 'resources.csv'},
            {'@type': 'DataDownload', 'encodingFormat': 'text/csv', 'contentUrl': PAGES + 'relations.csv'},
        ],
    }
    if doc.get('identifier'):
        d['identifier'] = doc['identifier']
    return d


# The data dictionary, one entry per field or group of fields: names, definition, and the controlled list it takes.
# The dashboard shows it, and the published dataset describes its fields with it (variableMeasured).
FIELDS = [
    ('key', 'Stable short identifier, used in the dashboard\'s links (#key) and in the CSV files.', None),
    ('name', 'Full name.', None),
    ('alternateName', 'Abbreviations and other names.', None),
    ('identifier', 'Persistent identifier: the FIC nanopublication of a FAIR Implementation Community, else the '
                   'FAIRsharing DOI, else https://w3id.org/fair-tox/dataset#key.', None),
    ('fairsharingType', 'FAIRsharing registry and record type, or Tool for software and services, which FAIRsharing '
                        'does not register.', 'fairsharingType'),
    ('fsrType', 'FAIR Supporting Resource (FSR) types in the FIP ontology, every one that applies, by the typing rule '
                'of the criteria. IRIs in the JSON-LD, labels in resources.csv.', None),
    ('fsrCategory', 'Derived from the FSR types: FAIR-Enabling Resource when one of them is, else FAIR Supporting '
                    'Resource (any other FSR). The Class filter uses it; resources without a type always pass it.', None),
    ('principles', 'Derived: the FAIR principles of the FIP questions the resource is declared for, such as F1; empty '
                   'when no FIP declares it.', None),
    ('scope', 'What the resource was made for: generic FAIR, generic life-science or toxicology infrastructure.', 'scope'),
    ('phase', 'The data life-cycle phase a toxicology resource acts on, the earliest if several. It sets the lane.',
     'phase'),
    ('span', 'Every data life-cycle phase a toxicology resource acts on, its phase first.', None),
    ('creatorType, qualifiedAttribution', 'Creator types: who made a toxicology resource; several may apply. In the '
     'layout by creator they set its lane (Made jointly for two or more). In the JSON-LD each is a qualified '
     'attribution whose role (hadRole) is the kind of creator.', 'creatorType'),
    ('buildsOnFair', f'Derived: true for a toxicology resource first published in {model.FAIR_PUBLISHED} or later that implements, '
                     'extends or profiles a generic resource. Its label is in italics.', None),
    ('subdomains', 'Toxicology sub-domains the resource serves.', 'subdomains'),
    ('datePublished, dateReleased, dateAdopted, dateCreated, date',
     'When the resource first became public: YYYY, YYYY-MM or YYYY-MM-DD, in the field of what the date refers to '
     '(publication, release, adoption, FAIRsharing year, or not recorded). resources.csv gives it as date, with '
     'dateBasis.', 'dateBasis'),
    ('dateSource', 'DOI or URL of the source that shows the date.', None),
    ('creator', 'Organisations that made the resource.', None),
    ('contactPoint', "Who to contact about the resource: a person's ORCID or an organisation's ROR. In the JSON-LD "
                     'only.', None),
    ('url', 'Homepage.', None),
    ('description', 'One to three sentences on what the resource is.', None),
    ('maintained', 'Maintenance status.', 'maintained'),
    ('fairsharingRecord', "FAIRsharing record code or numeric id. In the JSON-LD, a link to the record, with "
                          "FAIRsharing's subjects (about, as for scope) and domains (theme, as for span), inherited "
                          'when the dataset is built, not curated.', None),
    ('fsr', 'The IRIs under which the FIPs declare the resource, when they differ from its identifier.', None),
    ('fromCollection', 'In resources.csv only. Derived: true for a member of the FAIRsharing Toxicology collection '
                       'that entered this dataset only through the collection.', None),
    ('sources', 'In resources.csv only. Derived: where the resource was found, by the sources the criteria screen: the '
                'curation of the ELIXIR Toxicology Community, the FAIRsharing Toxicology collection, and each '
                'toxicology FIP that declares it (a FIP is a source of itself). The Source filter uses it.', None),
    ('qualifiedRelation, hadRole', 'Relations to other resources, read subject first ("CTD implements ExO"): '
                                   'qualifiedRelation in the JSON-LD, subject, hadRole and target in relations.csv.',
     'hadRole'),
    ('declaredIn', 'Derived: the FIPs that declare the resource (their keys in resources.csv).', None),
    ('fipDeclaration, declared-by', 'On a FIP, in the JSON-LD, read from its nanopublications (CC0) when the page is '
     'built: its declarations, each a nanopublication (@id) that links a listed resource through one of the '
     'properties below for a FIP question (question) and its principle; and declared-by, the FAIR Implementation '
     'Community that declares the FIP (declaredBy, its key, in resources.csv). The FIP declarations switch draws the '
     'declarations.', 'declaration'),
]
DEFINITION = {name: text for names, text, _ in FIELDS for name in names.split(', ')}


# Published files the dataset lists as downloads: media type, and the standard each follows.
DOWNLOADS = {'fair-tox-ecosystem.jsonld': ('application/ld+json', 'https://www.w3.org/TR/json-ld11/'),
             'resources.csv': ('text/csv', 'https://www.rfc-editor.org/rfc/rfc4180'),
             'relations.csv': ('text/csv', 'https://www.rfc-editor.org/rfc/rfc4180'),
             'terms.ttl': ('text/turtle', 'https://www.w3.org/TR/turtle/')}
CDIF = ['https://w3id.org/cdif/core/1.1', 'https://w3id.org/cdif/discovery/1.1']


def discovery(doc, out):
    """What the CDIF Discovery profile asks of the published dataset itself: its identifier (the Zenodo DOI once
    deposited, else its w3id address), landing page, release date (CITATION.cff), the years its resources span, the
    terms of its fields, its downloads with their checksums (the dataset file cannot carry its own), and the catalog
    record that declares conformance to CDIF Core and Discovery 1.1."""
    pid = doc.get('identifier') or model.BASE
    released = re.search(r'^date-released: *(\S+)', Path('CITATION.cff').read_text(encoding='utf-8'), re.M)
    years = sorted(filter(None, map(model._year, doc['hasPart'])))
    return {
        'identifier': {'@type': 'schema:PropertyValue', 'value': pid, 'url': pid,
                       **({'propertyID': 'https://registry.identifiers.org/registry/doi'} if '//doi.org/' in pid else {})},
        'url': PAGES, **({'datePublished': released.group(1)} if released else {}),
        **({'temporalCoverage': f'{years[0]}/{years[-1]}'} if years else {}), 'wasDerivedFrom': doc['isBasedOn'],
        'variableMeasured': [{'@type': 'schema:PropertyValue', 'name': f, 'propertyID': model.iri(model.term(f)),
                              'description': DEFINITION[f]}
                             for f in model.FIELD_ORDER if ':' in (model.term(f) or '')],
        'distribution': [{'@type': 'schema:DataDownload', 'contentUrl': PAGES + name, 'encodingFormat': media,
                          'conformsTo': spec, **({'checksum': {
                              '@type': 'spdx:Checksum', 'algorithm': 'SHA-256',
                              'checksumValue': hashlib.sha256(out[name].encode('utf-8')).hexdigest()}} if name in out else {})}
                         for name, (media, spec) in DOWNLOADS.items()],
        'subjectOf': {'@id': PAGES + 'fair-tox-ecosystem.jsonld', '@type': 'schema:Dataset',
                      'additionalType': 'dcat:CatalogRecord', 'about': model.BASE, 'conformsTo': CDIF,
                      'maintainer': doc['creator'],
                      'sdDatePublished': doc.get('dateModified', '')},
    }


def _script_json(value):
    # every '<' escaped, not only '</': '<!--' followed by '<script' in a text field would otherwise swallow the page
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')


def _csv(fields, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fields, extrasaction='ignore')
    w.writeheader()
    w.writerows({k: '; '.join(v) if isinstance(v, list) else v for k, v in row.items()} for row in rows)
    return buf.getvalue()


def build(doc, outdir, offline=False):
    """Write index.html, the dataset, two CSV files, the vocabulary and the context into outdir from the dataset with
    FAIRsharing added (fairsharing.enrich). The FIP declarations, read online or from the local cache, are added to a
    copy of the dataset, which is not saved."""
    doc = model.normalise(fip.enrich(copy.deepcopy(doc), fip.read(offline)))
    nodes, links, declarations = nodes_links(doc)
    doc = public(doc)
    keep = {r['key'] for r in doc['hasPart']}
    nodes = [n for n in nodes if n['key'] in keep]
    sources = {doc['creator']['name'], COLLECTION, *(n['label'] for n in nodes)}
    for n in nodes:   # as in public(): FIPs and communities that are not included are left out
        n['declaredIn'] = [k for k in n['declaredIn'] if k in keep]
        n['declaredBy'] = n['declaredBy'] if n['declaredBy'] in keep else ''
        n['sources'] = [s for s in n['sources'] if s in sources] or [doc['creator']['name']]
    links = [x for x in links if x['src'] in keep and x['dst'] in keep]
    declarations = [x for x in declarations if x['src'] in keep and x['dst'] in keep]
    page = files('fairtox').joinpath('dashboard.html').read_text(encoding='utf-8')
    terms = model.vocabulary(doc)
    jsonld = json.loads(terms.serialize(format='json-ld', context={p: str(ns) for p, ns in terms.namespaces()}))
    jsonld['@graph'].sort(key=lambda node: node['@id'])     # one order, so an unchanged build publishes nothing new
    page = page.replace('__SCHEMA__', _script_json(schema_org(doc)))
    page = page.replace('__DATA__', _script_json({'nodes': nodes, 'links': links, 'declarations': declarations,
                                                  'meta': page_meta(doc)}))
    out = {'index.html': page, 'resources.csv': _csv(NODE_FIELDS, nodes),
           'relations.csv': _csv(RELATION_FIELDS, model.relation_rows(doc)), 'terms.ttl': terms.serialize(format='turtle'),
           'terms.jsonld': model.dumps(jsonld), 'context.jsonld': model.dumps({'@context': model.CONTEXT})}
    out['fair-tox-ecosystem.jsonld'] = model.dumps({**doc, **discovery(doc, out)})
    leaks = [name for name, text in out.items() if re.search('manuscript', text, re.I)]
    if leaks:   # a last guard: the public pages go live from CI
        raise ValueError(f'public build not written: {", ".join(leaks)} mention the manuscript')
    Path(outdir).mkdir(parents=True, exist_ok=True)
    for name, text in out.items():
        (Path(outdir) / name).write_text(text, encoding='utf-8', newline='')
    return len(nodes), len(links)
