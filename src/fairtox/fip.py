"""FIP import: the declarations of the toxicology FIPs, read through each FIP's declaration index (never by community).

Every nanopublication read is kept in a local cache, build/fip/<id>.trig, with the answers of the nanopub query
service (invalidated nanopublications, the latest valid description of each declared resource, the valid FAIR
Implementation Communities) and FAIRsharing look-ups in build/fip/validity.json; `--offline` reads only that cache.
"""
import csv
import datetime as dt
import functools
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings

import rdflib
from rdflib import DCTERMS, OWL, RDF, RDFS, SKOS, URIRef

from fairtox import fairsharing, model
from fairtox.cli import names_of

FIPS = {'parcfip': 'https://w3id.org/np/RAKa7vUwc8qVbktDqDSpuq7lRrrKcjPKvkB4Tn7WHvr7E',
        'fairaop': 'https://w3id.org/np/RAQMnw2u-ZG_zVkVIzEdtYn3o4tYqyhsnOhiWaMLG01Bc'}
CACHE = 'build/fip'
QUERY = 'https://query.knowledgepixels.com/repo/full'
REPORT = 'build/fip-match-report.csv'
CONVERGENCE = 'docs/fip-convergence.md'
F, NPX = rdflib.Namespace(model.FIP), rdflib.Namespace('http://purl.org/nanopub/x/')
METHOD = ("Nanopublications read through each FIP's declaration index; validity from the admin graph of the nanopub "
          f'query service ({QUERY}): not invalidated by a nanopublication signed with the same key.')
PREFIXES = ('prefix np: <http://www.nanopub.org/nschema#> prefix npa: <http://purl.org/nanopub/admin/> '
            'prefix npx: <http://purl.org/nanopub/x/> prefix dct: <http://purl.org/dc/terms/> '
            'prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> prefix fip: <https://w3id.org/fair/fip/terms/> ')
VALID = ('graph npa:graph {{ ?np np:hasAssertion ?a ; {}npa:hasValidSignatureForPublicKey ?k . '
         'filter not exists {{ ?x npx:invalidates ?np ; npa:hasValidSignatureForPublicKey ?k }} }}')
INVALIDATED = ('select distinct ?np where { values ?np { %s } graph npa:graph { ?np npa:hasValidSignatureForPublicKey '
               '?k . ?x npx:invalidates ?np ; npa:hasValidSignatureForPublicKey ?k } }')
DESCRIPTIONS = ('select ?fsr ?np ?created where { values ?fsr { %s } graph ?a { ?fsr rdfs:label ?label } '
                + VALID.format('dct:created ?created ; ') + ' }')
FICS = ('select distinct ?fic ?label ?home where { graph ?a { ?fic a fip:FAIR-Implementation-Community . '
        'optional { ?fic rdfs:label ?label } optional { ?fic rdfs:seeAlso|<http://schema.org/url> ?home } } '
        + VALID.format('') + ' }')
ACTION = {'fsr': 'linked to {key}', 'doi': 'link to {key}', 'homepage': 'link to {key}',
          'name': 'link to {key} if it is the same resource', 'none': 'add as an undecided row'}


def _get(url, accept, data=None):
    """GET, or POST `data`, with retries and backoff on HTTP 429 and server errors."""
    request = urllib.request.Request(url, data, {'Accept': accept, 'User-Agent': fairsharing.UA})
    for wait in (5, 30, 120, None):
        try:
            with urllib.request.urlopen(request, timeout=120) as resp:
                return resp.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or wait is None:
                raise RuntimeError(f'{url} answered HTTP {e.code}') from None
            time.sleep(wait)


def _select(query):
    body = json.loads(_get(QUERY, 'application/sparql-results+json',
                           urllib.parse.urlencode({'query': PREFIXES + query}).encode()))
    return [{k: v['value'] for k, v in b.items()} for b in body['results']['bindings']]


def _values(iris):
    return ' '.join(f'<{i}>' for i in iris)


def _clean(text):
    return ' '.join(str(text or '').split())


def _q(question):
    """Short name of a FIP question: F1-D, or S-F1-Persistency-Policy for a supporting question."""
    return question.rsplit('/', 1)[-1].replace('FIP-', '').replace('Question-', '')


def _named(labels, fallback):
    """Name and aliases from 'ABBR | Name' labels (in either order): the longest part is the name."""
    parts = [p for p in dict.fromkeys(_clean(p) for label in labels for p in label.split('|')) if p] or [fallback]
    name = max(parts, key=len)
    return name, [p for p in parts if p != name]


def _url(homepages):
    return next((h for h in homepages if re.match(r'^https?://\S+$', h)), '')


def _graph(path):
    """All triples of a TriG file, of every graph in it, as one graph."""
    g = rdflib.Graph()
    with warnings.catch_warnings(action='ignore', category=DeprecationWarning):   # rdflib 7 warns about its own code
        g += (q[:3] for q in rdflib.Dataset().parse(path, format='trig').quads())
    return g


def nanopub(iri, offline=False):
    """A nanopublication's triples, from the cache; online, a missing one is fetched as TriG and cached first."""
    path = os.path.join(CACHE, re.search(r'/np/(RA[\w-]{43})', iri).group(1) + '.trig')
    if not offline and not os.path.exists(path):
        text = _get(iri, 'application/trig')
        os.makedirs(CACHE, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        time.sleep(fairsharing.PAUSE)
    return _graph(path)


@functools.cache
def ontology():
    """FIP question -> FAIR principle (such as F1) in the pinned FIP ontology, and the ontology's version label."""
    g = _graph(model.FIP_ONTOLOGY)
    version = _clean(g.value(g.value(None, RDF.type, NPX.NanopubIndex), RDFS.label))
    return {str(q): str(p).rsplit('/', 1)[-1] for q, p in g.subject_objects(F['refers-to-principle'])}, version


def read(offline=False):
    """Walk the FIPs: FIP -> declaration index -> valid declarations -> the latest valid description of each declared
    resource. Online, the query answers are renewed and missing nanopublications fetched; offline, only the cache is
    read."""
    answers = os.path.join(CACHE, 'validity.json')
    ans = model.load(answers) if offline else {'retrieved': dt.date.today().isoformat(), 'query': QUERY}
    principle, version = ontology()
    fips, decls = {}, []
    for key, iri in FIPS.items():
        g = nanopub(iri, offline)
        p = g.value(None, RDF.type, F['FAIR-Implementation-Profile'])
        fips[key] = {'label': _clean(g.value(p, RDFS.label)), 'profile': str(p), 'nanopub': iri,
                     'index': str(g.value(p, F['has-declaration-index'])), 'fic': str(g.value(p, F['declared-by'])),
                     'created': str(g.value(URIRef(iri), DCTERMS.created)).replace('+00:00', 'Z'),
                     'licence': str(g.value(URIRef(iri), DCTERMS.license))}
        for element in sorted(nanopub(fips[key]['index'], offline).objects(None, NPX.includesElement)):
            g = nanopub(str(element), offline)
            d, q = next(g.subject_objects(F['refers-to-question']))
            base = {'fip': key, 'nanopub': str(element), '@id': str(d), 'question': str(q),
                    'principle': principle.get(str(q)), 'considerations': _clean(g.value(d, F.considerations))}
            uses = [(p, str(t)) for p in model.FIP_PROPERTIES if p.startswith('declares-') for t in g.objects(d, F[p])]
            for p, t in uses or [(None, None)]:   # none: a no-choice declaration
                decls.append({**base, 'predicate': p, 'target': t})
    own = [f[k] for f in fips.values() for k in ('nanopub', 'index')]
    if not offline:
        nps = dict.fromkeys(own + [x['nanopub'] for x in decls])
        ans['invalidated'] = sorted({x['np'] for x in _select(INVALIDATED % _values(nps))})
    bad = set(ans['invalidated'])
    if bad & set(own):
        raise RuntimeError(f'invalidated FIP or declaration index {sorted(bad & set(own))}: update FIPS')
    for key, f in fips.items():
        f['invalidated'] = len({x['nanopub'] for x in decls if x['fip'] == key and x['nanopub'] in bad})
    decls = [x for x in decls if x['nanopub'] not in bad]
    for key, f in fips.items():
        f['noChoice'] = sorted(_q(x['question']) for x in decls if x['fip'] == key and not x['target'])

    targets = sorted({x['target'] for x in decls if x['target']})
    if not offline:
        latest = {}
        for x in _select(DESCRIPTIONS % _values(targets)):
            latest[x['fsr']] = max(latest.get(x['fsr'], ('', '')), (x['created'], x['np']))
        ans['descriptions'] = {k: v[1] for k, v in sorted(latest.items())}
    fsrs = {}
    for iri in targets:
        desc, s = ans['descriptions'].get(iri), URIRef(iri)
        g = nanopub(desc, offline) if desc else rdflib.Graph()
        refs = {iri} | {str(o) for p in (SKOS.exactMatch, SKOS.closeMatch, OWL.sameAs) for o in g.objects(s, p)}
        labels = sorted(_clean(x) for x in g.objects(s, RDFS.label))
        name, aliases = _named(labels, iri)
        fsrs[iri] = {'description': desc, 'labels': labels, 'name': name, 'aliases': aliases,
                     'types': sorted(re.split(r'[/#]', str(x))[-1] for x in g.objects(s, RDF.type)),
                     'fairsharing': sorted(r for r in refs if 'fairsharing' in r.lower()),
                     'homepages': sorted(str(x) for x in g.objects(s, URIRef('http://schema.org/url')))}
    numbers = sorted({c for f in fsrs.values() for c in map(model.fs_ref, f['fairsharing']) if c.isdigit()})
    if not offline:   # legacy numeric FAIRsharing pages give their DOI without a login
        ans['fairsharing'] = {n: model.fs_ref(fairsharing.slim(fairsharing.lookup(n))['doi']) for n in numbers}
    for f in fsrs.values():
        f['codes'] = sorted({ans.get('fairsharing', {}).get(c, c) for c in map(model.fs_ref, f['fairsharing'])} - {''})

    if not offline:
        fic = {}
        for x in _select(FICS):
            f = fic.setdefault(x['fic'], {'labels': set(), 'homepages': set()})
            f['labels'].update([_clean(x['label'])] if x.get('label') else [])
            f['homepages'].update([x['home']] if x.get('home') else [])
        ans['fic'] = {k: {n: sorted(v) for n, v in f.items()} for k, f in sorted(fic.items())}
        os.makedirs(CACHE, exist_ok=True)
        with open(answers, 'w', encoding='utf-8') as out:
            out.write(model.dumps(ans))
    return {'retrieved': ans['retrieved'], 'version': version, 'fips': fips, 'declarations': decls, 'fsrs': fsrs,
            'fic': ans['fic']}


def same(r, homepages, names):
    """'homepage' or 'name' when the row has one of these homepages, or one of these names or aliases."""
    if r.get('url') and fairsharing.norm_url(r['url']) in {fairsharing.norm_url(h) for h in homepages}:
        return 'homepage'
    if ({fairsharing.norm_name(n) for n in names} & {fairsharing.norm_name(n) for n in names_of(r)}) - {''}:
        return 'name'
    return None


def find(rows, iri, codes=(), homepages=(), names=()):
    """The row a declared resource is and how it was found: linked by an earlier import (fsr), then FAIRsharing DOI or
    record id (doi), homepage, name or alias (name, to be checked); (None, 'none') when it is not in the dataset."""
    by_id, by_code = fairsharing._index({'hasPart': rows})
    for r in rows:
        if iri in r.get('fsr', []):
            return r, 'fsr'
    for c in codes:
        r = by_id.get(int(c)) if c.isdigit() else by_code.get(c.lower())
        if r:
            return r, 'doi'
    for how in ('homepage', 'name'):
        for r in rows:
            if same(r, homepages, names) == how:
                return r, how
    return None, 'none'


def match(doc, data):
    """{FSR IRI: (row or None, method)} for every declared resource."""
    return {iri: find(doc['hasPart'], iri, f['codes'], f['homepages'],
                      names_of({'name': f['name'], 'alternateName': f['aliases']})) for iri, f in data['fsrs'].items()}


def report(doc, data, matches):
    """Write the match report: one row per declared resource, then the FAIR Implementation Communities to check (the
    FIPs' own, and every valid one whose label or homepage matches a row excluded as E1). Returns the rows."""
    out = []
    for iri, (r, how) in sorted(matches.items(), key=lambda m: (list(ACTION).index(m[1][1]),
                                                                data['fsrs'][m[0]]['name'].casefold())):
        f, ds = data['fsrs'][iri], [x for x in data['declarations'] if x['target'] == iri]
        out.append({'fips': '; '.join(dict.fromkeys(x['fip'] for x in ds)),
                    'questions': '; '.join(sorted({_q(x['question']) for x in ds})), 'fsr': iri,
                    'label': '; '.join(f['labels']), 'kind': '; '.join(f['types']),
                    'fairsharing': '; '.join(f['fairsharing']), 'homepage': '; '.join(f['homepages']),
                    'key': r['key'] if r else '', 'method': how, 'action': ACTION[how].format(key=r and r['key'])})
    for iri, f in data['fic'].items():
        declaring = [k for k, x in data['fips'].items() if x['fic'] == iri]
        name, aliases = _named(f['labels'], iri)
        names = names_of({'name': name, 'alternateName': aliases})
        hits = [(r, 'fsr') for r in doc['hasPart'] if r.get('@id') == iri] or [
            (r, how) for r in doc['hasPart'] if declaring or r.get('exclusionReason') == 'E1'
            for how in [same(r, f['homepages'], names)] if how]
        for r, how in hits or ([(None, 'none')] if declaring else []):
            action = ('linked to {key}' if how == 'fsr' else
                      'add as a FAIR Implementation Community row' + ('; check whether it is {key}' if r else '')
                      if declaring else 'identity check only: is {key} this community?')
            out.append({'fips': '; '.join(declaring), 'questions': '', 'fsr': iri, 'label': '; '.join(f['labels']),
                        'kind': 'FAIR-Implementation-Community', 'fairsharing': '',
                        'homepage': '; '.join(f['homepages']), 'key': r['key'] if r else '', 'method': how,
                        'action': action.format(key=r and r['key'])})
    os.makedirs(os.path.dirname(os.path.abspath(REPORT)), exist_ok=True)
    with open(REPORT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, list(out[0]))
        w.writeheader()
        w.writerows(out)
    return out


def apply(doc, data, matches):
    """Write the import into the dataset, in place: fsr links on the matched rows, undecided rows for the others, the
    declaring FICs, declared-by and the declarations on the FIP rows, sources.fip and isBasedOn. The links and
    declarations are importer-owned and replaced wholesale, so a second import changes nothing."""
    rows, date = doc['hasPart'], data['retrieved']
    by_key, taken = {r['key']: r for r in rows}, {r['key'] for r in rows}
    for r in rows:
        r.pop('fsr', None)
    target = {}
    for iri, (r, how) in matches.items():
        f, r = data['fsrs'][iri], r and by_key[r['key']]
        if r is None:
            first = next(x for x in data['declarations'] if x['target'] == iri)
            code = next((c for c in f['codes'] if c.startswith('FAIRsharing.') or c.isdigit()), '')
            r = {'key': model.slug(min([f['name']] + f['aliases'], key=len), taken), 'name': f['name'],
                 'alternateName': f['aliases'], 'decision': 'undecided', 'url': _url(f['homepages']),
                 'fairsharingRecord': code,
                 'fairsharingMatch': ('confirmed' if iri in f['fairsharing'] else 'to check') if code else '',
                 'note': f"Surfaced by {by_key[first['fip']]['name']} declaration {first['@id']}; screen against "
                         f'I1-I5. Retrieved {date}.'}
            r['@id'] = model.iri_of(r)
            taken.add(r['key'])
            rows.append(r)
        if iri != r['@id']:
            r['fsr'] = sorted(set(r.get('fsr', [])) | {iri})
        target[iri] = r['@id']
    for key, f in data['fips'].items():
        fic = data['fic'].get(f['fic'])
        if fic and not any(r.get('@id') == f['fic'] for r in rows):
            name, aliases = _named(fic['labels'], f['fic'])
            rows.append({'@id': f['fic'], 'key': model.slug(min([name] + aliases, key=len), taken), 'name': name,
                         'alternateName': aliases, 'decision': 'undecided', 'fsrType': [model.FIC],
                         'url': _url(fic['homepages']),
                         'note': f"FAIR Implementation Community that declares {by_key[key]['name']}, from its FIC "
                                 f'nanopublication. Retrieved {date}.'})
            taken.add(rows[-1]['key'])
        mine = sorted((x for x in data['declarations'] if x['fip'] == key and x['target']),
                      key=lambda x: (x['predicate'], target[x['target']], x['@id']))
        by_key[key]['declared-by'] = f['fic']
        by_key[key]['fipDeclaration'] = [{k: v for k, v in {
            '@id': x['@id'], '@type': 'fip:FIP-Declaration', x['predicate']: target[x['target']],
            'question': x['question'], 'principle': x['principle'], 'considerations': x['considerations']}.items() if v}
            for x in mine]
    doc.setdefault('sources', {})['fip'] = {key: {
        'label': f['label'], 'profile': f['profile'], 'nanopub': f['nanopub'], 'index': f['index'], 'fic': f['fic'],
        'created': f['created'], 'licence': f['licence'], 'retrieved': date,
        'declarations': sum(1 for x in data['declarations'] if x['fip'] == key and x['target']),
        'noChoice': f['noChoice'], 'invalidated': f['invalidated'], 'ontology': data['version'], 'method': METHOD}
        for key, f in data['fips'].items()}
    doc['isBasedOn'] = sorted(set(doc.get('isBasedOn', [])) | {f['profile'] for f in data['fips'].values()})
    return doc


def convergence(data):
    """Write the convergence table: per FIP question (the core questions in FAIR order, then the supporting ones),
    each FIP's choices or "no choice", and whether the FIPs share a choice."""
    principle, _ = ontology()
    core = sorted(principle, key=lambda q: ('FAIR'.index(_q(q)[0]), _q(q)))
    fips = data['fips']
    label = lambda iri: min([data['fsrs'][iri]['name']] + data['fsrs'][iri]['aliases'], key=len)
    lines, shared = [], []
    for q in core + sorted({x['question'] for x in data['declarations']} - set(core)):
        cells, picks = [], []
        for key in fips:
            ds = [x for x in data['declarations'] if x['fip'] == key and x['question'] == q]
            picks.append({x['target'] for x in ds if x['target']})
            cells.append(', '.join(sorted(map(label, picks[-1]), key=str.casefold)) if picks[-1] else
                         'no choice' if ds else 'not answered')
        both = set.intersection(*picks)
        if both and q in core:
            shared.append(_q(q))
        lines.append(f"| {_q(q)} | {principle.get(q, '')} | {' | '.join(cells)} | {'yes' if both else 'no'} |")
    text = '\n'.join([
        '# FIP convergence', '',
        f"Retrieved {data['retrieved']} through each FIP's declaration index; {data['version']}.", '',
        f'The FIPs share a choice on {len(shared)} of {len(core)} core questions'
        + (f" ({', '.join(shared)})" if shared else '') + '; no-choice declarations: '
        + ', '.join(f"{f['label']} {len(f['noChoice'])}" for f in fips.values()) + '.', '',
        '| Question | Principle | ' + ' | '.join(f['label'] for f in fips.values()) + ' | Shared |',
        '|---' * (3 + len(fips)) + '|', *lines]) + '\n'
    os.makedirs(os.path.dirname(os.path.abspath(CONVERGENCE)), exist_ok=True)
    with open(CONVERGENCE, 'w', encoding='utf-8') as f:
        f.write(text)
