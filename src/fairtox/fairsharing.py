"""FAIRsharing: the Toxicology collection (3496) and the records of the dataset's rows, and the submission export.

Every read is kept in a local cache, build/fairsharing/records.json; `--offline` reads only that cache. FAIRsharing
is read in full once a day: a later read that day keeps the day's records and reads only what they lack. Requests
are PAUSE seconds apart, as FAIRsharing asked.

The dataset stores only what is curated (`curate`): new collection members, as undecided rows or proposed matches,
and the result of searching FAIRsharing for each row never checked against it (`check`).
Record data, collection membership and associations are added when the site, the sheet or the submission export is
built (`enrich`), with their retrieval date.

FAIRsharing data are CC BY-SA 4.0 (credited in the dataset header and on the dashboard). Bulk data come only through
the signed-in REST API, as FAIRsharing asks; the public record JSON is used for single look-ups. Credentials come from
the environment (FAIRSHARING_LOGIN, FAIRSHARING_PASSWORD); the token stays in memory and nothing secret is printed.
"""
import datetime as dt
import difflib
import json
import os
import re
import time
import urllib.error
import urllib.parse

from fairtox import model, web

API = 'https://api.fairsharing.org'
SITE = 'https://fairsharing.org'
PAUSE = 10                  # seconds from one request to the next: FAIRsharing asked for one every 8 to 12 seconds
_last = float('-inf')       # when the last request started (time.monotonic)
CACHE = 'build/fairsharing'
RECORD_TYPE = {v[1]: k for k, v in model.TYPES.items() if v[1]}
MAINTAINED = {'ready': 'active', 'deprecated': 'discontinued', 'in_development': 'in development',
              'uncertain': 'unknown'}
STATUS = {v: k for k, v in MAINTAINED.items()}
# FAIRsharing's sub-labels folded into the six labels the dataset uses (accepts and outputs are kinds of implements;
# shares_data_with and shares_code_with are kinds of related_to).
FOLD = {'accepts': 'implements', 'outputs': 'implements', 'shares_data_with': 'related_to',
        'shares_code_with': 'related_to'}
# Common words left out of a search: with them, FAIRsharing's search answers HTTP 500 to many longer queries.
COMMON = {'a', 'an', 'and', 'for', 'from', 'in', 'of', 'on', 'or', 'the', 'to', 'with'}


class FairsharingError(web.Unreadable):
    pass


def _request(method, url, body=None, token=None):
    global _last
    time.sleep(max(0, _last + PAUSE - time.monotonic()))
    _last = time.monotonic()
    headers = {'Accept': 'application/json'}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        answer, raw = web.fetch(url, headers, data, method, timeout=60)
    except urllib.error.HTTPError as e:
        reason = _reason(e)
        if e.code == 401 and url.endswith('/users/sign_in'):
            raise FairsharingError(f'FAIRsharing refused the sign-in ({reason}): check FAIRSHARING_LOGIN and '
                                   'FAIRSHARING_PASSWORD (an ORCID account needs a FAIRsharing password).') from None
        if e.code in (401, 403):
            raise FairsharingError(f'signed in, but FAIRsharing refused {method} {url} '
                                   f'(HTTP {e.code}: {reason}).') from None
        raise FairsharingError(f'{method} {url} answered HTTP {e.code} ({reason}).') from None
    if 'true' in (str(answer.get('maintenance')).lower(), str(answer.get('read-only')).lower()):
        raise FairsharingError('FAIRsharing is in maintenance or read-only mode; try again later.')
    return json.loads(raw)


def _reason(error):
    """FAIRsharing's own error text from an HTTP error response (it never echoes credentials)."""
    try:
        body = json.loads(error.read().decode('utf-8', 'replace'))
        return str(body.get('error') or body.get('message') or body.get('errors') or body)[:200] \
            if isinstance(body, dict) else str(body)[:200]
    except (ValueError, OSError):
        return 'no details'


def sign_in(login, password):
    jwt = _request('POST', f'{API}/users/sign_in', {'user': {'login': login, 'password': password}}).get('jwt')
    if not jwt:
        raise FairsharingError('FAIRsharing answered the sign-in without a token.')
    return jwt


def record(rid, jwt):
    return _request('GET', f'{API}/fairsharing_records/{rid}', token=jwt)


def lookup(ref):
    """Public record JSON (no login) for one id or FAIRsharing.xxx code."""
    return _request('GET', f'{SITE}/{model.fs_ref(ref)}')


def search(q, jwt):
    """The first page (25 records) of FAIRsharing's search for q, with the fields `propose` compares."""
    found = _request('POST', f'{API}/search/fairsharing_records?q={urllib.parse.quote(q)}', token=jwt)['data']
    return [{k: s[k] for k in ('id', 'doi', 'name', 'abbreviation', 'homepage')} for s in map(slim, found)]


def _first(*values):
    for v in values:
        if v not in (None, '', [], {}):
            return v
    return None


def _name(v):
    return v.get('name') or v.get('label') if isinstance(v, dict) else v


def slim(raw):
    """A FAIRsharing record in any of the shapes FAIRsharing serves (REST JSON:API, public JSON, GraphQL) -> the
    fields the dataset keeps, plus its associations with other records."""
    d = raw.get('data', raw) if isinstance(raw, dict) else {}
    a = d.get('attributes') or d
    meta = a.get('metadata') or {}
    tags = a.get('tags') or {}

    def terms(name):                                # the public record gives IRIs, the REST record only labels
        items = _first(tags.get(name), a.get(name)) or []
        return [{'iri': t.get('iri') or '', 'label': t['label']} if isinstance(t, dict) else {'iri': '', 'label': t}
                for t in items if (t.get('label') if isinstance(t, dict) else t)]

    assocs = []
    for key, outgoing in (('record_associations', True), ('recordAssociations', True),
                          ('reverse_record_associations', False), ('reverseRecordAssociations', False)):
        for x in a.get(key) or []:
            other = _first(x.get('linked_record'), x.get('linkedRecord')) if outgoing else \
                _first(x.get('fairsharing_record'), x.get('fairsharingRecord'))
            label = _name(_first(x.get('record_assoc_label'), x.get('recordAssocLabel')))
            if isinstance(other, dict) and other.get('id') and label:
                assocs.append({'other': int(other['id']), 'otherName': other.get('name', ''), 'label': label,
                               'outgoing': outgoing})
    # REST shape (checked 5 Oct 2026): linked_records = outgoing, linking_records = incoming
    for key, outgoing in (('linked_records', True), ('linking_records', False)):
        for x in a.get(key) or []:
            side = 'linked_record' if outgoing else 'linking_record'
            rid = _first(x.get(f'{side}_id'), x.get('linked_record_id'), x.get('linking_record_id'))
            if rid and x.get('relation'):
                assocs.append({'other': int(rid), 'label': x['relation'], 'outgoing': outgoing,
                               'otherName': _first(x.get(f'{side}_name'), x.get('linked_record_name'),
                                                   x.get('linking_record_name')) or ''})
    year = _first(meta.get('year_creation'), a.get('year_creation'))
    registry = _name(_first(a.get('registry'), a.get('fairsharing_registry')))
    return {
        'id': int(d['id']), 'doi': _first(a.get('doi'), meta.get('doi')),
        'name': re.sub(r'^FAIRsharing record for:\s*', '', _first(meta.get('name'), a.get('name')) or '').strip(),
        'abbreviation': _first(a.get('abbreviation'), meta.get('abbreviation')),
        'registry': str(registry).capitalize() if registry else None,
        'recordType': _name(_first(a.get('record_type'), a.get('type'))),
        'status': _first(meta.get('status'), a.get('status')),
        'yearCreation': int(year) if str(year or '').isdigit() else None,
        'homepage': _first(meta.get('homepage'), a.get('homepage')),
        'description': _first(meta.get('description'), a.get('description')),
        'subjects': terms('subjects'), 'domains': terms('domains'), 'associations': assocs,
        'legacyIds': _first(a.get('legacy_ids'), a.get('legacyIds')) or [],   # bsg-xxx, cited by older nanopublications
    }


def block(rec, members, today):
    """The `fairsharing` block that `enrich` adds to a resource."""
    keep = ('id', 'doi', 'name', 'abbreviation', 'registry', 'recordType', 'status', 'yearCreation', 'homepage',
            'subjects', 'domains')
    out = {k: rec[k] for k in keep if rec.get(k) not in (None, '')}
    out['inCollection'] = rec['id'] in members
    out['associations'] = sorted([FOLD.get(a['label'], a['label']), a['other']] for a in rec['associations']
                                 if a['outgoing'])
    out['retrieved'] = today
    return out


def norm_url(u):
    return re.sub(r'^https?://(www\.)?', '', str(u or '').strip().lower()).rstrip('/')


def norm_name(s):
    return re.sub(r'[^a-z0-9]+', ' ', str(s or '').lower()).strip()


def _index(doc):
    """Rows by FAIRsharing record id and by lower-case FAIRsharing.xxx code, from fairsharingRecord and @id."""
    by_id, by_code = {}, {}
    for r in doc['hasPart']:
        for ref in map(model.fs_ref, (r.get('fairsharingRecord'), r.get('@id'))):
            if ref.isdigit():
                by_id[int(ref)] = r
            if ref.startswith('FAIRsharing.'):
                by_code[ref.lower()] = r
    return by_id, by_code


def find(doc, rec):
    """The dataset resource a FAIRsharing record belongs to, via a recorded id or DOI only."""
    by_id, by_code = _index(doc)
    code = (rec.get('doi') or '').split('/')[-1].lower()
    return by_id.get(rec['id']) or (by_code.get(code) if code else None)


def row_names(r):
    """A row's name and other names, each also split at its brackets ("AOP-DB (Adverse Outcome Pathway Database)" is
    also "AOP-DB" and "Adverse Outcome Pathway Database"), normalised."""
    texts = [t for t in (r.get('name'), *r.get('alternateName', [])) if t]
    return list(dict.fromkeys(n for t in texts for n in map(norm_name, (t, *re.split(r'[()]', t))) if n))


def propose(r, records):
    """A `to check` proposal for a resource with no FAIRsharing match yet: homepage, then name or abbreviation."""
    names = set(row_names(r))
    for rec in records:
        if r.get('url') and rec.get('homepage') and norm_url(r['url']) == norm_url(rec['homepage']):
            return rec, 'same homepage'
    for rec in records:
        theirs = {norm_name(rec.get('name')), norm_name(rec.get('abbreviation'))} - {''}
        if names & theirs:
            return rec, 'same name or abbreviation'
        if any(difflib.SequenceMatcher(None, a, b).ratio() >= 0.85 for a in names for b in theirs if len(a) > 5):
            return rec, 'similar name'
    return None, ''


def unchecked(doc):
    """Rows never checked against FAIRsharing: not excluded, with neither a FAIRsharing record nor a match."""
    return [r for r in doc['hasPart'] if r.get('decision') != 'exclude' and not r.get('fairsharingMatch')
            and not r.get('fairsharingRecord')]


def queries(r):
    """What a row is searched for in FAIRsharing: its names (`row_names`) without common words, each cut to its first
    ten words, and its homepage's host, in letters, digits and dots only. FAIRsharing's search answers HTTP 500 to a
    slash, a bracket and many queries of more than ten words or with common words (tried on 31 Oct 2026)."""
    host = (urllib.parse.urlsplit(r.get('url') or '').hostname or '').removeprefix('www.')
    names = (' '.join([w for w in n.split() if w not in COMMON][:10]) for n in row_names(r))
    return list(dict.fromkeys(q for q in (*names, host) if q))


def _code(rec):
    return (rec.get('doi') or '').split('/')[-1] or str(rec['id'])


def read(login, password, offline=False, search_unchecked=False):
    """The collection members, the records of the collection and of every row with a FAIRsharing record and, with
    `search_unchecked` (only `fairtox fairsharing`), what FAIRsharing's search finds for each unchecked row (`searches`, by key),
    read signed in and cached; offline, only the cache is read. A row searched the same day is not searched again."""
    path = os.path.join(CACHE, 'records.json')
    if offline:
        if not os.path.exists(path):
            raise FairsharingError(f'{path} is missing: read FAIRsharing once without --offline.')
        return model.load(path)
    if not (login and password):
        raise FairsharingError('FAIRSHARING_LOGIN and FAIRSHARING_PASSWORD are not set (locally: uv run --env-file '
                               '.env fairtox ...); --offline reads the local cache.')
    jwt, records = sign_in(login, password), {}
    cached = model.load(path) if os.path.exists(path) else {}
    today = cached.get('retrieved') == dt.date.today().isoformat()   # read today: only what is missing is read
    if today:
        records = {x['id']: x for x in cached['records']}

    def get(rid):
        records[rid] = slim(record(rid, jwt))
        public = slim(lookup(rid))                      # subjects and domains with their IRIs
        records[rid].update({k: public[k] for k in ('subjects', 'domains')})

    if model.COLLECTION_ID not in records:
        get(model.COLLECTION_ID)
    members = sorted({a['other'] for a in records[model.COLLECTION_ID]['associations']
                      if a['outgoing'] and a['label'] == 'collects'})
    if not members:
        raise FairsharingError('no collection members found in the collection record; the REST field names may '
                               'differ: adapt slim().')
    doc = model.load()
    refs = {model.fs_ref(r.get('fairsharingRecord')) for r in doc['hasPart']}
    for rid in sorted((set(members) | {int(x) for x in refs if x.isdigit()}) - set(records)):
        get(rid)
    known = {model.fs_ref(x['doi']) for x in records.values()}
    for code in sorted(x for x in refs if x.startswith('FAIRsharing.') and x not in known):
        rid = slim(lookup(code))['id']   # the public record JSON gives the record id behind a code
        if rid not in records:
            get(rid)
    searches, failed = dict(cached.get('searches', {})) if today else {}, 0
    for r in [r for r in unchecked(doc) if r['key'] not in searches] if search_unchecked else []:
        hits = {}                                       # in FAIRsharing's order, each record once
        try:
            for q in queries(r):
                for x in search(q, jwt):
                    hits.setdefault(x['id'], x)
        except web.Unreadable:                          # not answered, even when asked again: the row stays
            failed += 1                                 # unchecked until the next read; after three rows in a
            if failed == 3:                             # row the search is taken to be down
                break
            continue
        failed = 0
        searches[r['key']] = list(hits.values())
    data = {'retrieved': dt.date.today().isoformat(), 'members': members,
            'records': [records[k] for k in sorted(records)], 'searches': searches}
    os.makedirs(CACHE, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(model.dumps(data))
    return data


def curate(doc, data):
    """What `fairtox fairsharing --apply` saves, in place: a collection member without a row is proposed for an open
    row with the same homepage or name (to check), or else added as an undecided row; a second run changes nothing.
    Returns the report: these changes, FAIRsharing associations that are not relations here (two-hop when the other
    record has no row), and first-publication years more than a year from FAIRsharing's year of creation."""
    report, members = [], set(data['members'])
    open_rows = [r for r in doc['hasPart'] if not r.get('fairsharingMatch')]
    for rec in data['records']:
        if rec['id'] not in members or find(doc, rec) is not None:
            continue
        code = _code(rec)
        hit = next((r for r in open_rows if propose(r, [rec])[0]), None)
        if hit is not None:
            hit.update(fairsharingRecord=code, fairsharingMatch='to check')
            open_rows.remove(hit)
            report.append(f"proposed match: {hit['key']} = FAIRsharing {rec['id']} {rec['name']} "
                          f"({propose(hit, [rec])[1]})")
            continue
        key = model.slug(rec.get('abbreviation') or rec['name'], {r['key'] for r in doc['hasPart']})
        row = {'key': key, 'name': rec['name'], 'alternateName': [rec['abbreviation']] if rec.get('abbreviation') else [],
               'decision': 'undecided', 'fairsharingType': RECORD_TYPE.get(rec.get('recordType'), ''),
               'url': rec.get('homepage') or '', 'description': rec.get('description') or '',
               'maintained': MAINTAINED.get(rec.get('status'), 'unknown'), 'manuscript': 'absent',
               'fairsharingRecord': code, 'fairsharingMatch': 'confirmed',
               'note': f"Added from the FAIRsharing Toxicology collection on {data['retrieved']}."}
        if rec.get('yearCreation'):
            row.update(datePublished=str(rec['yearCreation']), dateBasis='FAIRsharing year',
                       dateSource='https://doi.org/' + rec['doi'] if rec.get('doi') else f"{SITE}/{rec['id']}")
        doc['hasPart'].append(row)
        report.append(f"new collection member: {key} ({rec['name']})")
    model.normalise(doc)
    by_id = {x['id']: x for x in data['records']}
    linked = lambda r: {q['relation'] for q in r.get('qualifiedRelation', [])}
    for rec in data['records']:
        r = find(doc, rec)
        if r is None:
            continue
        year, fy = model._year(r), rec.get('yearCreation')
        if year and fy and abs(fy - year) > 1:
            report.append(f"{r['key']}: first published {year}, FAIRsharing year of creation {fy}")
        for a in rec['associations']:
            label = FOLD.get(a['label'], a['label'])
            if not a['outgoing'] or label not in model.RELATIONS:
                continue
            t = find(doc, by_id.get(a['other'], {'id': a['other']}))
            if t is None:
                report.append(f"two-hop: {r['key']} {a['label']} FAIRsharing {a['other']} {a['otherName']}")
            elif t is not r and t['@id'] not in linked(r) and r['@id'] not in linked(t):
                report.append(f"FAIRsharing association, not a relation here: {r['key']} {label} {t['key']}")
    return report


def check(doc, data):
    """What `fairtox fairsharing --apply` saves, in place, for each unchecked row that FAIRsharing was searched for: the
    record found by the rules of `propose` that no other row has, to check, or else no record. Returns the report."""
    report = []
    for r in unchecked(doc):
        hits = data.get('searches', {}).get(r['key'])
        if hits is None:
            report.append(f"not searched in FAIRsharing, still unchecked: {r['key']}")
            continue
        rec, why = propose(r, [x for x in hits if find(doc, x) is None])   # a record is one row's identifier
        if rec:
            r.update(fairsharingRecord=_code(rec), fairsharingMatch='to check')
            report.append(f"proposed match: {r['key']} = FAIRsharing {rec['id']} {rec['name']} ({why})")
        else:
            r['fairsharingMatch'] = 'no record'
            report.append(f"no FAIRsharing record found: {r['key']}")
    return report


def enrich(doc, data):
    """For the site, the sheet and the submission export, in memory: the `fairsharing` block of each row whose record
    was read, and sources.fairsharing with the retrieval date."""
    members = set(data['members'])
    for rec in data['records']:
        r = find(doc, rec)
        if r is not None:
            r['fairsharing'] = block(rec, members, data['retrieved'])
    doc.setdefault('sources', {})['fairsharing'] = {'retrieved': data['retrieved'], 'members': len(members)}
    return doc


# ---- submission export -----------------------------------------------------------------------------------------------

def submission(doc):
    """What could be added to FAIRsharing, from a document with FAIRsharing added (`enrich`), in the shapes of its API.
    Only what FAIRsharing accepts and the curators have checked is proposed: new records for included resources that
    FAIRsharing was checked not to hold; associations it allows between these record types and does not hold yet,
    between records that exist or are proposed here, with published evidence; and records to add to the collection.
    Everything else is held back with the reason. Nothing is posted: FAIRsharing approves a new record only once its
    subjects, domains, species, countries and organisations are filled in."""
    rs = {r['key']: r for r in doc['hasPart'] if r.get('decision') == 'include'}
    out = {'records': [], 'associations': [], 'collectionAdditions': [], 'heldBack': []}
    ref = {}
    for k, r in rs.items():
        t, code = model.TYPES.get(r.get('fairsharingType')), model.fs_ref(r.get('fairsharingRecord'))
        if r.get('fairsharingMatch') == 'confirmed' and code:
            ref[k] = r['@id'] if not r['@id'].startswith(model.BASE) else f'{SITE}/{code}'
            if not (r.get('fairsharing') or {}).get('inCollection'):
                out['collectionAdditions'].append({'key': k, 'name': r['name'], 'record': ref[k]})
            continue
        missing = [f for f in ('name', 'description', 'url') if not r.get(f)]
        reason = ('FAIRsharing not yet checked for a record of it' if r.get('fairsharingMatch') != 'no record' else
                  'software: bio.tools, or FAIRassist for FAIR assessment tools' if not t or t[0] == 'Tool' else
                  'missing ' + ', '.join(missing) if missing else '')
        if reason:
            out['heldBack'].append({'item': k, 'name': r['name'], 'reason': reason})
            continue
        ref[k] = f'new: {k}'
        metadata = {'name': r['name'], 'homepage': r['url'], 'description': r['description'],
                    'status': STATUS.get(r.get('maintained'), 'uncertain')}
        if r.get('alternateName'):
            metadata['abbreviation'] = r['alternateName'][0]
        if model._year(r):
            metadata['year_creation'] = model._year(r)
        out['records'].append({'key': k, 'fairsharing_record': {'metadata': metadata, 'record_type_id': t[2]},
                               'for_the_form': {'type': r['fairsharingType'], 'organisations': r.get('creator', ''),
                                                'publication': r.get('dateSource', '')}})
    for x in model.relation_rows(doc):
        s, t = x['subject'], x['target']
        if s not in rs or t not in rs or x['evidence'] == 'FAIRsharing':
            continue
        ids = [(rs[k].get('fairsharing') or {}).get('id') for k in (s, t)]
        if [x['hadRole'], ids[1]] in (rs[s].get('fairsharing') or {}).get('associations', []):
            continue
        reason = ('not a FAIRsharing label' if model.RELATIONS[x['hadRole']][0] is None else
                  'FAIRsharing does not allow this label between these record types'
                  if (model.registry(rs[s]), model.registry(rs[t])) not in model.ALLOWED.get(x['hadRole'], set()) else
                  'not every end is in FAIRsharing or proposed here' if s not in ref or t not in ref else
                  'the only evidence is the unpublished manuscript' if x['evidence'] == 'manuscript' else '')
        if reason:
            out['heldBack'].append({'item': f"{s} {x['hadRole']} {t}", 'reason': reason})
            continue
        out['associations'].append({'record': ref[s], 'record_id': ids[0], 'relation': x['hadRole'],
                                    'linked_record': ref[t], 'linked_record_id': ids[1],
                                    'record_assoc_label_id': model.RELATIONS[x['hadRole']][0],
                                    'evidence': x['evidence'], 'source': x['source']})
    return out


def write_submission(doc, outdir):
    from openpyxl import Workbook
    os.makedirs(outdir, exist_ok=True)
    sub = submission(doc)
    with open(os.path.join(outdir, 'fairsharing-submission.json'), 'w', encoding='utf-8') as f:
        json.dump(sub, f, indent=1, ensure_ascii=False)
    wb = Workbook()
    wb.remove(wb.active)
    flat = {
        'New records': [{'key': x['key'], **x['fairsharing_record']['metadata'],
                         'record_type_id': x['fairsharing_record']['record_type_id'], **x['for_the_form']}
                        for x in sub['records']],
        'Associations': sub['associations'], 'Add to collection': sub['collectionAdditions'],
        'Held back': sub['heldBack'],
    }
    for title, rows in flat.items():
        ws = wb.create_sheet(title)
        cols = list(dict.fromkeys(c for row in rows for c in row)) or ['(none)']
        ws.append(cols)
        for row in rows:
            ws.append([row.get(c, '') for c in cols])
        ws.freeze_panes = 'A2'
    wb.save(os.path.join(outdir, 'fairsharing-submission.xlsx'))
    return {k: len(v) for k, v in sub.items()}
