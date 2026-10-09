"""Command line: `uv run fairtox <command>`. Run from the repository root."""
import argparse
import collections
import csv
import json
import os
import re
import sys

from fairtox import __version__, model


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


def _fairsharing(a):
    """FAIRsharing, read with FAIRSHARING_LOGIN and FAIRSHARING_PASSWORD or, with --offline, from the local cache. The
    command stops when it cannot be read."""
    from fairtox import fairsharing
    try:
        return fairsharing.read(os.environ.get('FAIRSHARING_LOGIN'), os.environ.get('FAIRSHARING_PASSWORD'), a.offline)
    except fairsharing.FairsharingError as e:
        sys.exit(f'FAIRsharing could not be read, so nothing was built or changed: {e}')


def _enriched(a):
    """The dataset with FAIRsharing added in memory, for the site, the sheet and the submission export."""
    from fairtox import fairsharing
    data = _fairsharing(a)
    return fairsharing.enrich(_load(), data)


def cmd_fairsharing(a):
    from fairtox import fairsharing
    data, doc = _fairsharing(a), _load()
    before = json.loads(json.dumps(doc))
    lines = fairsharing.curate(doc, data)
    changes = model.diff(before, model.normalise(doc))
    _report([f"{len(data['records'])} FAIRsharing records read on {data['retrieved']}; {len(data['members'])} "
             'collection members'] + lines, a.report, 'FAIRsharing')
    if a.apply:
        if model.save(doc):
            model.log_changes(changes, f"fairsharing import {data['retrieved']}", 'FAIRsharing Toxicology collection',
                              dict.fromkeys((c[0] for c in changes), 'fairtox fairsharing'))
        print(f'{len(changes)} changes applied and logged in {model.CHANGES}')
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
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    n, m = sheet.build(doc, a.out)
    print(f'{a.out}: {n} resources, {m} relations')
    return 0


def cmd_ingest(a):
    from fairtox import sheet
    doc = _load()
    new, changes, problems, notes, reviewers = sheet.ingest(doc, a.workbook, force=a.force)
    for n in notes:
        print('note:', n)
    if problems:
        path = os.path.join('build', 'ingest-errors.csv')
        os.makedirs('build', exist_ok=True)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, ['sheet', 'cell', 'column', 'value', 'problem'])
            w.writeheader()
            w.writerows(problems)
        for p in problems[:30]:
            print(f"problem: {p['sheet']}!{p['cell']} {p['column']}: {p['problem']}")
        print(f'{len(problems)} problems, nothing changed. The full list is in {path}.')
        return 1
    model.save(new)
    model.log_changes(changes, a.round, os.path.basename(a.workbook), reviewers)
    print(f'{len(changes)} changes applied and logged in {model.CHANGES}')
    _, warnings = model.check(new)
    print(f'{len(warnings)} warnings remain (see: uv run fairtox validate)')
    return 0


def cmd_site(a):
    from fairtox import site
    n, m = site.build(_enriched(a), a.outdir, internal=a.internal, offline=a.offline)
    print(f'{a.outdir}/index.html: {n} resources, {m} relations' + (' (internal curation view, never publish)' if a.internal else ''))
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


def lines_of(evidence):
    """Line numbers in a manuscript evidence text such as 'AOP section; L117, L126-129, [ag] L391'."""
    out = set()
    for a, b in re.findall(r'L(\d+)(?:\s*[-–]\s*L?(\d+))?', evidence or ''):
        out.update(range(int(a), int(b or a) + 1))
    return out


def names_of(r):
    """A resource's name and aliases, plus the parts of 'Long name (ABBR)'."""
    out = set()
    for n in [r['name']] + r.get('alternateName', []):
        out.add(n)
        m = re.match(r'^(.*?)\s*\(([^)]+)\)\s*$', n)
        if m:
            out.update({m.group(1).strip(), m.group(2).strip()})
    return {n for n in out if len(n) >= 2}


def mentions(text, names):
    """Line numbers (1-based) where any of the names occurs as a word; short names are matched case-sensitively."""
    hits = set()
    for name in names:
        flags = 0 if len(name) <= 5 else re.IGNORECASE
        pattern = re.compile(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', flags)
        hits.update(i for i, line in enumerate(text, 1) if pattern.search(line))
    return hits


def cmd_draft_check(a):
    with open(a.draft, encoding='utf-8') as f:
        text = f.read().splitlines()
    lines_wrong, described, newly_named = [], [], []
    for r in _load()['hasPart']:
        found = mentions(text, names_of(r))
        cited = lines_of(r.get('manuscriptEvidence'))
        if r.get('manuscript', 'absent') != 'absent':
            if not found:
                described.append(r['key'])
            elif not cited or cited - found:
                lines_wrong.append(f"{r['key']}: cited at {sorted(cited)}, name found at {sorted(found)[:10]}")
        elif found and r.get('decision') != 'exclude':
            newly_named.append(f"{r['key']}: marked absent, but named at lines {sorted(found)[:10]}")
    for title, items in (('Check the line numbers (the name occurs, but not at every cited line)', lines_wrong),
                         ('Marked absent but named in this draft', newly_named)):
        print(f'{title}: {len(items)}')
        for item in items:
            print('  ' + item)
    print(f'Described rather than named, so not checked by name: {len(described)}')
    print('  ' + ', '.join(described))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog='fairtox', description=__doc__)
    p.add_argument('--version', action='version', version=__version__)
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('validate', help='check the dataset')
    s.add_argument('--strict', action='store_true', help='fail on warnings too')
    s.set_defaults(run=cmd_validate)
    s = sub.add_parser('fairsharing', help='read the FAIRsharing Toxicology collection and report its new members; '
                                           'FAIRsharing record data are never stored: the builds read them')
    s.add_argument('--offline', action='store_true', help='read only the local cache in build/fairsharing')
    s.add_argument('--report', metavar='FILE', help='also append the report to a markdown file')
    s.add_argument('--apply', action='store_true', help='store new collection members as undecided rows or proposed '
                                                        'matches (after reviewing the report)')
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
    s.set_defaults(run=cmd_ingest)
    s = sub.add_parser('site', help='build the static dashboard (the public page; --internal for the curation view)')
    s.add_argument('outdir')
    s.add_argument('--internal', action='store_true', help='every row with the curation view; local only, never publish')
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
    s.add_argument('--report', action='store_true', help='also write the convergence table, docs/fip-convergence.md')
    s.add_argument('--apply', action='store_true', help='store links to the declared resources and undecided rows for '
                                                        'new ones and their communities (after reviewing the report)')
    s.set_defaults(run=cmd_fip)
    s = sub.add_parser('draft-check', help='check manuscript line references against a draft export (read-only)')
    s.add_argument('draft')
    s.set_defaults(run=cmd_draft_check)
    a = p.parse_args(argv)
    sys.exit(a.run(a))
