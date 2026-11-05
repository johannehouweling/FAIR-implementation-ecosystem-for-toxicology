"""Names of creators given as ORCID or ROR links, read from the registries' public APIs (no login) and kept in
build/pids/names.json; `--offline` reads only that cache. A creator given as a name is never looked up."""
import json
import os
import re

from fairtox import web

CACHE = 'build/pids'
ORCID = re.compile(r'^https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]$')
ROR = re.compile(r'^https://ror\.org/0[a-hj-km-np-tv-z0-9]{6}\d{2}$')


def is_pid(value):
    """Whether `value` is an ORCID or ROR link."""
    return bool(ORCID.match(value or '') or ROR.match(value or ''))


def _registered(iri):
    code = iri.rsplit('/', 1)[1]
    if ORCID.match(iri):
        name = json.loads(web.get(f'https://pub.orcid.org/v3.0/{code}/person', 'application/json')).get('name') or {}
        part = lambda k: (name.get(k) or {}).get('value') or ''
        return part('credit-name') or ' '.join(p for p in (part('given-names'), part('family-name')) if p)
    org = json.loads(web.get(f'https://api.ror.org/v2/organizations/{code}', 'application/json'))
    return next((n['value'] for n in org.get('names', []) if 'ror_display' in n.get('types', [])), '')


def names(values, offline=False):
    """ORCID or ROR link -> its registered name, for the links among `values`: the cache answers first, each registry
    is asked once per link, and offline an unknown link gets no name."""
    path = os.path.join(CACHE, 'names.json')
    known = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            known = json.load(f)
    new = sorted(v for v in set(values) if is_pid(v) and v not in known)
    if new and not offline:
        known.update({v: _registered(v) for v in new})
        os.makedirs(CACHE, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(known, f, indent=1, sort_keys=True, ensure_ascii=False)
            f.write('\n')
    return {v: known[v] for v in set(values) if known.get(v)}
