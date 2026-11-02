"""Command line: `uv run fairtox <command>`. Run from the repository root."""
import argparse
import collections
import csv
import json
import os
import sys

from fairtox import __version__, model, web


def _load():
    return model.load(model.DATASET)


def cmd_validate(a):
    errors, warnings = model.check(_load())
    for e in errors:
        print('error:', e)
    for w in warnings:
        print('warning:', w)
    print(f'{len(errors)} errors, {len(warnings)} warnings')
    return 1 if errors or (a.strict and warnings) else 0


def _fairsharing(a, search_unchecked=False):
    """FAIRsharing, read with FAIRSHARING_LOGIN and FAIRSHARING_PASSWORD or, with --offline, from the local cache."""
    from fairtox import fairsharing
    return fairsharing.read(os.environ.get('FAIRSHARING_LOGIN'), os.environ.get('FAIRSHARING_PASSWORD'), a.offline,
                            search_unchecked)


def _enriched(a):
    """The dataset with FAIRsharing added in memory, for the site, the sheet and the submission export."""
    from fairtox import fairsharing
    data = _fairsharing(a)
    return fairsharing.enrich(_load(), data)


def cmd_fairsharing(a):
    from fairtox import fairsharing
    data, doc = _fairsharing(a, search_unchecked=True), _load()
    before = json.loads(json.dumps(doc))
    lines = fairsharing.curate(doc, data)
    changes = model.diff(before, model.normalise(doc))
    before = json.loads(json.dumps(doc))
    lines += fairsharing.check(doc, data)
    checked = model.diff(before, model.normalise(doc))
    _report([f"{len(data['records'])} FAIRsharing records read on {data['retrieved']}; {len(data['members'])} "
             f"collection members; {len(data.get('searches', {}))} unchecked rows searched"] + lines,
            a.report, 'FAIRsharing')
    if a.apply:
        if model.save(doc):
            for done, source in ((changes, 'FAIRsharing Toxicology collection'),
                                 (checked, f'{fairsharing.API}/search/fairsharing_records')):
                model.log_changes(done, f"fairsharing import {data['retrieved']}", source,
                                  dict.fromkeys((c[0] for c in done), 'fairtox fairsharing'))
        print(f'{len(changes) + len(checked)} changes applied and logged in {model.CHANGES}')
    return 0


def _report(lines, path, title):
    for line in lines:
        print(line)
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f'## {title}\n\n' + ''.join(f'- {line}\n' for line in lines) + '\n')


def cmd_sheet(a):
    from fairtox import fip, sheet
    doc = fip.enrich(_enriched(a), fip.read(a.offline))
    with open(model.CHANGES, newline='', encoding='utf-8') as f:    # rows that co-authors added in the sheet
        added = {r['key'] for r in csv.DictReader(f)
                 if r['field'] == '(row)' and r['source'] == 'curation-sheet.xlsx'}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    n, m = sheet.build(doc, a.out, added=added)
    print(f'{a.out}: {n} resources, {m} relations')
    return 0


def cmd_ingest(a):
    from fairtox import sheet
    doc, source = _load(), os.path.basename(a.workbook)
    last = {}                                                       # rows and relations last changed by reading
    with open(model.CHANGES, newline='', encoding='utf-8') as f:    # this sheet back
        for r in csv.DictReader(f):
            rel = r['field'].startswith('relation')
            last[(r['key'], *model.relation_of(r['field'], r['old'], r['new'])) if rel else r['key']] = r['source']
    read_back = {k for k, s in last.items() if s == source}
    new, changes, problems, notes, reviewers = sheet.ingest(doc, a.workbook, force=a.force, read_back=read_back)
    path = os.path.join('build', 'ingest-errors.csv')
    if problems:
        os.makedirs('build', exist_ok=True)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, ['sheet', 'cell', 'column', 'value', 'problem'])
            w.writeheader()
            w.writerows(problems)
    cell = lambda p: f"{p['sheet']}!{' '.join(filter(None, (p['cell'], p['column'], p['value'])))}: {p['problem']}"
    if new is None:
        _report([f'{len(problems)} problems, nothing changed. The full list is in {path}.',
                 *(f'problem: {cell(p)}' for p in problems[:30]), *(f'note: {n}' for n in notes)],
                a.report, 'Curation sheet')
        return 1
    model.save(new)
    model.log_changes(changes, a.round, source, reviewers)

    def item(c):                                            # the row, or the relation, a change is about
        if len(c) < 5:
            return c[0]
        return f'{c[0]} {" ".join(model.relation_of(*c[1:4]))}'
    by = lambda c: c[4] if len(c) > 4 else reviewers.get(c[0], '')
    before = {(x['subject'], x['hadRole'], x['target']): x['reviewedBy'] for x in model.relation_rows(doc)}
    resigned = {item(c) for c in changes if c[1] in ('reviewedBy', '(row)') or c[1].endswith(' reviewedBy')
                or c[2] == '(new)' or c[3] == '(removed)' and c[4] != before.get(
                    (c[0], *model.relation_of(*c[1:4])), '')}  # signed in this read-back
    unsigned = sorted({item(c) for c in changes if not by(c)})
    kept = sorted({f'{item(c)} ({by(c)})' for c in changes if by(c) and item(c) not in resigned})
    included, rels = [r for r in new['hasPart'] if r.get('decision') == 'include'], model.relation_rows(new)
    lines = [f'{len(changes)} changes read back and logged in {model.CHANGES}',
             *(f'waits until fixed: {cell(p)}' for p in problems),
             *([f"changed without initials: {', '.join(unsigned)}"] if unsigned else []),
             *([f"changed under the initials already in Reviewed by: {', '.join(kept)}"] if kept else []),
             f"signed by a curator: {sum(bool(r.get('reviewedBy')) for r in included)} of {len(included)} included "
             f"rows, {sum(bool(x['reviewedBy']) for x in rels)} of {len(rels)} relations",
             *(f'note: {n}' for n in notes)]
    _report(lines, a.report, 'Curation sheet')
    _, warnings = model.check(new)
    print(f'{len(warnings)} warnings remain (see: uv run fairtox validate)')
    return 0


def cmd_site(a):
    from fairtox import site
    n, m = site.build(_enriched(a), a.outdir, offline=a.offline)
    print(f'{a.outdir}/index.html: {n} resources, {m} relations')
    return 0


def cmd_export(a):
    from fairtox import fairsharing
    counts = fairsharing.write_submission(_enriched(a), a.outdir)
    print(f'{a.outdir}/fairsharing-submission.json and .xlsx: ' + ', '.join(f'{k} {v}' for k, v in counts.items()))
    return 0


def cmd_fip(a):
    from fairtox import fip
    data = fip.read(offline=a.offline)
    doc = _load()
    matches = fip.match(doc, data)
    rows = fip.report(doc, data, matches)
    for key, f in data['fips'].items():
        n = sum(1 for x in data['declarations'] if x['fip'] == key and x['target'])
        print(f"{f['label']}: {n} declarations, {len(f['noChoice'])} no choice, "
              f"{f['invalidated']} invalidated and skipped")
    methods = collections.Counter(how for _, how in matches.values())
    print(f'{len(matches)} declared resources, matched by ' + ', '.join(f'{k} {v}' for k, v in sorted(methods.items())))
    e1 = {r['key'] for r in doc['hasPart'] if r.get('exclusionReason') == 'E1'}
    hits = [r for r in rows if r['kind'] == 'FAIR-Implementation-Community' and r['key'] in e1]
    print(f"{len(data['fic'])} valid FAIR Implementation Communities; {len(hits)} match rows excluded as E1 "
          '(identity check)')
    print(f'{fip.REPORT}: {len(rows)} rows')
    if a.report:
        fip.convergence(data)
        print(f'{fip.CONVERGENCE} written')
    if a.apply:
        before = json.loads(json.dumps(doc))
        changes = model.diff(before, model.normalise(fip.curate(doc, data, matches)))
        if model.save(doc):
            model.log_changes(changes, f"fip import {data['retrieved']}", 'FIP nanopublications',
                              dict.fromkeys((c[0] for c in changes), 'fairtox fip'))
        print(f'{len(changes)} changes applied and logged in {model.CHANGES}')
    return 0


def cmd_query(a):
    import rdflib
    from fairtox import site
    doc = model.normalise(_load())
    ids = {r['@id'] for r in doc['hasPart'] if model.in_figure(r)}
    doc = site.public(doc)                                  # the published dataset, cut to the resources in the figure
    doc['hasPart'] = [{**r, 'qualifiedRelation': [q for q in r.get('qualifiedRelation', []) if q['relation'] in ids]}
                      for r in doc['hasPart'] if r['@id'] in ids]
    g = rdflib.Graph().parse(data=model.dumps(doc), format='json-ld')
    with open(a.query, encoding='utf-8') as f:
        sys.stdout.write(g.query(f.read()).serialize(format='csv').decode('utf-8'))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog='fairtox', description=__doc__)
    p.add_argument('--version', action='version', version=__version__)
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('validate', help='check the dataset')
    s.add_argument('--strict', action='store_true', help='fail on warnings too')
    s.set_defaults(run=cmd_validate)
    s = sub.add_parser('fairsharing', help='read the FAIRsharing Toxicology collection and report its new members, '
                                           'and search FAIRsharing for the rows never checked against it; '
                                           'FAIRsharing record data are never stored: the builds read them')
    s.add_argument('--offline', action='store_true', help='read only the local cache in build/fairsharing')
    s.add_argument('--report', metavar='FILE', help='also append the report to a markdown file')
    s.add_argument('--apply', action='store_true', help='store new collection members as undecided rows or proposed '
                                                        'matches, and the search results as proposed matches or no '
                                                        'record (after reviewing the report)')
    s.set_defaults(run=cmd_fairsharing)
    s = sub.add_parser('sheet', help='build the curation workbook')
    s.add_argument('out', help='path of the .xlsx to write')
    s.add_argument('--offline', action='store_true', help='read FAIRsharing and the FIP declarations from the local '
                                                          'caches in build/fairsharing and build/fip')
    s.set_defaults(run=cmd_sheet)
    s = sub.add_parser('ingest', help='read a curated workbook back into the dataset')
    s.add_argument('workbook')
    s.add_argument('--force', action='store_true', help='apply rows that changed in the dataset after the sheet was made')
    s.add_argument('--round', default='curation', help='name of the curation round for the change log')
    s.add_argument('--report', metavar='FILE', help='also append the report to a markdown file')
    s.set_defaults(run=cmd_ingest)
    s = sub.add_parser('site', help='build the static dashboard')
    s.add_argument('outdir')
    s.add_argument('--offline', action='store_true', help='read FAIRsharing and the FIP declarations from the local '
                                                          'caches in build/fairsharing and build/fip')
    s.set_defaults(run=cmd_site)
    s = sub.add_parser('export-fairsharing', help='write what could be added to FAIRsharing (nothing is posted)')
    s.add_argument('outdir')
    s.add_argument('--offline', action='store_true', help='read FAIRsharing from the local cache in build/fairsharing')
    s.set_defaults(run=cmd_export)
    s = sub.add_parser('fip', help="read the toxicology FIPs' declarations and write the match report; the "
                                   'declarations are never stored: the site build reads them')
    s.add_argument('--offline', action='store_true', help='read only the local cache in build/fip')
    s.add_argument('--report', action='store_true', help='also write the convergence table, build/fip-convergence.md')
    s.add_argument('--apply', action='store_true', help='store links to the declared resources and undecided rows for '
                                                        'new ones and their communities (after reviewing the report)')
    s.set_defaults(run=cmd_fip)
    s = sub.add_parser('query', help='run a SPARQL query (queries/*.rq) over the resources in the figure; CSV out')
    s.add_argument('query')
    s.set_defaults(run=cmd_query)
    a = p.parse_args(argv)
    try:
        sys.exit(a.run(a))
    except web.Unreadable as e:
        sys.exit(f'Nothing was built or changed: {e}')
