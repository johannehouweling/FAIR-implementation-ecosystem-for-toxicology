"""Command line: `uv run fairtox <command>`. Run from the repository root."""
import argparse
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


def cmd_fetch(a):
    from fairtox import fairsharing
    login, password = os.environ.get('FAIRSHARING_LOGIN'), os.environ.get('FAIRSHARING_PASSWORD')
    if not login or not password:
        print('FAIRSHARING_LOGIN and FAIRSHARING_PASSWORD are not set; nothing fetched. '
              'Locally: uv run --env-file .env fairtox fetch')
        return 0
    doc = _load() if os.path.exists(model.DATASET) else model.new_document()
    before = json.loads(json.dumps(doc))
    try:
        sample = [int(x) for x in a.ids.split(',')] if a.ids else None
        report = fairsharing.fetch(doc, login, password, dry_run=a.dry_run or (len(sample) if sample else None),
                                   sample=sample)
    except fairsharing.FairsharingError as e:
        print('FAIRsharing:', e)
        return 1
    if not (a.dry_run or a.ids):
        changes = model.diff(before, model.normalise(doc))
        if model.save(doc):
            model.log_changes(changes, 'FAIRsharing refresh', 'FAIRsharing REST API')
    _report(report, a.report, 'FAIRsharing refresh')
    return 0


def _report(lines, path, title):
    for line in lines:
        print(line)
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f'## {title}\n\n' + ''.join(f'- {line}\n' for line in lines) + '\n')


def cmd_sheet(a):
    from fairtox import sheet
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    n, m = sheet.build(_load(), a.out)
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
    n, m = site.build(_load(), a.outdir, internal=a.internal)
    print(f'{a.outdir}/index.html: {n} resources, {m} relations' + (' (internal curation view, never publish)' if a.internal else ''))
    return 0


def cmd_export(a):
    from fairtox import fairsharing
    counts = fairsharing.write_submission(_load(), a.outdir)
    print(f'{a.outdir}/fairsharing-submission.json and .xlsx: ' + ', '.join(f'{k} {v}' for k, v in counts.items()))
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
    s = sub.add_parser('fetch', help='pull the FAIRsharing Toxicology collection and linked records')
    s.add_argument('--dry-run', type=int, metavar='N', help='read N records and print their fields; write nothing')
    s.add_argument('--report', metavar='FILE', help='append the report to a markdown file')
    s.add_argument('--ids', metavar='ID,ID', help='dry run on these FAIRsharing record ids')
    s.set_defaults(run=cmd_fetch)
    s = sub.add_parser('sheet', help='build the curation workbook')
    s.add_argument('out', help='path of the .xlsx to write')
    s.set_defaults(run=cmd_sheet)
    s = sub.add_parser('ingest', help='read a curated workbook back into the dataset')
    s.add_argument('workbook')
    s.add_argument('--force', action='store_true', help='apply rows that changed in the dataset after the sheet was made')
    s.add_argument('--round', default='curation', help='name of the curation round for the change log')
    s.set_defaults(run=cmd_ingest)
    s = sub.add_parser('site', help='build the static dashboard (the public page; --internal for the curation view)')
    s.add_argument('outdir')
    s.add_argument('--internal', action='store_true', help='every row with the curation view; local only, never publish')
    s.set_defaults(run=cmd_site)
    s = sub.add_parser('export-fairsharing', help='write what could be added to FAIRsharing (nothing is posted)')
    s.add_argument('outdir')
    s.set_defaults(run=cmd_export)
    s = sub.add_parser('draft-check', help='check manuscript line references against a draft export (read-only)')
    s.add_argument('draft')
    s.set_defaults(run=cmd_draft_check)
    a = p.parse_args(argv)
    sys.exit(a.run(a))
