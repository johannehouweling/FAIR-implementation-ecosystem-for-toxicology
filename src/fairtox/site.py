"""Build the static dashboard: index.html with the data embedded, plus the dataset and CSV downloads.

The public build (the default, deployed to GitHub Pages) holds the included resources only, without curation fields.
The internal build (`--internal`, local only) holds every row and adds the curation view: the parts of the template
marked <!--internal-->...<!--/internal--> or /*internal*/.../*/internal*/, which the public build strips.
"""
import csv
import io
import json
import re
from importlib.resources import files
from pathlib import Path

from fairtox import model

REPO = 'https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology'          # private
# CI deploys the public build to this public repository, which serves it on GitHub Pages
PUBLIC_REPO = 'https://github.com/johannehouweling/FAIR-implementation-ecosystem-toxicology-timeline'
PAGES = 'https://johannehouweling.github.io/FAIR-implementation-ecosystem-toxicology-timeline/'
CRITERIA = REPO + '/blob/main/docs/inclusion-criteria.md'
NODE_FIELDS = ['key', 'name', 'label', 'abbr', 'aliases', 'year', 'date', 'lane', 'creatorLane', 'phase', 'type',
               'registry', 'scope', 'stakeholders', 'buildsOnFair', 'subdomains', 'decision', 'exclusionReason',
               'coveredBy', 'manuscript', 'manuscriptEvidence', 'inCollection', 'fairsharing', 'url', 'creator',
               'maintained', 'description', 'dateSource', 'dateBasis']
RELATION_FIELDS = ['subject', 'hadRole', 'target', 'evidence', 'source', 'reviewedBy', 'note']
# Curation fields and vocabularies that stay out of the public build. Relations keep only their label: their evidence
# and source cite the manuscript draft. inCollection serves the curation panel only.
PRIVATE = ('decision', 'exclusionReason', 'coveredBy', 'manuscript', 'manuscriptEvidence', 'reviewedBy', 'note',
           'fairsharingMatch')
PRIVATE_VOCABULARIES = ('decision', 'exclusionReason', 'manuscript', 'fairsharingMatch', 'evidence')
PUBLIC_FIELDS = [f for f in NODE_FIELDS if f not in PRIVATE and f != 'inCollection']
INTERNAL = re.compile(r'(?:<!--|/\*)internal(?:-->|\*/).*?(?:<!--|/\*)/internal(?:-->|\*/)', re.S)


NOT_A_NAME = re.compile(r'^[a-z]+\d+[a-z]?$|^Issue #|FAIRsharing\.')   # citation keys, issue numbers, record codes


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
    return name if len(name) <= 40 else name[:40].rsplit(' ', 1)[0] + '…'


def abbr(r):
    """The short alias shown after the name, unless the name already says it (ignoring case and punctuation)."""
    a, flat = clean_alias(r), lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
    return '' if not a or flat(a) in flat(r['name']) or flat(r['name']) in flat(a) else a


def fairsharing_url(r):
    ref = model.fs_ref(r.get('fairsharingRecord'))
    if r.get('fairsharingMatch') != 'confirmed' or not ref:
        return ''
    return 'https://doi.org/10.25504/' + ref if ref.startswith('FAIRsharing.') else f'https://fairsharing.org/{ref}'


def nodes_links(doc):
    """Flatten the dataset for the page. Links run from the earlier resource (src, the relation's target) to the
    one that builds on it (dst, the relation's subject), so "CTD implements ExO" is drawn ExO -> CTD."""
    nodes = []
    for r in doc['hasPart']:
        fs = r.get('fairsharing') or {}
        nodes.append({
            'key': r['key'], 'name': r['name'].strip(), 'label': label(r), 'abbr': abbr(r),
            'aliases': r.get('alternateName', []), 'year': model._year(r),
            'date': r.get('datePublished', ''), 'lane': model.lane(r), 'creatorLane': model.creator_lane(r),
            'phase': r.get('phase', ''), 'type': r.get('type', ''), 'registry': model.registry(r) or '',
            'scope': r.get('scope', ''), 'stakeholders': r.get('stakeholders', []),
            'buildsOnFair': bool(r.get('buildsOnFair')), 'subdomains': r.get('subdomains', []),
            'decision': r.get('decision', 'undecided'), 'exclusionReason': r.get('exclusionReason', ''),
            'coveredBy': r.get('coveredBy', ''), 'manuscript': r.get('manuscript', 'absent'),
            'manuscriptEvidence': r.get('manuscriptEvidence', ''), 'inCollection': bool(fs.get('inCollection')),
            'fairsharing': fairsharing_url(r), 'url': r.get('url', ''), 'creator': r.get('creator', ''),
            'maintained': r.get('maintained', ''), 'description': r.get('description', ''),
            'dateSource': r.get('dateSource', ''), 'dateBasis': r.get('dateBasis', ''),
        })
    links = [{'src': x['target'], 'dst': x['subject'], 'label': x['hadRole'], 'lineage': model.RELATIONS[x['hadRole']][1],
              'evidence': x['evidence'], 'source': x['source'], 'note': x['note']} for x in model.relation_rows(doc)]
    return nodes, links


def public(doc):
    """The dataset as published: included resources only, without curation fields, unconfirmed FAIRsharing records,
    relation provenance or relations to resources that are not included; the curation vocabularies and sources go."""
    out = dict(doc)
    out['sources'] = {k: v for k, v in doc.get('sources', {}).items() if k not in ('manuscript', 'previous')}
    out['vocabularies'] = {k: v for k, v in doc.get('vocabularies', {}).items() if k not in PRIVATE_VOCABULARIES}
    if 'subdomains' in out['vocabularies']:   # their definitions cite the manuscript's figure caption
        out['vocabularies']['subdomains'] = {s: re.sub(r'\s*\([^)]*manuscript[^)]*\)', '', d)
                                             for s, d in out['vocabularies']['subdomains'].items()}
    keep = [r for r in doc['hasPart'] if r.get('decision') == 'include']
    ids = {r['@id'] for r in keep}
    out['hasPart'] = []
    for r in keep:
        p = {k: v for k, v in r.items() if k not in PRIVATE}
        if r.get('fairsharingMatch') != 'confirmed':
            p.pop('fairsharingRecord', None)
            p.pop('fairsharing', None)
        rels = [{'relation': q['relation'], 'hadRole': q['hadRole']} for q in r.get('qualifiedRelation', [])
                if q['relation'] in ids]
        if rels:
            p['qualifiedRelation'] = rels
        else:
            p.pop('qualifiedRelation', None)
        out['hasPart'].append(p)
    return out


def page_meta(doc, internal=False):
    return {
        'title': doc['name'], 'version': doc['version'], 'dateModified': doc.get('dateModified', ''),
        'creator': doc.get('creator', ''), 'sources': doc.get('sources', {}), 'lanes': model.LANES,
        'toxLanes': model.TOX_LANES, 'laneDef': model.LANE_DEF,
        'creatorLanes': list(model.CREATOR_LANE_DEF), 'creatorLaneDef': model.CREATOR_LANE_DEF,
        'subdomains': [[s, model.SUBDOMAIN_LANE[s]] for s in model.SUBDOMAINS],
        'relations': {k: {'id': v[0], 'lineage': v[1], 'definition': v[2]} for k, v in model.RELATIONS.items()},
        'vocab': doc.get('vocabularies', model.VOCABULARIES), 'repo': REPO if internal else PUBLIC_REPO, 'pages': PAGES,
        'publicRepo': PUBLIC_REPO,   # cited in both builds: the source repository is private
        'doi': doc.get('identifier', ''), 'collection': model.COLLECTION_DOI,
        **({'criteria': CRITERIA} if internal else {}),
    }


def schema_org(doc):
    """schema.org Dataset metadata for the page head, so search engines (Google Dataset Search) find the dataset."""
    d = {
        '@context': 'https://schema.org', '@type': 'Dataset', 'name': doc['name'], 'description': doc['description'],
        'url': PAGES, 'version': doc['version'], 'dateModified': doc.get('dateModified', ''),
        'license': doc['license'], 'creditText': doc['creditText'], 'isBasedOn': doc.get('isBasedOn', []),
        'creator': {'@type': 'Organization', 'name': doc.get('creator', '')},
        'keywords': ['FAIR', 'toxicology', 'FAIR-enabling resources', 'FAIRsharing', 'research data management'],
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


def _script_json(value):
    # every '<' escaped, not only '</': '<!--' followed by '<script' in a text field would otherwise swallow the page
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')


def _csv(fields, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fields, extrasaction='ignore')
    w.writeheader()
    w.writerows({k: '; '.join(v) if isinstance(v, list) else v for k, v in row.items()} for row in rows)
    return buf.getvalue()


def build(doc, outdir, dataset_path=model.DATASET, internal=False):
    """Write index.html, the dataset and two CSV files into outdir: the public build, or with internal=True the
    curation view of every row with a copy of the full dataset (never to be published)."""
    nodes, links = nodes_links(doc)
    page = files('fairtox').joinpath('dashboard.html').read_text(encoding='utf-8')
    if internal:
        fields, rel_fields, dataset = NODE_FIELDS, RELATION_FIELDS, Path(dataset_path).read_text(encoding='utf-8')
    else:
        doc = public(doc)
        keep = {r['key'] for r in doc['hasPart']}
        fields, rel_fields, dataset = PUBLIC_FIELDS, RELATION_FIELDS[:3], model.dumps(doc)
        nodes = [{f: n[f] for f in fields} for n in nodes if n['key'] in keep]
        links = [{k: x[k] for k in ('src', 'dst', 'label', 'lineage')} for x in links
                 if x['src'] in keep and x['dst'] in keep]
        page = INTERNAL.sub('', page)
    page = page.replace('__SCHEMA__', _script_json(schema_org(doc)))
    page = page.replace('__DATA__', _script_json({'nodes': nodes, 'links': links, 'meta': page_meta(doc, internal)}))
    out = {'index.html': page, 'fair-tox-ecosystem.jsonld': dataset, 'resources.csv': _csv(fields, nodes),
           'relations.csv': _csv(rel_fields, model.relation_rows(doc))}
    leaks = [name for name, text in out.items() if not internal and re.search('manuscript', text, re.I)]
    if leaks:   # a last guard: the public pages go live from CI
        raise ValueError(f'public build not written: {", ".join(leaks)} mention the manuscript')
    Path(outdir).mkdir(parents=True, exist_ok=True)
    for name, text in out.items():
        (Path(outdir) / name).write_text(text, encoding='utf-8', newline='')
    return len(nodes), len(links)
