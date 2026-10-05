"""Build the static dashboard: index.html with the data embedded, plus the dataset and CSV downloads."""
import csv
import json
import os
import re
import shutil
from importlib.resources import files

from fairtox import model

REPO = 'https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology'
PAGES = 'https://johannehouweling.github.io/FAIR-implementation-ecosystem-for-toxicology/'
CRITERIA = REPO + '/blob/main/docs/inclusion-criteria.md'
NODE_FIELDS = ['key', 'name', 'label', 'abbr', 'year', 'date', 'lane', 'phase', 'type', 'registry', 'scope', 'stakeholder',
               'subdomains', 'decision', 'exclusionReason', 'coveredBy', 'manuscript', 'manuscriptEvidence',
               'inCollection', 'fairsharing', 'url', 'creator', 'maintained', 'description', 'dateSource', 'dateBasis']


NOT_A_NAME = re.compile(r'^[a-z]+\d+[a-z]?$|^Issue #|FAIRsharing\.')   # citation keys, issue numbers, record codes


def clean_alias(r):
    """The first alias when it is a usable short name, else ''."""
    a = (r.get('alternateName') or [''])[0]
    ok = a and a != r['name'] and len(a) <= 28 and re.search(r'[A-Z0-9]', a) and not NOT_A_NAME.search(a)
    return a if ok else ''


def label(r):
    """The figure label: the name when short, else a clean short alias, else the name cut at a word."""
    name = r['name']
    if len(name) <= 28:
        return name
    if clean_alias(r):
        return clean_alias(r)
    return name if len(name) <= 40 else name[:40].rsplit(' ', 1)[0] + '…'


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
            'key': r['key'], 'name': r['name'], 'label': label(r), 'abbr': clean_alias(r), 'year': model._year(r),
            'date': r.get('datePublished', ''), 'lane': model.lane(r), 'phase': r.get('phase', ''),
            'type': r.get('type', ''), 'registry': model.registry(r) or '', 'scope': r.get('scope', ''),
            'stakeholder': r.get('stakeholder', ''), 'subdomains': r.get('subdomains', []),
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


def page_meta(doc):
    return {
        'title': doc['name'], 'version': doc['version'], 'dateModified': doc.get('dateModified', ''),
        'sources': doc.get('sources', {}), 'lanes': model.LANES, 'toxLanes': model.TOX_LANES, 'laneDef': model.LANE_DEF,
        'subdomains': [[s, model.SUBDOMAIN_LANE[s]] for s in model.SUBDOMAINS],
        'relations': {k: {'id': v[0], 'lineage': v[1], 'definition': v[2]} for k, v in model.RELATIONS.items()},
        'vocab': model.VOCABULARIES, 'repo': REPO, 'pages': PAGES, 'criteria': CRITERIA,
        'doi': doc.get('identifier', ''), 'collection': model.COLLECTION_DOI,
    }


def schema_org(doc):
    """schema.org Dataset metadata for the page head, so search engines (Google Dataset Search) find the dataset."""
    d = {
        '@context': 'https://schema.org', '@type': 'Dataset', 'name': doc['name'], 'description': doc['description'],
        'url': PAGES, 'version': doc['version'], 'dateModified': doc.get('dateModified', ''),
        'license': doc['license'], 'creditText': doc['creditText'], 'isBasedOn': doc.get('isBasedOn', []),
        'creator': {'@type': 'Organization', 'name': doc.get('creator', '')},
        'keywords': ['FAIR', 'toxicology', 'FAIR-enabling resources', 'FAIRsharing', 'research data management'],
        'codeRepository': REPO,
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


def build(doc, outdir, dataset_path=model.DATASET):
    """Write index.html, the dataset and two CSV files into outdir."""
    os.makedirs(outdir, exist_ok=True)
    nodes, links = nodes_links(doc)
    page = files('fairtox').joinpath('dashboard.html').read_text(encoding='utf-8')
    page = page.replace('__SCHEMA__', _script_json(schema_org(doc)))
    page = page.replace('__DATA__', _script_json({'nodes': nodes, 'links': links, 'meta': page_meta(doc)}))
    with open(os.path.join(outdir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page)
    shutil.copyfile(dataset_path, os.path.join(outdir, 'fair-tox-ecosystem.jsonld'))
    with open(os.path.join(outdir, 'resources.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, NODE_FIELDS)
        w.writeheader()
        for n in nodes:
            w.writerow({**n, 'subdomains': '; '.join(n['subdomains'])})
    with open(os.path.join(outdir, 'relations.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, ['subject', 'hadRole', 'target', 'evidence', 'source', 'reviewedBy', 'note'])
        w.writeheader()
        w.writerows(model.relation_rows(doc))
    return len(nodes), len(links)
