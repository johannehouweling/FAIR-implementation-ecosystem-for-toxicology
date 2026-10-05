"""FAIRsharing: sign in, pull the Toxicology collection (3496) and linked records, merge them into the dataset,
propose matches for manuscript resources, and write the submission export.

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
import urllib.request

from fairtox import __version__, model

API = 'https://api.fairsharing.org'
SITE = 'https://fairsharing.org'
UA = f'fairtox/{__version__} (+https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology)'
PAUSE = 0.25
RECORD_TYPE = {v[1]: k for k, v in model.TYPES.items() if v[1]}
MAINTAINED = {'ready': 'active', 'deprecated': 'discontinued', 'in_development': 'in development',
              'uncertain': 'unknown'}
STATUS = {v: k for k, v in MAINTAINED.items()}
# FAIRsharing's sub-labels folded into the six labels the dataset uses (accepts and outputs are kinds of implements;
# shares_data_with and shares_code_with are kinds of related_to).
FOLD = {'accepts': 'implements', 'outputs': 'implements', 'shares_data_with': 'related_to',
        'shares_code_with': 'related_to'}


class FairsharingError(RuntimeError):
    pass


def _request(method, url, body=None, token=None):
    headers = {'Accept': 'application/json', 'User-Agent': UA}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data, headers, method=method), timeout=60) as resp:
                if 'true' in (str(resp.headers.get('maintenance')).lower(), str(resp.headers.get('read-only')).lower()):
                    raise FairsharingError('FAIRsharing is in maintenance or read-only mode; try again later.')
                return json.load(resp)
        except urllib.error.HTTPError as e:
            reason = _reason(e)
            if e.code == 401 and url.endswith('/users/sign_in'):
                raise FairsharingError(f'FAIRsharing refused the sign-in ({reason}): check FAIRSHARING_LOGIN and '
                                       'FAIRSHARING_PASSWORD (an ORCID account needs a FAIRsharing password).') from None
            if e.code in (401, 403):
                raise FairsharingError(f'signed in, but FAIRsharing refused {method} {url} '
                                       f'(HTTP {e.code}: {reason}).') from None
            if e.code in (429, 500, 502, 503, 504) and attempt == 1:
                time.sleep(5)
                continue
            raise FairsharingError(f'{method} {url} answered HTTP {e.code} ({reason}).') from None
        except urllib.error.URLError as e:
            raise FairsharingError(f'{method} {url} failed: {e.reason}') from None


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

    def terms(name):
        items = _first(a.get(name), tags.get(name)) or []
        return [{'iri': t.get('iri', ''), 'label': t['label']} for t in items if isinstance(t, dict) and t.get('label')]

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
        'name': re.sub(r'^FAIRsharing record for:\s*', '', _first(meta.get('name'), a.get('name')) or ''),
        'abbreviation': _first(a.get('abbreviation'), meta.get('abbreviation')),
        'registry': str(registry).capitalize() if registry else None,
        'recordType': _name(_first(a.get('record_type'), a.get('type'))),
        'status': _first(meta.get('status'), a.get('status')),
        'yearCreation': int(year) if str(year or '').isdigit() else None,
        'homepage': _first(meta.get('homepage'), a.get('homepage')),
        'description': _first(meta.get('description'), a.get('description')),
        'subjects': terms('subjects'), 'domains': terms('domains'), 'associations': assocs,
    }


def block(rec, members, today):
    """The `fairsharing` block stored on a resource (never curated)."""
    keep = ('id', 'doi', 'name', 'abbreviation', 'registry', 'recordType', 'status', 'yearCreation', 'homepage')
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
    by_id, by_code = {}, {}
    for r in doc['hasPart']:
        fs = r.get('fairsharing') or {}
        ref = model.fs_ref(r.get('fairsharingRecord'))
        if fs.get('id'):
            by_id[int(fs['id'])] = r
        if ref.isdigit():
            by_id[int(ref)] = r
        if ref.startswith('FAIRsharing.'):
            by_code[ref.lower()] = r
        if fs.get('doi'):
            by_code[fs['doi'].split('/')[-1].lower()] = r
    return by_id, by_code


def find(doc, rec):
    """The dataset resource a FAIRsharing record belongs to, via a recorded id or DOI only."""
    by_id, by_code = _index(doc)
    code = (rec.get('doi') or '').split('/')[-1].lower()
    return by_id.get(rec['id']) or (by_code.get(code) if code else None)


def propose(r, records):
    """A `to check` proposal for a resource with no FAIRsharing match yet: homepage, then name or abbreviation."""
    names = {norm_name(r.get('name'))} | {norm_name(x) for x in r.get('alternateName', [])}
    names.discard('')
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


def merge(doc, records, members, today=None):
    """Write FAIRsharing data into the dataset in place and return report lines. Curated fields are only filled for
    new rows; a resource's `fairsharing` block is replaced; FAIRsharing associations between dataset resources become
    relations with evidence FAIRsharing."""
    today = today or dt.date.today().isoformat()
    report = []
    unmatched = []
    for rec in records:
        r = find(doc, rec)
        if r is None:
            unmatched.append(rec)
            continue
        was = (r.get('fairsharing') or {}).get('inCollection')
        r['fairsharing'] = block(rec, members, today)
        if was and not r['fairsharing']['inCollection']:
            report.append(f"{r['key']}: no longer in the collection")
    # members not yet in the dataset: propose a match to an existing row, else add a new row
    open_rows = [r for r in doc['hasPart'] if not r.get('fairsharingMatch')]
    for rec in unmatched:
        if rec['id'] not in members:
            continue
        hit = next((r for r in open_rows if propose(r, [rec])[0]), None)
        if hit is not None:
            hit['fairsharingRecord'] = (rec.get('doi') or '').split('/')[-1] or str(rec['id'])
            hit['fairsharingMatch'] = 'to check'
            hit['fairsharing'] = block(rec, members, today)
            open_rows.remove(hit)
            report.append(f"proposed match: {hit['key']} = FAIRsharing {rec['id']} {rec['name']} "
                          f"({propose(hit, [rec])[1]})")
            continue
        key = model.slug(rec.get('abbreviation') or rec['name'], {r['key'] for r in doc['hasPart']})
        row = {'key': key, 'name': rec['name'], 'alternateName': [rec['abbreviation']] if rec.get('abbreviation') else [],
               'decision': 'undecided', 'type': RECORD_TYPE.get(rec.get('recordType'), ''),
               'url': rec.get('homepage') or '', 'description': rec.get('description') or '',
               'maintained': MAINTAINED.get(rec.get('status'), 'unknown'), 'manuscript': 'absent',
               'fairsharingRecord': (rec.get('doi') or '').split('/')[-1] or str(rec['id']),
               'fairsharingMatch': 'confirmed', 'fairsharing': block(rec, members, today),
               'note': f'Added from the FAIRsharing Toxicology collection on {today}.'}
        if rec.get('yearCreation'):
            row.update(datePublished=str(rec['yearCreation']), dateBasis='FAIRsharing year',
                       dateSource='https://doi.org/' + rec['doi'] if rec.get('doi') else f"{SITE}/{rec['id']}")
        doc['hasPart'].append(row)
        report.append(f"new collection member: {key} ({rec['name']})")
    # associations between dataset resources
    model.normalise(doc)
    for rec in records:
        subject = find(doc, rec)
        for a in rec['associations']:
            label = FOLD.get(a['label'], a['label'])
            if not a['outgoing'] or label not in model.RELATIONS:
                continue
            target = find(doc, {'id': a['other']})
            if subject is None or target is None:
                if subject is not None and a['label'] != 'collects':
                    report.append(f"two-hop: {subject['key']} {a['label']} FAIRsharing {a['other']} {a['otherName']}")
                continue
            linked = {q['relation'] for q in subject.get('qualifiedRelation', [])}
            back = {q['relation'] for q in target.get('qualifiedRelation', [])}
            if target['@id'] in linked or subject['@id'] in back or target is subject:
                continue
            subject.setdefault('qualifiedRelation', []).append({
                'relation': target['@id'], 'hadRole': label, 'evidence': 'FAIRsharing',
                'source': f"https://fairsharing.org/{rec['id']}" + (f" ({a['label']})" if label != a['label'] else '')})
            report.append(f"new relation: {subject['key']} {label} {target['key']}")
    return report


def fetch(doc, login, password, dry_run=None, today=None, log=print, sample=None):
    """Sign in, read the collection and every relevant record, merge. Returns report lines."""
    today = today or dt.date.today().isoformat()
    jwt = sign_in(login, password)
    raw = record(model.COLLECTION_ID, jwt)
    if dry_run:
        attrs = (raw.get('data') or {}).get('attributes') or raw
        log('collection record keys: ' + ', '.join(sorted(attrs)))
        for key in ('linked_records', 'linking_records', 'record_associations', 'reverse_record_associations'):
            if isinstance(attrs.get(key), list):
                log(f'{key}: {len(attrs[key])} items; first two: '
                    + json.dumps(attrs[key][:2], ensure_ascii=False)[:1500])
    coll = slim(raw)
    members = {a['other'] for a in coll['associations'] if a['outgoing'] and a['label'] == 'collects'}
    if not members:
        if not dry_run:
            raise FairsharingError('No collection members found in the collection record; the REST field names may '
                                   'differ. Run with --dry-run 3 and adapt slim().')
        log('no collection members recognised yet; continuing with records from the dataset')
    ids = set(members)
    for r in doc['hasPart']:
        fs, ref = r.get('fairsharing') or {}, model.fs_ref(r.get('fairsharingRecord'))
        if fs.get('id'):
            ids.add(int(fs['id']))
        elif ref.isdigit():
            ids.add(int(ref))
        elif ref.startswith('FAIRsharing.'):
            ids.add(slim(lookup(ref))['id'])
            time.sleep(PAUSE)
    ids = (list(sample) if sample else sorted(ids)[:dry_run]) if dry_run else sorted(ids)
    records = []
    for rid in ids:
        raw = record(rid, jwt)
        records.append(slim(raw))
        if dry_run:
            attrs = (raw.get('data') or {}).get('attributes') or raw
            log(f'record {rid} keys: ' + ', '.join(sorted(attrs)))
            for key in ('linked_records', 'linking_records'):
                items = attrs.get(key) if isinstance(attrs.get(key), list) else []
                log(f'  {key}: {len(items)} items; first two: ' + json.dumps(items[:2], ensure_ascii=False)[:800])
            log('  ' + json.dumps({k: v for k, v in records[-1].items() if k != 'description'}, ensure_ascii=False)[:800])
        time.sleep(PAUSE)
    if dry_run:
        return [f'dry run: {len(members)} collection members; nothing written']
    report = merge(doc, records, members, today)
    doc.setdefault('sources', {})['fairsharing'] = {
        'collection': model.COLLECTION_DOI, 'members': len(members), 'method': 'FAIRsharing REST API',
        'retrieved': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    return [f'{len(records)} FAIRsharing records read; {len(members)} collection members'] + report


# ---- submission export -----------------------------------------------------------------------------------------------

def submission(doc):
    """What could be added to FAIRsharing: new records (in the API create shape), associations FAIRsharing does not
    hold yet, records to add to the collection, and resources FAIRsharing does not register. Nothing is posted."""
    rs = {r['key']: r for r in doc['hasPart'] if r.get('decision') == 'include'}
    ref = {}
    for k, r in rs.items():
        code = model.fs_ref(r.get('fairsharingRecord'))
        ref[k] = (f'new: {k}' if r.get('fairsharingMatch') != 'confirmed' or not code else
                  r['@id'] if not r['@id'].startswith('#') else f'{SITE}/{code}')
    out = {'records': [], 'incomplete': [], 'associations': [], 'collectionAdditions': [], 'notRegistrable': []}
    for k, r in rs.items():
        t = model.TYPES.get(r.get('type'))
        if r.get('fairsharingMatch') == 'confirmed':
            if not (r.get('fairsharing') or {}).get('inCollection'):
                out['collectionAdditions'].append({'key': k, 'name': r['name'], 'record': r['@id']})
            continue
        if not t or t[0] == 'Tool':
            out['notRegistrable'].append({'key': k, 'name': r['name'], 'type': r.get('type', ''),
                                          'suggestion': 'bio.tools (software) or FAIRassist (FAIR assessment tools)'})
            continue
        missing = [f for f in ('name', 'description', 'url') if not r.get(f)]
        if missing:
            out['incomplete'].append({'key': k, 'name': r['name'], 'missing': missing})
            continue
        metadata = {'name': r['name'], 'homepage': r['url'], 'description': r['description'],
                    'status': STATUS.get(r.get('maintained'), 'uncertain')}
        if r.get('alternateName'):
            metadata['abbreviation'] = r['alternateName'][0]
        if model._year(r):
            metadata['year_creation'] = model._year(r)
        out['records'].append({'key': k, 'fairsharing_record': {'metadata': metadata, 'record_type_id': t[2]},
                               'for_the_form': {'type': r['type'], 'organisations': r.get('creator', ''),
                                                'publication': r.get('dateSource', '')}})
    for x in model.relation_rows(doc):
        if x['subject'] not in rs or x['target'] not in rs or x['evidence'] == 'FAIRsharing':
            continue
        held = (rs[x['subject']].get('fairsharing') or {}).get('associations', [])
        if [x['hadRole'], (rs[x['target']].get('fairsharing') or {}).get('id')] in held:
            continue
        a, b = model.registry(rs[x['subject']]), model.registry(rs[x['target']])
        out['associations'].append({
            'subject': ref[x['subject']], 'relation': x['hadRole'], 'relation_id': model.RELATIONS[x['hadRole']][0],
            'target': ref[x['target']], 'enterable': (a, b) in model.ALLOWED.get(x['hadRole'], set()),
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
        'Incomplete': [{**x, 'missing': ', '.join(x['missing'])} for x in sub['incomplete']],
        'Associations': sub['associations'], 'Add to collection': sub['collectionAdditions'],
        'Not registrable': sub['notRegistrable'],
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
