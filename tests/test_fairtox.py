"""Tests for the fairtox package (standard-library unittest): uv run python -m unittest discover -s tests -v"""
import copy
import json
import os
import re
import tempfile
import unittest

from openpyxl import load_workbook

from fairtox import __version__, fairsharing, model, sheet, site

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fixture():
    rs = [
        {'key': 'exo', 'name': 'Exposure Ontology', 'alternateName': ['ExO'], 'decision': 'include',
         'type': 'Standard: terminology artefact', 'scope': 'Toxicology', 'stakeholder': 'In silico research',
         'subdomains': ['exposome'], 'datePublished': '2012-01', 'dateBasis': 'publication',
         'dateSource': 'https://doi.org/10.1021/es2033857', 'url': 'https://github.com/CTDbase/exposure-ontology',
         'manuscript': 'named', 'manuscriptEvidence': 'Data generation; L100', 'fairsharingRecord': 'FAIRsharing.6hna78',
         'fairsharingMatch': 'confirmed', 'maintained': 'active'},
        {'key': 'ctd', 'name': 'Comparative Toxicogenomics Database', 'alternateName': ['CTD'], 'decision': 'include',
         'type': 'Database: knowledgebase', 'scope': 'Toxicology', 'stakeholder': 'In silico research',
         'datePublished': '2004', 'dateBasis': 'publication', 'dateSource': 'https://doi.org/10.1093/nar/gkg044',
         'url': 'https://ctdbase.org', 'description': 'Curated chemical-gene-disease interactions.',
         'manuscript': 'absent', 'maintained': 'active',
         'qualifiedRelation': [{'relation': '#exo', 'hadRole': 'implements', 'evidence': 'FAIRsharing'}]},
        {'key': 'oecd_gd', 'name': 'OECD guidance on research data', 'decision': 'include', 'type': 'Policy: institution',
         'scope': 'Toxicology', 'stakeholder': 'Regulator', 'datePublished': '2026', 'manuscript': 'cited',
         'manuscriptEvidence': 'L190'},
        {'key': 'parc', 'name': 'PARC', 'decision': 'exclude', 'exclusionReason': 'E1', 'manuscript': 'named'},
        {'key': 'tool', 'name': 'A FAIR tool', 'decision': 'undecided', 'type': 'Tool', 'scope': 'FAIR'},
    ]
    return model.new_document(rs)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)


class ModelTest(TempDir):
    def test_fixture_is_valid_and_normalised(self):
        doc = model.normalise(fixture())
        errors, warnings = model.check(doc)
        self.assertEqual(errors, [])
        exo = next(r for r in doc['hasPart'] if r['key'] == 'exo')
        ctd = next(r for r in doc['hasPart'] if r['key'] == 'ctd')
        self.assertEqual(exo['@id'], 'https://doi.org/10.25504/FAIRsharing.6hna78')
        self.assertEqual(ctd['qualifiedRelation'][0]['relation'], exo['@id'])   # follows the @id change
        self.assertEqual(exo['phase'], 'Data Integration')
        self.assertNotIn('phase', next(r for r in doc['hasPart'] if r['key'] == 'tool'))
        # CTD (2004) implements ExO (2012) backwards in time, allowed because FAIRsharing asserts it
        self.assertFalse(any('first published later' in w for w in warnings))

    def test_each_bad_case_is_an_error(self):
        cases = [
            ('exo', 'scope', 'Toxicologie', 'not an allowed value'),
            ('exo', 'datePublished', '2012-13', 'YYYY'),
            ('exo', 'datePublished', '2999', 'YYYY'),
            ('parc', 'exclusionReason', '', 'exclusion reason is required'),
            ('ctd', 'stakeholder', '', 'stakeholder is required'),
            ('tool', 'stakeholder', 'Regulator', 'stakeholder is required'),
            ('parc', 'exclusionReason', 'E6', 'E6 needs Covered by'),
            ('exo', 'subdomains', ['ecotox'], 'sub-domain'),
            ('exo', 'url', 'ctdbase.org', 'http(s) URL'),
        ]
        for key, field, value, message in cases:
            doc = fixture()
            next(r for r in doc['hasPart'] if r['key'] == key)[field] = value
            errors, _ = model.check(model.normalise(doc))
            self.assertTrue(any(message in e for e in errors), (key, field, value, errors))

    def test_structural_errors(self):
        doc = fixture()
        doc['hasPart'].append(copy.deepcopy(doc['hasPart'][0]))
        self.assertTrue(any('duplicate key' in e for e in model.check(doc)[0]))
        doc = fixture()
        doc['hasPart'][1]['qualifiedRelation'] = [{'relation': '#nothing', 'hadRole': 'implements', 'evidence': 'curator'}]
        self.assertTrue(any('not in the dataset' in e for e in model.check(model.normalise(doc))[0]))
        doc = fixture()
        doc['hasPart'][1]['qualifiedRelation'][0]['hadRole'] = 'part_of'
        self.assertTrue(any('not an allowed label' in e for e in model.check(model.normalise(doc))[0]))

    def test_lane_rule(self):
        self.assertEqual(model.lane({'scope': 'Toxicology building on FAIR'}), 'FAIR infrastructure')
        self.assertEqual(model.lane({'scope': 'Life Sciences'}), 'Life Sciences infrastructure')
        self.assertEqual(model.lane({'scope': 'Toxicology', 'stakeholder': 'Wet-lab research'}), 'Data Generation')
        self.assertEqual(model.lane({'scope': 'Toxicology', 'stakeholder': 'In silico research'}), 'Tools & Integration')
        self.assertEqual(model.lane({'scope': 'Toxicology', 'stakeholder': 'Regulator'}), 'Application (regulatory)')

    def test_save_is_atomic_validated_and_skips_timestamp_only_changes(self):
        p = self.path('d.jsonld')
        self.assertTrue(model.save(fixture(), p))
        self.assertFalse(model.save(model.load(p), p))
        doc = model.load(p)
        doc['hasPart'][0]['exclusionReason'] = 'E9'
        with self.assertRaises(ValueError):
            model.save(doc, p)

    def test_diff_and_change_log(self):
        a = model.normalise(fixture())
        b = copy.deepcopy(a)
        next(r for r in b['hasPart'] if r['key'] == 'ctd')['datePublished'] = '2003'
        changes = model.diff(a, b)
        self.assertEqual(changes, [('ctd', 'datePublished', '2004', '2003')])
        log = self.path('changes.csv')
        model.log_changes(changes, 'round 1', 'test.xlsx', {'ctd': 'JH'}, path=log)
        with open(log) as f:
            self.assertIn('round 1,ctd,datePublished,2004,2003,JH,test.xlsx', f.read())


class SheetTest(TempDir):
    def build(self, doc):
        p = self.path('curation.xlsx')
        sheet.build(doc, p)
        return p

    def edit(self, p, column, key, value, tab='Resources'):
        wb = load_workbook(p)
        ws = wb[tab]
        head = {c.value: c.column for c in ws[1]}
        row = next(c.row for c in ws['A'] if c.value == key)
        ws.cell(row=row, column=head[column], value=value)
        wb.save(p)

    def test_round_trip_without_edits_changes_nothing(self):
        doc = model.normalise(fixture())
        new, changes, problems, notes, _ = sheet.ingest(doc, self.build(doc))
        self.assertEqual(problems, [])
        self.assertEqual(changes, [])

    def test_one_edit_gives_one_change(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'First published', 'ctd', '2003')
        self.edit(p, 'Reviewed by', 'ctd', 'JH')
        new, changes, problems, _, reviewers = sheet.ingest(doc, p)
        self.assertEqual(problems, [])
        self.assertEqual(changes, [('ctd', 'datePublished', '2004', '2003'), ('ctd', 'reviewedBy', '', 'JH')])
        self.assertEqual(reviewers, {'ctd': 'JH'})

    def test_bad_value_is_reported_with_its_cell(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        self.edit(p, 'Scope', 'ctd', 'Toxicologie')
        new, _, problems, _, _ = sheet.ingest(doc, p)
        self.assertIsNone(new)
        self.assertEqual(problems[0]['sheet'], 'Resources')
        self.assertRegex(problems[0]['cell'], r'^[A-Z]+\d+$')
        self.assertIn('allowed values', problems[0]['problem'])

    def test_stale_row_is_refused_unless_forced(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        moved = copy.deepcopy(doc)
        next(r for r in moved['hasPart'] if r['key'] == 'ctd')['note'] = 'changed elsewhere'
        self.edit(p, 'Name', 'ctd', 'CTD database')
        self.assertTrue(sheet.ingest(moved, p)[2])
        new, changes, problems, _, _ = sheet.ingest(moved, p, force=True)
        self.assertEqual(problems, [])
        self.assertIn(('ctd', 'name', 'Comparative Toxicogenomics Database', 'CTD database'), changes)

    def test_new_row_and_relation_removal(self):
        doc = model.normalise(fixture())
        p = self.build(doc)
        wb = load_workbook(p)
        ws = wb['Resources']
        head = {c.value: c.column for c in ws[1]}
        n = next(c.row for c in ws['B'] if c.row > 1 and c.value is None)
        for col, value in (('Name', 'New Resource'), ('Aliases', 'NewRes'), ('Decision', 'undecided')):
            ws.cell(row=n, column=head[col], value=value)
        rel = wb['Relations']
        rh = {c.value: c.column for c in rel[1]}
        rel.cell(row=2, column=rh['Keep'], value='remove')
        wb.save(p)
        new, changes, problems, notes, _ = sheet.ingest(doc, p)
        self.assertEqual(problems, [])
        self.assertIn(('newres', '(row)', '(new)', 'New Resource'), changes)
        self.assertIn(('ctd', 'relation', 'implements exo', '(removed)'), changes)


REST = {'data': {'id': '1716', 'type': 'fairsharing_records', 'attributes': {
    'name': 'Comparative Toxicogenomics Database', 'abbreviation': 'CTD', 'registry': 'Database',
    'record_type': 'knowledgebase', 'metadata': {'doi': '10.25504/FAIRsharing.h3tjtr', 'year_creation': 2004,
                                                 'status': 'ready', 'homepage': 'https://ctdbase.org/'},
    'record_associations': [{'record_assoc_label': 'implements', 'linked_record': {'id': 512, 'name': 'ExO'}}],
    'reverse_record_associations': [{'record_assoc_label': 'collects',
                                     'fairsharing_record': {'id': 3496, 'name': 'Toxicology'}}]}}}
PUBLIC = {'id': 512, 'name': 'Exposure Ontology', 'registry': 'Standard', 'type': 'terminology_artefact',
          'abbreviation': 'ExO', 'metadata': {'doi': '10.25504/FAIRsharing.6hna78', 'year_creation': 2012,
                                              'status': 'ready', 'homepage': 'https://github.com/CTDbase/exposure-ontology'},
          'tags': {'subjects': [{'label': 'Toxicology', 'iri': 'http://www.fairsharing.org/ontology/subject/SRAO_0000001'}]}}
NEW = {'id': 9999, 'name': 'New Tox Database', 'registry': 'Database', 'type': 'repository',
       'metadata': {'doi': '10.25504/FAIRsharing.zzz999', 'year_creation': 2019, 'status': 'ready',
                    'homepage': 'https://newtox.example.org', 'description': 'Example.'}}


class FairsharingTest(unittest.TestCase):
    def test_slim_reads_rest_and_public_shapes(self):
        c, e = fairsharing.slim(REST), fairsharing.slim(PUBLIC)
        self.assertEqual((c['id'], c['registry'], c['recordType'], c['yearCreation'], c['homepage']),
                         (1716, 'Database', 'knowledgebase', 2004, 'https://ctdbase.org/'))
        self.assertIn({'other': 512, 'otherName': 'ExO', 'label': 'implements', 'outgoing': True}, c['associations'])
        self.assertIn({'other': 3496, 'otherName': 'Toxicology', 'label': 'collects', 'outgoing': False},
                      c['associations'])
        self.assertEqual((e['registry'], e['recordType'], e['doi']), ('Standard', 'terminology_artefact',
                                                                       '10.25504/FAIRsharing.6hna78'))
        self.assertEqual(e['subjects'][0]['label'], 'Toxicology')

    def test_merge_proposes_adds_and_links(self):
        doc = fixture()
        ctd = next(r for r in doc['hasPart'] if r['key'] == 'ctd')
        del ctd['qualifiedRelation']
        model.normalise(doc)
        records = [fairsharing.slim(x) for x in (REST, PUBLIC, NEW)]
        report = fairsharing.merge(doc, records, members={1716, 9999}, today='2026-10-05')
        by = {r['key']: r for r in doc['hasPart']}
        self.assertEqual(by['exo']['fairsharing']['id'], 512)
        self.assertFalse(by['exo']['fairsharing']['inCollection'])
        self.assertEqual((by['ctd']['fairsharingMatch'], by['ctd']['fairsharingRecord']), ('to check', 'FAIRsharing.h3tjtr'))
        new = next(r for r in doc['hasPart'] if r.get('fairsharingRecord') == 'FAIRsharing.zzz999')
        self.assertEqual((new['decision'], new['manuscript'], new['type'], new['datePublished'], new['dateBasis']),
                         ('undecided', 'absent', 'Database: repository', '2019', 'FAIRsharing year'))
        q = by['ctd']['qualifiedRelation'][0]
        self.assertEqual((q['hadRole'], q['evidence'], q['relation']),
                         ('implements', 'FAIRsharing', 'https://doi.org/10.25504/FAIRsharing.6hna78'))
        self.assertTrue(any(line.startswith('new relation: ctd implements exo') for line in report))
        self.assertEqual(model.check(model.normalise(doc))[0], [])

    def test_submission_export(self):
        doc = model.normalise(fixture())
        sub = fairsharing.submission(doc)
        self.assertEqual([x['key'] for x in sub['incomplete']], ['oecd_gd'])          # no description, no homepage
        self.assertEqual(sub['incomplete'][0]['missing'], ['description', 'url'])
        ctd = next(x for x in sub['records'] if x['key'] == 'ctd')['fairsharing_record']
        self.assertEqual(ctd['record_type_id'], 2)
        self.assertEqual(set(ctd['metadata']) >= {'name', 'description', 'homepage', 'status'}, True)
        self.assertEqual(sub['collectionAdditions'][0]['key'], 'exo')
        self.assertEqual(sub['associations'], [])                                        # FAIRsharing evidence only


class SiteTest(TempDir):
    def test_build_embeds_data_lanes_and_metadata(self):
        doc = fixture()
        p = self.path('d.jsonld')
        model.save(doc, p)
        n, m = site.build(model.load(p), self.path('site'), dataset_path=p)
        self.assertEqual((n, m), (5, 1))
        html = open(self.path('site/index.html'), encoding='utf-8').read()
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(data['meta']['lanes'], model.LANES)
        self.assertEqual({x['src'] for x in data['links']}, {'exo'})
        self.assertIn('Toxicology infrastructure', html)
        schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(schema['@type'], 'Dataset')
        self.assertIn('fairsharing-attribution.svg', html)
        for f in ('fair-tox-ecosystem.jsonld', 'resources.csv', 'relations.csv'):
            self.assertTrue(os.path.exists(self.path(f'site/{f}')))


class RepositoryTest(unittest.TestCase):
    def test_one_version_everywhere(self):
        with open(os.path.join(ROOT, 'pyproject.toml')) as f:
            self.assertIn(f'version = "{__version__}"', f.read())
        with open(os.path.join(ROOT, 'CITATION.cff')) as f:
            self.assertIn(f'version: {__version__}', f.read())
        dataset = os.path.join(ROOT, model.DATASET)
        if os.path.exists(dataset):
            self.assertEqual(model.load(dataset)['version'], __version__)

    def test_every_vocabulary_value_is_documented(self):
        with open(os.path.join(ROOT, 'docs', 'data-dictionary.md'), encoding='utf-8') as f:
            text = f.read()
        for name, vocab in model.VOCABULARIES.items():
            for value in vocab:
                self.assertIn(value, text, f'{name}: {value}')

    def test_dataset_is_valid_and_parses_as_json_ld(self):
        dataset = os.path.join(ROOT, model.DATASET)
        if not os.path.exists(dataset):
            self.skipTest('no dataset yet')
        doc = model.load(dataset)
        self.assertEqual(model.check(doc)[0], [])
        try:
            import rdflib
        except ImportError:
            self.skipTest('rdflib is in the dev group')
        g = rdflib.Graph().parse(data=json.dumps(doc), format='json-ld')
        name = rdflib.URIRef('https://schema.org/name')
        self.assertGreaterEqual(len(set(g.subjects(name, None))), len(doc['hasPart']))


if __name__ == '__main__':
    unittest.main()
