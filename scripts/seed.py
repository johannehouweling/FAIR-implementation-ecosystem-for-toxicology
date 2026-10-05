"""One-off build of the first dataset version, kept for provenance.

Sources:
1. scripts/seed-manuscript.csv: every named entity in manuscript draft (8), screened against the criteria in
   docs/inclusion-criteria.md (two independent extraction passes, reconciled and verified).
2. The FAIRsharing Toxicology collection (record 3496): membership as read from fairsharing.org on 1 Oct 2026
   (previous inventory, fairsharing_3496_review.csv) until the signed-in API pull (`fairtox fetch`) replaces it;
   record data from FAIRsharing's public record JSON.
3. The previous inventory (FAIR_tox, audit of 2 Oct 2026), as evidence only: first-release years with their sources,
   DOIs, FAIRsharing records, maintenance status and relations. Everything taken over is marked to verify.

Run from the repository root:
    uv run python scripts/seed.py <FAIR_tox folder> "<draft (8) .txt>"
"""
import csv
import datetime as dt
import hashlib
import os
import re
import sys
import time

from fairtox import fairsharing, model

# Relations of the previous inventory, (earlier, later) -> label, read "later label earlier". From the 3 Oct 2026
# plan in FAIR_tox (docs/superpowers/plans/2026-10-03-fair-tox-jsonld-tree.md), relabelled to the six labels used here.
ROLES = {
    ('fairprinc', 'fipwiz'): 'implements', ('fipwiz', 'fairaop'): 'implements',
    ('fairsharing', 'toxcoll'): 'part_of', ('cookbook', 'recipe_bao'): 'part_of',
    ('cookbook', 'recipe_aop'): 'part_of', ('rdmkit', 'rdmtox'): 'part_of',
    ('bao', 'recipe_bao'): 'implements', ('gd211', 'toxtemp'): 'implements',
    ('toxtemp', 'tta'): 'implements', ('tg236', 'intob'): 'implements',
    ('biostudies', 'eutr_ki'): 'related_to', ('miame', 'arraytrack'): 'implements',
    ('isatab', 'dixa'): 'implements', ('isatab', 'isanano'): 'extends',
    ('maqc', 'rodaf'): 'implements', ('seqc', 'rodaf'): 'implements',
    ('rodaf', 'oorf'): 'related_to', ('opentox', 'enm_db'): 'implements',
    ('bao', 'enm_ont'): 'extends', ('obi', 'enm_ont'): 'extends',
    ('chebi', 'enm_ont'): 'extends', ('cl', 'enm_ont'): 'extends',
    ('nsc', 'enm_ont'): 'implements', ('enm_db', 'nanocommons'): 'extends',
    ('enm_ont', 'nanoaop'): 'implements', ('aopwikirdf', 'nanoaop'): 'extends',
    ('oht', 'iuclid'): 'implements', ('send', 'etransafe'): 'implements',
    ('aopfw', 'aopwiki'): 'implements', ('wikipathways', 'aopwiki'): 'related_to',
    ('aopwiki', 'aopo'): 'extends', ('aopwiki', 'aopdb'): 'extends',
    ('aopwiki', 'aopwikirdf'): 'extends', ('aopdb', 'aopdbrdf'): 'extends',
    ('aopo', 'aopdbrdf'): 'implements', ('aopdbrdf', 'aopwikirdf'): 'related_to',
    ('aopwikirdf', 'fairaop'): 'recommends', ('fairaop', 'aoproadmap'): 'extends',
    ('aopwiki', 'aoplink'): 'related_to', ('openrisknet', 'aoplink'): 'part_of',
    ('sbml', 'fairmodels'): 'related_to', ('sedml', 'fairmodels'): 'related_to',
    ('omex', 'fairmodels'): 'related_to', ('miriam', 'fairmodels'): 'related_to',
    ('fairmodels', 'fairlite'): 'extends', ('sbml', 'cure'): 'recommends',
    ('omex', 'cure'): 'recommends', ('miriam', 'cure'): 'recommends',
    ('biomodels', 'cure'): 'recommends', ('sbml', 'pbk'): 'extends',
    ('chebi', 'aopwikirdf'): 'implements', ('sbml', 'biomodels'): 'implements',
    ('sbml', 'sedml'): 'related_to', ('sbml', 'omex'): 'related_to',
    ('sbml', 'miriam'): 'related_to', ('biomodels', 'fairmodels'): 'related_to',
    ('fairprinc', 'cure'): 'extends', ('fairprinc', 'fairmodels'): 'implements',
    ('fairprinc', 'parc'): 'implements', ('fipwiz', 'parcfip'): 'implements',
    ('enm_ont', 'enm_db'): 'implements', ('enm_ont', 'nanocommons'): 'implements',
    ('isatab', 'enm_db'): 'implements', ('isanano', 'nanocommons'): 'implements',
    ('aopwiki', 'aopnet'): 'related_to', ('miame', 'miametox'): 'extends',
    ('exo', 'ecto'): 'extends', ('oht', 'echemportal'): 'implements',
    ('tggates', 'dixa'): 'shares_data_with',
}
RELABEL = {'part_of': 'extends', 'shares_data_with': 'related_to'}
# FAIRsharing record ids of the previous inventory (checked against fairsharing.org on 2 and 5 Oct 2026).
FS_IDS = {
    'fairprinc': 1236, 'fairsharing': 2521, 'toxcoll': 3496, 'rdmtox': 7474, 'isanano': 1339, 'sbml': 18,
    'sedml': 80, 'omex': 1161, 'miriam': 988, 'biomodels': 1846, 'bao': 874, 'obi': 1488, 'chebi': 1036,
    'cl': 1004, 'enm_db': 2282, 'enm_ont': 493, 'nanocommons': 2979, 'wikipathways': 1698, 'miame': 96,
    'isatab': 1497, 'oorf': 5501, 'miate': 1111, 'mitnano': 5228, 'erm': 816, 'exo': 512, 'ecto': 4861,
    'expexplorer': 4722, 'ipchem': 5633, 'ecotox': 4704, 'ectothes': 4460, 'miametox': 1258, 'ctd': 1716,
    'tggates': 2604, 'comptox': 2480, 'qsardb': 4904, 'echemportal': 4724,
}
PREVIOUS_NOTE = 'Year, sources and FAIRsharing record taken over from the previous inventory (2 Oct 2026); to verify.'


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def split(text, sep=';'):
    return [x.strip() for x in str(text or '').split(sep) if x.strip()]


def line_refs(lines):
    nums = sorted({int(x) for x in re.findall(r'\d+', lines or '')})
    out, start = [], None
    for i, n in enumerate(nums):
        if start is None:
            start = n
        if i + 1 == len(nums) or nums[i + 1] != n + 1:
            out.append(f'L{start}' if start == n else f'L{start}-{n}')
            start = None
    return ', '.join(out)


def first_url(text):
    for part in re.split(r'[;\s]+', str(text or '')):
        part = part.strip().rstrip('.,')
        if part.startswith('http'):
            return part
        if re.match(r'^10\.\d{4,}/', part):
            return 'https://doi.org/' + part
    return ''


def manuscript_rows(path):
    rows = read_csv(path)
    keys = {r['key'] for r in rows}
    names = {}
    for r in rows:
        for n in [r['name']] + split(r['aliases']):
            names.setdefault(fairsharing.norm_name(n), r['key'])
    out = []
    for r in rows:
        res = {'key': r['key'], 'name': r['name'], 'alternateName': split(r['aliases']), 'decision': r['decision'],
               'type': r['type'], 'scope': r['scope'], 'stakeholder': r['stakeholder'] if r['scope'] == 'Toxicology' else '',
               'subdomains': [s for s in split(r['subdomains']) if s in model.SUBDOMAINS], 'creator': r['creator'],
               'url': r['homepage'] if r['homepage'].startswith('http') else '', 'manuscript': r['manuscript'],
               'manuscriptEvidence': '; '.join(x for x in (r['section'], line_refs(r['lines'])) if x)}
        if r['decision'] == 'exclude':
            res['exclusionReason'] = r['exclusion_code']
            cover = r['covered_by'].strip()
            if r['exclusion_code'] == 'E6':
                key = cover if cover in keys else names.get(fairsharing.norm_name(cover))
                if key and key != r['key']:
                    res['coveredBy'] = key
                else:
                    res.update(decision='undecided', exclusionReason='',
                               note=f'Proposed as E6 (covered by {cover!r}), but that row was not found.')
        if r['scope'] == 'Toxicology' and not r['stakeholder']:
            res['scope'] = ''
            res['note'] = (res.get('note', '') + ' Scope Toxicology proposed without a stakeholder.').strip()
        out.append(res)
    return out


def add_previous_evidence(resources, old_dir):
    nodes = {r['id']: r for r in read_csv(os.path.join(old_dir, 'nodes.csv'))}
    audit = {r['id']: r for r in read_csv(os.path.join(old_dir, 'audit.csv'))}
    for r in resources:
        n, a = nodes.get(r['key']), audit.get(r['key'])
        if not n or not a:
            continue
        r['datePublished'] = r.get('datePublished') or n['year']
        r['dateSource'] = r.get('dateSource') or first_url(a['doi_or_url'])
        if not r.get('url'):
            u = first_url(a['doi_or_url'])
            if u and 'doi.org' not in u:
                r['url'] = u
        if a['maintained'] in model.MAINTAINED:
            r['maintained'] = a['maintained']
        ref = model.fs_ref(a['fairsharing_url']) or (str(FS_IDS[r['key']]) if r['key'] in FS_IDS else '')
        if ref:
            r['fairsharingRecord'], r['fairsharingMatch'] = ref, 'confirmed'
        r['note'] = (r.get('note', '') + ' ' + PREVIOUS_NOTE).strip()


def add_previous_relations(resources, old_dir):
    by_key = {r['key']: r for r in resources if r['decision'] != 'exclude'}
    count = 0
    for e in read_csv(os.path.join(old_dir, 'edges.csv')):
        earlier, later = e['src'], e['dst']
        label = ROLES.get((earlier, later))
        if not label or earlier not in by_key or later not in by_key:
            continue
        label = RELABEL.get(label, label)
        if e['status'] in ('c', 'n'):
            evidence = 'manuscript'
        elif 'fairsharing' in e['note'].lower():
            evidence = 'FAIRsharing'
        else:
            evidence = 'curator'
        q = {'relation': '#' + earlier, 'hadRole': label, 'evidence': evidence,
             'source': 'previous inventory (2 Oct 2026)', 'note': (e['note'] + ' To verify.').strip()}
        by_key[later].setdefault('qualifiedRelation', []).append(q)
        count += 1
    return count


def main(old_dir, draft):
    today = dt.date.today().isoformat()
    resources = manuscript_rows('scripts/seed-manuscript.csv')
    add_previous_evidence(resources, old_dir)
    n_rel = add_previous_relations(resources, old_dir)
    with open(draft, 'rb') as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    doc = model.new_document(resources)
    doc['sources'] = {
        'manuscript': {'name': 'ELIXIR Toxicology Community paper, draft (8)', 'file': os.path.basename(draft),
                       'dateModified': dt.date.fromtimestamp(os.path.getmtime(draft)).isoformat(), 'sha256': digest},
        'previous': {'name': 'FAIR_tox inventory and audit', 'date': '2026-10-02', 'use': 'evidence only, to verify'},
    }
    model.normalise(doc)
    members = {int(r['fairsharing_id']) for r in read_csv(os.path.join(old_dir, 'fairsharing_3496_review.csv'))
               if r['relation'] == 'member'}
    ids = set(members)
    for r in doc['hasPart']:
        ref = model.fs_ref(r.get('fairsharingRecord'))
        if ref:
            ids.add(ref)
    records = []
    for ref in sorted(ids, key=str):
        try:
            records.append(fairsharing.slim(fairsharing.lookup(ref)))
        except fairsharing.FairsharingError as e:
            print(f'FAIRsharing {ref}: {e}')
        time.sleep(0.3)
    report = fairsharing.merge(doc, records, members, today)
    doc['sources']['fairsharing'] = {
        'collection': model.COLLECTION_DOI, 'members': len(members),
        'method': 'membership read from fairsharing.org on 2026-10-01; record data from the public FAIRsharing '
                  'record JSON; replaced by the signed-in API pull (fairtox fetch)',
        'retrieved': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    model.save(doc)
    print(f'{len(doc["hasPart"])} resources ({len(resources)} from the manuscript), {n_rel} relations from the '
          f'previous inventory, {len(records)} FAIRsharing records read')
    for line in report:
        print(' ', line)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
