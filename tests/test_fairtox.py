"""Tests for the fairtox package (standard-library unittest): uv run python -m unittest discover -s tests -v"""
import copy
import csv
import io
import json
import os
import pathlib
import re
import tempfile
import unittest
import warnings
from unittest import mock

from openpyxl import load_workbook

from fairtox import __version__, cli, fairsharing, fip, model, sheet, site

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fixture():
    rs = [
        {'key': 'exo', 'name': 'Exposure Ontology', 'alternateName': ['ExO'], 'decision': 'include',
         'type': 'Standard: terminology artefact', 'scope': 'Toxicology', 'phase': 'Data integration',
         'span': ['Data integration'],
         'stakeholders': ['In silico research'], 'subdomains': ['exposome'], 'datePublished': '2012-01', 'dateBasis': 'publication',
         'dateSource': 'https://doi.org/10.1021/es2033857', 'url': 'https://github.com/CTDbase/exposure-ontology',
         'manuscript': 'named', 'manuscriptEvidence': 'Data generation; L100', 'fairsharingRecord': 'FAIRsharing.6hna78',
         'fairsharingMatch': 'confirmed', 'maintained': 'active'},
        {'key': 'ctd', 'name': 'Comparative Toxicogenomics Database', 'alternateName': ['CTD'], 'decision': 'include',
         'type': 'Database: knowledgebase', 'scope': 'Toxicology', 'phase': 'Data integration',
         'span': ['Data integration', 'Regulatory assessment'],
         'stakeholders': ['In silico research', 'Wet-lab research'], 'datePublished': '2004', 'dateBasis': 'publication', 'dateSource': 'https://doi.org/10.1093/nar/gkg044',
         'url': 'https://ctdbase.org', 'description': 'Curated chemical-gene-disease interactions.',
         'manuscript': 'absent', 'maintained': 'active',
         'qualifiedRelation': [{'relation': '#exo', 'hadRole': 'implements', 'evidence': 'FAIRsharing'}]},
        {'key': 'oecd_gd', 'name': 'OECD guidance on research data', 'decision': 'include', 'type': 'Policy: institution',
         'scope': 'Toxicology', 'phase': 'Regulatory assessment', 'span': ['Regulatory assessment'],
         'stakeholders': ['Regulator'],
         'datePublished': '2026', 'manuscript': 'cited',
         'manuscriptEvidence': 'L190'},
        {'key': 'parc', 'name': 'PARC', 'decision': 'exclude', 'exclusionReason': 'E1', 'manuscript': 'named'},
        {'key': 'tool', 'name': 'A FAIR tool', 'decision': 'undecided', 'type': 'Tool', 'scope': 'Generic'},
    ]
    return model.new_document(rs)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        # FIP and FAIRsharing data come from the fixtures, never from the network; FIP reports go to this folder
        for module, name, value in ((fip, 'CACHE', os.path.join(ROOT, 'tests', 'fixtures', 'fip')),
                                    (fip, 'FIPS', {'tool': np_iri('fipA'), 'oecd_gd': np_iri('fipB')}),
                                    (fip, 'REPORT', self.path('report.csv')), (fip, 'CONVERGENCE', self.path('fip.md')),
                                    (fairsharing, 'CACHE', os.path.join(ROOT, 'tests', 'fixtures', 'fairsharing'))):
            patcher = mock.patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

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
        self.assertEqual(exo['phase'], 'Data integration')
        self.assertNotIn('phase', next(r for r in doc['hasPart'] if r['key'] == 'tool'))
        # CTD (2004) implements ExO (2012) backwards in time, allowed because FAIRsharing asserts it
        self.assertFalse(any('first published later' in w for w in warnings))

    def test_each_bad_case_is_an_error(self):
        cases = [
            ('exo', 'scope', 'Toxicologie', 'not an allowed value'),
            ('exo', 'datePublished', '2012-13', 'YYYY'),
            ('exo', 'datePublished', '2999', 'YYYY'),
            ('parc', 'exclusionReason', '', 'exclusion reason is required'),
            ('ctd', 'phase', '', 'phase is required'),
            ('ctd', 'stakeholders', [], 'creator type is required'),
            ('tool', 'phase', 'Data generation', 'phase is required'),
            ('exo', 'stakeholders', ['Lab'], 'creator type'),
            ('parc', 'exclusionReason', 'E6', 'E6 needs Covered by'),
            ('exo', 'subdomains', ['ecotox'], 'sub-domain'),
            ('exo', 'url', 'ctdbase.org', 'http(s) URL'),
            ('exo', 'span', ['Data generation', 'Data integration'], 'earliest phase'),
            ('ctd', 'span', [], 'earliest phase'),
            ('exo', 'fsrType', [model.FIP + 'Structured-vocabulary', model.FIP + 'Registry'], 'one FSR type'),
            ('exo', 'fsrType', [model.FIP + 'Crosswalk'], 'not an allowed value'),   # not one the typing rule uses
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

    def test_lane_rules(self):
        self.assertEqual(model.lane({'scope': 'Generic'}), 'Generic infrastructure')
        self.assertEqual(model.lane({'scope': 'Life Sciences'}), 'Life Sciences infrastructure')
        for phase in model.PHASES:   # the toxicology lanes take the phase names
            self.assertEqual(model.lane({'scope': 'Toxicology', 'phase': phase}), phase)
        self.assertEqual(model.creator_lane({'scope': 'Toxicology', 'stakeholders': ['Regulator']}), 'Made by regulators')
        self.assertEqual(model.creator_lane({'scope': 'Toxicology', 'stakeholders': ['Regulator', 'Wet-lab research']}),
                         'Made jointly')
        self.assertEqual(model.creator_lane({'scope': 'Life Sciences'}), 'Life Sciences infrastructure')

    def test_building_on_fair_is_derived_from_a_builds_on_relation(self):
        doc = fixture()
        exo = next(r for r in doc['hasPart'] if r['key'] == 'exo')
        exo['qualifiedRelation'] = [{'relation': '#tool', 'hadRole': 'related_to', 'evidence': 'curator'}]
        exo['datePublished'] = '2020'
        self.assertNotIn('buildsOnFair', next(r for r in model.normalise(doc)['hasPart'] if r['key'] == 'exo'))
        exo = next(r for r in doc['hasPart'] if r['key'] == 'exo')
        exo['qualifiedRelation'][0]['hadRole'] = 'implements'
        self.assertTrue(next(r for r in model.normalise(doc)['hasPart'] if r['key'] == 'exo')['buildsOnFair'])
        next(r for r in doc['hasPart'] if r['key'] == 'exo')['datePublished'] = '2012'   # before the FAIR principles
        self.assertNotIn('buildsOnFair', next(r for r in model.normalise(doc)['hasPart'] if r['key'] == 'exo'))

    def test_fsr_and_fip_fields_are_derived(self):
        types = model.fsr_types()
        self.assertEqual((len(types), sum(t[2] for t in types.values())), (57, 20))   # FSR types, of which FER
        self.assertLessEqual(set(model.FSR_OFFERED), set(types))
        doc = fixture()
        by = {r['key']: r for r in doc['hasPart']}
        by['exo']['fsrType'], by['ctd']['fsrType'] = [model.FIP + 'Structured-vocabulary'], [model.FIP + 'Editor']
        by['tool']['declared-by'] = '#parc'
        by['tool']['fipDeclaration'] = [{'@id': 'https://w3id.org/np/RAx', '@type': 'fip:FIP-Declaration',
                                         'declares-current-use-of': 'https://doi.org/10.25504/FAIRsharing.6hna78',
                                         'question': model.FIP + 'FIP-Question-I2-D', 'principle': 'I2'}]
        by = {r['key']: r for r in model.normalise(doc)['hasPart']}
        self.assertEqual((by['exo']['fsrCategory'], by['ctd']['fsrCategory']), (model.FER, model.FSR))
        self.assertEqual((by['exo']['declaredIn'], by['exo']['principles']), (['#tool'], ['I2']))
        self.assertNotIn('declaredIn', by['parc'])   # declared-by names the FIP's community, not a resource it uses
        self.assertEqual(model.check(doc)[0], [])

    def test_fair_implementation_community_needs_its_fic_nanopublication(self):
        doc = model.normalise(fixture())
        parc = next(r for r in doc['hasPart'] if r['key'] == 'parc')
        parc['fsrType'] = [model.FIC]
        self.assertTrue(any('FAIR Implementation Community' in e for e in model.check(doc)[0]))   # @id is #parc
        parc['@id'] = 'https://w3id.org/np/RAexample#PARC'
        self.assertEqual(model.check(doc)[0], [])

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
        cell = ws.cell(row=row, column=head[column], value=value).coordinate
        wb.save(p)
        return cell

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
        for column, value in (('Scope', 'Toxicologie'), ('FSR type', 'Databank')):
            p = self.build(doc)
            cell = self.edit(p, column, 'ctd', value)
            new, _, problems, _, _ = sheet.ingest(doc, p)
            self.assertIsNone(new)
            self.assertEqual([(x['sheet'], x['cell'], x['column']) for x in problems], [('Resources', cell, column)])
            self.assertIn('allowed values', problems[0]['problem'])

    def test_fsr_types_span_and_read_only_fip_rows(self):
        doc = model.normalise(fixture())
        by = {r['key']: r for r in doc['hasPart']}
        by['exo']['fsrType'], by['ctd']['fsrType'] = [model.FIP + 'Structured-vocabulary'], [model.FIP + 'Editor']
        p = self.build(fip.enrich(copy.deepcopy(doc), fip.read(offline=True)))   # tool and oecd_gd declare exo
        wb = load_workbook(p)
        tab = lambda name: [dict(zip([c.value for c in wb[name][1]], r))
                            for r in wb[name].iter_rows(min_row=2, values_only=True) if r[0]]
        exo = next(r for r in tab('Resources') if r['Key'] == 'exo')
        self.assertEqual([exo[h] for h in ('FSR type', 'Class', 'Principles', 'Declared in', *sheet.SPAN_HEAD.values())],
                         ['Structured vocabulary', 'FAIR-Enabling Resource', 'F1',
                          'OECD guidance on research data (F1-D); A FAIR tool (F1-D)', None, 'x', None])
        self.assertEqual([(x['Resource'], x['Relation'], x['Target'], x['Vocabulary'], x['Question'], x['Use'])
                          for x in tab('Relations') if x['Evidence'] == 'FIP'],
                         [('oecd_gd', 'declares-current-use-of', 'exo', 'FIP ontology', 'F1-D', 'current use'),
                          ('tool', 'declares-current-use-of', 'exo', 'FIP ontology', 'F1-D', 'current use')])
        self.assertEqual({x['Vocabulary'] for x in tab('Relations') if x['Evidence'] != 'FIP'}, {'FAIRsharing'})
        self.assertEqual(sheet.ingest(doc, p)[1:3], ([], []))                  # no changes, no problems
        self.edit(p, 'Target', 'tool', 'ctd', tab='Relations')                 # a FIP row: ignored
        self.edit(p, 'FSR type', 'ctd', 'Registry')
        self.edit(p, 'Span: regulatory assessment', 'exo', 'x')
        self.assertEqual(sheet.ingest(doc, p)[1:3], ([
            ('ctd', 'fsrType', model.FIP + 'Editor', model.FIP + 'Registry'),
            ('exo', 'span', 'Data integration', 'Data integration; Regulatory assessment')], []))
        by['exo']['fsrType'] = [model.FIP + 'Semantic-model']                  # changed after the sheet was made
        self.assertIn('changed in the dataset', sheet.ingest(doc, p)[2][0]['problem'])

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


# The REST shape as served on 5 Oct 2026 (abridged from a real response).
REST_LINKED = {'data': {'id': '3496', 'type': 'fairsharing_records', 'attributes': {
    'name': 'FAIRsharing record for: ELIXIR Toxicology Community', 'fairsharing_registry': 'Collection',
    'record_type': 'collection', 'doi': '10.25504/FAIRsharing.f60a10',
    'metadata': {'name': 'ELIXIR Toxicology Community', 'year_creation': 2020, 'status': 'ready'},
    'linked_records': [{'linked_record_name': 'WikiPathways', 'linked_record_id': 1698, 'relation': 'collects',
                        'relation_id': 10, 'linked_record_registry': 'Database'},
                       {'linked_record_name': 'X', 'linked_record_id': 9, 'relation': 'accepts', 'relation_id': 2}],
    'linking_records': [{'linking_record_name': 'Y', 'linking_record_id': 7, 'relation': 'recommends'}]}}}


class FairsharingTest(TempDir):
    """Read offline from tests/fixtures/fairsharing: members ExO (a row) and New Tox Database (not yet a row)."""
    def setUp(self):
        super().setUp()
        self.data = fairsharing.read(None, None, offline=True)

    def test_slim_reads_linked_records_and_the_real_name(self):
        c = fairsharing.slim(REST_LINKED)
        self.assertEqual((c['name'], c['registry'], c['yearCreation']), ('ELIXIR Toxicology Community', 'Collection', 2020))
        self.assertIn({'other': 1698, 'otherName': 'WikiPathways', 'label': 'collects', 'outgoing': True},
                      c['associations'])
        self.assertIn({'other': 7, 'otherName': 'Y', 'label': 'recommends', 'outgoing': False}, c['associations'])
        self.assertEqual(fairsharing.block(c, set(), '2026-10-05')['associations'], [['collects', 1698], ['implements', 9]])

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

    def test_read_takes_the_members_and_the_rows_records_and_caches_them(self):
        api = {3496: {'id': 3496, 'record_associations': [{'record_assoc_label': 'collects', 'linked_record': {'id': 9}}]},
               9: {'id': 9, 'doi': '10.25504/FAIRsharing.nine'}, 5: {'id': 5, 'doi': '10.25504/FAIRsharing.five'}}
        rows = {'hasPart': [{'fairsharingRecord': 'FAIRsharing.nine'}, {'fairsharingRecord': 'FAIRsharing.five'}]}
        with mock.patch.multiple(fairsharing, CACHE=self.dir, PAUSE=0, sign_in=mock.DEFAULT,
                                 record=lambda rid, jwt: api[rid], lookup=lambda code: api[5]), \
                mock.patch.object(model, 'load', return_value=rows):
            data = fairsharing.read('login', 'password')
        self.assertEqual((data['members'], [x['id'] for x in data['records']]), ([9], [5, 9, 3496]))
        self.assertEqual(model.load(os.path.join(self.dir, 'records.json')), data)   # the cache --offline reads

    def test_curate_adds_a_new_member_once(self):
        doc = model.normalise(fixture())
        self.assertEqual(fairsharing.curate(doc, self.data), [
            'new collection member: newtox (New Tox Database)',
            'exo: first published 2012, FAIRsharing year of creation 2015',
            'FAIRsharing association, not a relation here: newtox implements exo',
            'two-hop: newtox related_to FAIRsharing 7777 Other record'])
        new = next(r for r in doc['hasPart'] if r['key'] == 'newtox')
        self.assertEqual((new['decision'], new['manuscript'], new['type'], new['datePublished'], new['dateBasis'],
                          new['fairsharingRecord'], new['fairsharingMatch']),
                         ('undecided', 'absent', 'Database: repository', '2019', 'FAIRsharing year', 'FAIRsharing.zzz999',
                          'confirmed'))
        self.assertEqual(model.check(doc)[0], [])
        self.assertEqual([r['key'] for r in doc['hasPart'] if 'fairsharing' in r], [])   # nothing read is stored
        once = model.dumps(doc)
        self.assertEqual(len(fairsharing.curate(doc, self.data)), 3)                       # only the notes again
        self.assertEqual(model.dumps(model.normalise(doc)), once)
        doc = model.normalise(fixture())
        next(r for r in doc['hasPart'] if r['key'] == 'tool')['url'] = 'https://newtox.example.org'
        self.assertEqual(fairsharing.curate(doc, self.data)[0],
                         'proposed match: tool = FAIRsharing 9999 New Tox Database (same homepage)')

    def test_enrich_adds_the_published_block(self):
        doc = fairsharing.enrich(model.normalise(fixture()), self.data)
        self.assertEqual([(r['key'], r['fairsharing']) for r in doc['hasPart'] if 'fairsharing' in r], [('exo', {
            'id': 512, 'doi': '10.25504/FAIRsharing.6hna78', 'name': 'Exposure Ontology', 'abbreviation': 'ExO',
            'registry': 'Standard', 'recordType': 'terminology_artefact', 'status': 'ready', 'yearCreation': 2015,
            'homepage': 'https://github.com/CTDbase/exposure-ontology', 'inCollection': True, 'associations': [],
            'retrieved': '2026-10-09'})])
        self.assertEqual(doc['sources']['fairsharing'], {'retrieved': '2026-10-09', 'members': 2})

    def test_commands_stop_when_fairsharing_cannot_be_read(self):
        with mock.patch.dict(os.environ, {'FAIRSHARING_LOGIN': '', 'FAIRSHARING_PASSWORD': ''}):
            for argv in (['site', self.path('site')], ['sheet', self.path('c.xlsx')], ['export-fairsharing', self.dir],
                         ['fairsharing', '--apply']):
                with self.assertRaises(SystemExit) as stop:
                    cli.main(argv)
                self.assertIn('FAIRsharing could not be read', str(stop.exception.code))
        self.assertEqual(os.listdir(self.dir), [])

    def test_submission_export(self):
        doc = fairsharing.enrich(model.normalise(fixture()), dict(self.data, members=[9999]))   # exo not a member
        sub = fairsharing.submission(doc)
        self.assertEqual([x['key'] for x in sub['incomplete']], ['oecd_gd'])          # no description, no homepage
        self.assertEqual(sub['incomplete'][0]['missing'], ['description', 'url'])
        ctd = next(x for x in sub['records'] if x['key'] == 'ctd')['fairsharing_record']
        self.assertEqual(ctd['record_type_id'], 2)
        self.assertEqual(set(ctd['metadata']) >= {'name', 'description', 'homepage', 'status'}, True)
        self.assertEqual(sub['collectionAdditions'][0]['key'], 'exo')
        self.assertEqual(sub['associations'], [])                                        # FAIRsharing evidence only


class SiteTest(TempDir):
    FILES = ('index.html', 'fair-tox-ecosystem.jsonld', 'resources.csv', 'relations.csv', 'terms.ttl', 'terms.jsonld',
             'context.jsonld')

    def build(self, internal=False, doc=None):
        doc = doc or fixture()
        doc['sources'] = {'manuscript': {'name': 'ELIXIR Toxicology Community paper, draft (8)'},
                          'previous': {'name': 'inventory'}}
        p = self.path('d.jsonld')
        model.save(doc, p)
        out = self.path('internal' if internal else 'site')
        doc = fairsharing.enrich(model.load(p), fairsharing.read(None, None, offline=True))
        counts = site.build(doc, out, internal=internal, offline=True)
        return counts, {f: pathlib.Path(out, f).read_text(encoding='utf-8') for f in self.FILES}

    def test_public_build_holds_included_resources_only(self):
        counts, text = self.build()
        self.assertEqual(counts, (3, 1))
        for name, t in text.items():
            for word in ('manuscript', 'draft', 'undecided', 'exclusion', 'screened', 'PARC', 'A FAIR tool'):
                self.assertNotIn(word.lower(), t.lower(), name)
        html = text['index.html']
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
        included = {'exo', 'ctd', 'oecd_gd'}
        self.assertEqual({x['key'] for x in data['nodes']}, included)
        self.assertEqual({x['src'] for x in data['links']}, {'exo'})
        self.assertEqual(set(data['meta']['sources']), {'fairsharing', 'fip'})
        self.assertEqual(data['meta']['lanes'], model.LANES)
        self.assertIn('Toxicology infrastructure', html)
        schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(schema['@type'], 'Dataset')
        self.assertIn('fairsharing-attribution.svg', html)
        self.assertIn('Contains information from FAIRsharing', html)
        self.assertIn(site.PUBLIC_REPO, html)                      # the source repository is private
        self.assertNotIn(site.REPO, html)
        dataset = json.loads(text['fair-tox-ecosystem.jsonld'])
        self.assertEqual(dataset['@context'], model.CONTEXT)
        self.assertEqual({r['key'] for r in dataset['hasPart']}, included)
        self.assertEqual({r['key'] for r in csv.DictReader(io.StringIO(text['resources.csv']))}, included)
        self.assertEqual([(r['subject'], r['hadRole'], r['target']) for r in csv.DictReader(io.StringIO(text['relations.csv']))],
                         [('ctd', 'implements', 'exo')])

    def test_lanes_by_phase_or_by_creator(self):
        doc = fixture()
        next(r for r in doc['hasPart'] if r['key'] == 'tool')['decision'] = 'include'
        next(r for r in doc['hasPart'] if r['key'] == 'oecd_gd')['qualifiedRelation'] = [
            {'relation': '#tool', 'hadRole': 'recommends', 'evidence': 'curator'}]     # builds on a FAIR resource
        _, text = self.build(doc=doc)
        html = text['index.html']
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
        nodes = {n['key']: n for n in data['nodes']}
        self.assertEqual({k: (n['lane'], n['creatorLane'], n['buildsOnFair']) for k, n in nodes.items()}, {
            'exo': ('Data integration', 'Made by in silico research', False),
            'ctd': ('Data integration', 'Made jointly', False),
            'oecd_gd': ('Regulatory assessment', 'Made by regulators', True),
            'tool': ('Generic infrastructure', 'Generic infrastructure', False)})
        self.assertEqual((nodes['ctd']['phase'], nodes['ctd']['stakeholders']),
                         ('Data integration', ['Wet-lab research', 'In silico research']))
        self.assertEqual((nodes['tool']['phase'], nodes['tool']['stakeholders']), ('', []))
        self.assertEqual(data['meta']['creatorLanes'], list(model.CREATOR_LANE_DEF))
        self.assertEqual(data['meta']['creatorLaneDef'], model.CREATOR_LANE_DEF)
        self.assertLessEqual({'phase', 'stakeholders', 'creatorLane'}, set(data['meta']['vocab']))
        rows = {r['key']: r for r in csv.DictReader(io.StringIO(text['resources.csv']))}
        self.assertEqual((rows['ctd']['stakeholders'], rows['oecd_gd']['buildsOnFair'], rows['ctd']['buildsOnFair']),
                         ('Wet-lab research; In silico research', 'True', 'False'))
        # the two-option layout toggle, the creator lanes, and italics from buildsOnFair rather than the scope
        self.assertIn('<legend>Toxicology lanes</legend>', html)
        self.assertEqual(len(re.findall(r'<input type="radio" name="mode"', html)), 2)
        for name in ('checked> Phase</label>', 'Creator', *model.CREATOR_LANE_DEF):
            self.assertIn(name, html)
        self.assertRegex(html, r'const italic = n => n\.buildsOnFair\b')
        self.assertIn('label: toxicology resource building on FAIR', html)
        for name, t in text.items():   # no single stakeholder field is left, and no "intended use" or "main use"
            self.assertNotRegex(t, r'(?i)\bstakeholder\b|intended use|main use', name)
            self.assertNotIn('Toxicology building on FAIR', t, name)

    def test_collection_switch_hides_collection_members_the_manuscript_does_not_name(self):
        doc = model.normalise(fixture())                          # members: exo, named in the manuscript, and newtox
        fairsharing.curate(doc, fairsharing.read(None, None, offline=True))
        next(r for r in doc['hasPart'] if r['key'] == 'newtox')['decision'] = 'include'
        html = self.build(doc=doc)[1]['index.html']
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual({n['key'] for n in data['nodes'] if n['fromCollection']}, {'newtox'})
        self.assertIn('<input type="checkbox" id="t-coll" checked>', html)
        self.assertIn("(!n.fromCollection || $('t-coll').checked)", html)

    def test_internal_build_keeps_every_row_and_the_curation_view(self):
        counts, text = self.build(internal=True)
        self.assertEqual(counts, (5, 1))
        self.assertIn('FAIRsharing vs manuscript', text['index.html'])
        self.assertIn('Internal curation view. Not for publication.', text['index.html'])
        self.assertIn('"decision": "exclude"', text['fair-tox-ecosystem.jsonld'])

    def test_both_builds_follow_the_journal_figure_rules(self):
        # Scientific Data: white only, one sans-serif face, sentence-case labels, the 183 mm export, a data dictionary
        for internal in (False, True):
            html = self.build(internal)[1]['index.html']
            self.assertNotIn('prefers-color-scheme', html)
            self.assertNotIn('data-theme', html)
            self.assertIn('"Helvetica Neue", Helvetica, Arial, sans-serif', html)
            for text in ('Generic infrastructure', 'Life sciences infrastructure', 'Data generation', 'Data integration',
                         'Regulatory assessment', 'Toxicology infrastructure', 'Year first published',
                         'Before 2000', 'window.publicationSVG', '183mm', 'Data dictionary',
                         'as required by the FAIRsharing data they include', 'Toxicology lanes', '> Phase</label>',
                         'life-cycle phase it acts on (the earliest, if several)', "row('Phase'", "row('Span'",
                         "{t: 'Span'", "{t: 'FSR type'", 'FIP declarations', 'Declared in a toxicology FIP',
                         'Magagna et al. 2024, CEUR-WS Vol-3882', 'are read when the page is built',
                         *model.CREATOR_LANE_DEF):
                self.assertIn(text, html, (internal, text))

    def test_vocabulary_context_and_anchors_resolve_our_iris(self):
        import rdflib
        from rdflib import OWL, RDF, SKOS
        self.enterContext(warnings.catch_warnings(action='ignore', category=DeprecationWarning))   # rdflib's own code
        t = rdflib.Namespace(model.TERMS)
        fields = {'@context': model.CONTEXT, **dict.fromkeys(model.CURATED + model.RELATION_ORDER, 'x')}
        own = {p[len(model.TERMS):] for p in rdflib.Graph().parse(data=json.dumps(fields), format='json-ld')
               .predicates() if p.startswith(model.TERMS)}         # the fields the context leaves to our terms
        self.assertEqual(len(own), 14)
        for internal in (False, True):                             # the public build leaves out the curation terms
            text, hidden = self.build(internal)[1], set() if internal else {*site.PRIVATE, *site.PRIVATE_VOCABULARIES}
            terms = rdflib.Graph().parse(data=text['terms.ttl'], format='turtle')
            self.assertEqual(set(terms), set(rdflib.Graph().parse(data=text['terms.jsonld'], format='json-ld')))
            self.assertEqual(json.loads(text['context.jsonld']), {'@context': model.CONTEXT})
            data = rdflib.Graph().parse(data=text['fair-tox-ecosystem.jsonld'], format='json-ld')
            used = {x for triple in data for x in triple if x.startswith(model.TERMS)}
            self.assertLessEqual(used, set(terms.subjects()))      # every IRI of ours in the data is defined
            props = {p[len(model.TERMS):] for p in terms.subjects(RDF.type, RDF.Property)}
            self.assertEqual(props, own - hidden)
            for name, values in model.VOCABULARIES.items():        # one concept per value, labelled with it
                concepts = set(terms.subjects(SKOS.inScheme, t[name + '-values']))
                labels = {str(terms.value(c, SKOS.prefLabel)) for c in concepts}
                expected = (set(), 0) if name in hidden else (set(values), len(values))
                self.assertEqual((labels, len(concepts)), expected, name)
            html = text['index.html']                              # an anchor per term; a fragment opens its resource
            for code in (*(f"['{name}', '" for name in props),
                         """<dt id="${esc(f.split(',')[0])}">""", """<dt${v === 'hadRole' ? ` id="${esc(k)}"` : ''}>""",
                         'if (Object.hasOwn(byKey, hash)) select(hash);'):
                self.assertIn(code, html, (internal, code))


class LabelTest(unittest.TestCase):
    def test_figure_labels(self):
        self.assertEqual(site.label({'name': 'AOP-Wiki', 'alternateName': ['AOP-wiki']}), 'AOP-Wiki')
        self.assertEqual(site.label({'name': 'ChEBI (Chemical Entities of Biological Interest)',
                                     'alternateName': ['ChEBI']}), 'ChEBI')
        self.assertEqual(site.label({'name': 'Nanomaterial data integrated with AOP knowledge in RDF',
                                     'alternateName': ['vanrijn2024']}), 'Nanomaterial data integrated with AOP…')
        self.assertEqual(site.clean_alias({'name': 'AOP-helpFinder', 'alternateName': ['jaylet2023']}), '')

    def test_a_cut_label_does_not_end_on_a_stop_word(self):
        for name, cut in (('FAIR Cookbook recipe: Metadata for bioassay data with BAO', 'FAIR Cookbook recipe: Metadata…'),
                          ('Proposals to harmonise spreadsheets for toxicology data', 'Proposals to harmonise spreadsheets…'),
                          ('ISA extensions for toxicogenomics, metabolomics and more', 'ISA extensions for toxicogenomics…'),
                          ('Regulatory Forum Opinion Piece: The Interpretation', 'Regulatory Forum Opinion Piece…')):
            self.assertEqual(site.label({'name': name}), cut)


def np_iri(tag, base='https://w3id.org/np/'):
    """A fixture nanopublication IRI (tests/fixtures/fip/<code>.trig)."""
    return base + 'RA' + tag + '0' * (43 - len(tag))


class FipTest(TempDir):
    """Two FIPs on tiny TriG fixtures, read offline: the `tool` row's FIP and the `oecd_gd` row's FIP."""
    X, W = np_iri('fsrX', 'http://purl.org/np/') + '#X', np_iri('fsrW', 'http://purl.org/np/') + '#W'

    def setUp(self):
        super().setUp()
        self.data = fip.read(offline=True)

    def test_index_walk_skips_invalidated_declarations_and_reads_the_latest_description(self):
        a = self.data['fips']['tool']
        self.assertEqual((a['label'], a['created'], a['invalidated'], a['noChoice']),
                         ('Test FIP A', '2026-01-01T00:00:00Z', 1, ['A1.2-D']))
        uses = sorted((x['fip'], fip._q(x['question']), x['principle'], x['target'], x['considerations'])
                      for x in self.data['declarations'] if x['target'])
        self.assertEqual(uses, [('oecd_gd', 'F1-D', 'F1', self.X, ''), ('oecd_gd', 'R1.1-D', 'R1.1', self.W, ''),
                                ('tool', 'F1-D', 'F1', self.X, 'Used for test data.')])   # not the invalidated I1-D
        x = self.data['fsrs'][self.X]   # superseded where it was minted: its latest valid description is read
        self.assertEqual((x['description'], x['name'], x['aliases'], x['codes']),
                         (np_iri('fsrXtwo'), 'X Resource Name', ['XYZ'], ['FAIRsharing.6hna78']))

    def test_match_order(self):
        rows = model.normalise(fixture())['hasPart']

        def find(**kw):
            r, how = fip.find(rows, self.X, **kw)
            return r and r['key'], how
        self.assertEqual(find(codes=['FAIRsharing.6hna78'], homepages=['https://ctdbase.org/'], names=['CTD']),
                         ('exo', 'doi'))
        self.assertEqual(find(homepages=['https://ctdbase.org/'], names=['ExO']), ('ctd', 'homepage'))
        self.assertEqual(find(names=['ExO']), ('exo', 'name'))
        self.assertEqual(find(names=['Unknown']), (None, 'none'))
        next(r for r in rows if r['key'] == 'tool')['@id'] = self.X   # the row is the declared resource
        self.assertEqual(find(codes=['FAIRsharing.6hna78']), ('tool', 'fsr'))
        next(r for r in rows if r['key'] == 'ctd')['fsr'] = [self.X]   # linked by an earlier import
        self.assertEqual(find(codes=['FAIRsharing.6hna78']), ('ctd', 'fsr'))

    def curated(self):
        doc = model.normalise(fixture())
        return model.normalise(fip.curate(doc, self.data, fip.match(doc, self.data)))

    def test_report_then_curate_twice_changes_nothing_the_second_time(self):
        doc = model.normalise(fixture())
        rows = fip.report(doc, self.data, fip.match(doc, self.data))
        self.assertEqual([(r['label'], r['key'], r['method']) for r in rows], [
            ('XYZ | X Resource Name', 'exo', 'doi'), ('W Licence | WLic', '', 'none'),
            ('TOX | Toxicology Community', '', 'none'),           # the FIPs' own FIC
            ('PARC | Partnership for testing', 'parc', 'name')])  # a valid FIC named like an E1 row: identity check
        with open(fip.REPORT, encoding='utf-8') as f:
            self.assertEqual(len(list(csv.DictReader(f))), 4)
        one = self.curated()
        self.assertEqual(model.check(one)[0], [])
        self.assertEqual([c[0] for c in model.diff(model.normalise(fixture()), one)], ['tox', 'wlic'])   # new rows
        two = model.normalise(fip.curate(copy.deepcopy(one), self.data, fip.match(one, self.data)))
        self.assertEqual(model.dumps(two), model.dumps(one))
        by = {r['key']: r for r in one['hasPart']}
        self.assertEqual(by['exo']['fsr'], [self.X])
        self.assertEqual((by['wlic']['decision'], by['wlic']['alternateName'], by['wlic']['url'], by['wlic']['fsr']),
                         ('undecided', ['WLic'], 'https://w.example.org/licence', [self.W]))
        self.assertTrue(by['wlic']['note'].endswith('screen against I1-I5. Retrieved 2026-10-08.'))
        self.assertEqual((by['tox']['@id'], by['tox']['fsrType']), (np_iri('ficA') + '#TOX', [model.FIC]))
        # nothing imported is stored: no declarations, FIP sources or profiles
        self.assertEqual([r['key'] for r in one['hasPart'] if {'declared-by', 'fipDeclaration'} & r.keys()], [])
        self.assertEqual((one['sources'], one['isBasedOn']), ({}, [model.COLLECTION_DOI]))

    def test_enrich_adds_the_declarations_with_targets_resolved_to_rows(self):
        # before curation, W and the FIPs' community have no row, so they are left out
        by = {r['key']: r for r in model.normalise(fip.enrich(model.normalise(fixture()), self.data))['hasPart']}
        self.assertEqual([d['declares-current-use-of'] for d in by['oecd_gd']['fipDeclaration']], [by['exo']['@id']])
        self.assertNotIn('declared-by', by['oecd_gd'])
        doc = model.normalise(fip.enrich(self.curated(), self.data))
        by = {r['key']: r for r in doc['hasPart']}
        fic = np_iri('ficA') + '#TOX'
        self.assertEqual((by['tool']['declared-by'], by['oecd_gd']['declared-by'], by['tox']['@id']), (fic, fic, fic))
        self.assertEqual(by['tool']['fipDeclaration'], [{
            '@id': np_iri('decA') + '/declaration', '@type': 'fip:FIP-Declaration',
            'declares-current-use-of': by['exo']['@id'], 'question': model.FIP + 'FIP-Question-F1-D', 'principle': 'F1',
            'considerations': 'Used for test data.'}])
        self.assertEqual([d['declares-current-use-of'] for d in by['oecd_gd']['fipDeclaration']],
                         [by['wlic']['@id'], by['exo']['@id']])   # wlic through its fsr link
        self.assertEqual((by['exo']['declaredIn'], by['exo']['principles']), (['#oecd_gd', '#tool'], ['F1']))
        self.assertEqual({k: (s['retrieved'], s['declarations']) for k, s in doc['sources']['fip'].items()},
                         {'tool': ('2026-10-08', 1), 'oecd_gd': ('2026-10-08', 2)})
        self.assertEqual(doc['isBasedOn'], sorted([model.COLLECTION_DOI, np_iri('fipA') + '/fip',
                                                   np_iri('fipB') + '#fip']))

    def test_site_and_sheet_builds_publish_declarations_to_included_rows_only_and_save_nothing(self):
        doc, folder = self.curated(), pathlib.Path(ROOT, 'data')
        state = lambda: (model.dumps(doc), {p: p.stat().st_mtime_ns for p in folder.rglob('*')})
        before = state()
        built = fairsharing.enrich(copy.deepcopy(doc), fairsharing.read(None, None, offline=True))
        site.build(built, self.path('site'), offline=True)
        sheet.build(built, self.path('curation.xlsx'))
        self.assertEqual(state(), before)   # copies are enriched, and nothing under data/ is written
        by = {r['key']: r for r in model.load(self.path('site/fair-tox-ecosystem.jsonld'))['hasPart']}
        # oecd_gd also declares wlic, and is declared by tox: both undecided; tool, the other FIP, is undecided too
        self.assertEqual([d['declares-current-use-of'] for d in by['oecd_gd']['fipDeclaration']], [by['exo']['@id']])
        self.assertNotIn('declared-by', by['oecd_gd'])
        self.assertEqual(by['exo']['declaredIn'], ['#oecd_gd'])

    def test_dashboard_shows_types_and_declarations_and_never_draws_communities(self):
        doc = self.curated()
        by = {r['key']: r for r in doc['hasPart']}
        by['exo']['fsrType'], by['ctd']['fsrType'] = [model.FIP + 'Structured-vocabulary'], [model.FIP + 'Editor']
        pages = []
        for internal in (False, True):
            built = fairsharing.enrich(copy.deepcopy(doc), fairsharing.read(None, None, offline=True))
            site.build(built, self.path(str(internal)), internal=internal, offline=True)
            html = pathlib.Path(self.path(str(internal)), 'index.html').read_text(encoding='utf-8')
            data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
            pages.append((html, data, {n['key']: n for n in data['nodes']}))
        html, data, nodes = pages[0]
        self.assertEqual([(nodes[k]['fsrType'], nodes[k]['fsrCategory']) for k in ('exo', 'ctd')],
                         [(['Structured vocabulary'], 'FAIR-Enabling Resource'), (['Editor'], 'FAIR Supporting Resource')])
        self.assertEqual((nodes['exo']['principles'], nodes['exo']['declaredIn'], nodes['oecd_gd']['declaredBy']),
                         (['F1'], ['oecd_gd'], ''))   # its community, tox, is not included
        self.assertEqual(data['declarations'], [{'src': 'oecd_gd', 'dst': 'exo',
                                                 'q': [['F1-D', np_iri('decD') + '/declaration']]}])
        self.assertEqual((data['meta']['classes'], data['meta']['communities']),
                         (['FAIR-Enabling Resource', 'FAIR Supporting Resource'],
                          ['Emerging community', 'FAIR Implementation Community', 'Mature community']))
        # the Class filter; the FIP switches, off on load, the lines never in the export; communities never drawn
        for code in ('(!n.fsrCategory || state.cls.has(n.fsrCategory))', '<input type="checkbox" id="t-fip">',
                     "const fipOn = !G.print && $('t-fip').checked", '<input type="checkbox" id="t-declared">',
                     'n.fsrType.some(t => META.communities.includes(t))',
                     "=> dated(n) && laneNames().includes(laneOf(n)) && !community(n);"):
            self.assertIn(code, html)
        _, data, nodes = pages[1]
        self.assertEqual((nodes['oecd_gd']['declaredBy'], nodes['tox']['fsrType']),
                         ('tox', ['FAIR Implementation Community']))
        self.assertEqual(len(data['declarations']), 3)   # tool and oecd_gd declare exo, oecd_gd declares wlic

    def test_convergence_rows(self):
        fip.convergence(self.data)
        with open(fip.CONVERGENCE, encoding='utf-8') as f:
            text = f.read()
        for row in ('| Question | Principle | Test FIP A | Test FIP B | Shared |', '| F1-D | F1 | XYZ | XYZ | yes |',
                    '| A1.2-D | A1.2 | no choice | not answered | no |', '| R1.1-D | R1.1 | not answered | WLic | no |',
                    'share a choice on 1 of 21 core questions (F1-D)'):
            self.assertIn(row, text)
        self.assertLess(text.index('| F4-MD |'), text.index('| A1.1-D |'))   # F, A, I, R


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

    def test_no_two_public_resources_share_a_figure_label(self):
        dataset = os.path.join(ROOT, model.DATASET)
        if not os.path.exists(dataset):
            self.skipTest('no dataset yet')
        labels = [site.label(r) for r in site.public(model.load(dataset))['hasPart']]
        self.assertEqual(sorted({x for x in labels if labels.count(x) > 1}), [])

    def test_dataset_is_valid_and_parses_as_json_ld(self):
        dataset = os.path.join(ROOT, model.DATASET)
        if not os.path.exists(dataset):
            self.skipTest('no dataset yet')
        doc = model.load(dataset)
        self.assertEqual(model.check(doc)[0], [])
        self.assertEqual([r['key'] for r in doc['hasPart'] if 'fairsharing' in r], [])   # FAIRsharing is read when
        self.assertNotIn('fairsharing', doc['sources'])                                  # building, never stored
        import rdflib
        g = rdflib.Graph().parse(data=json.dumps(doc), format='json-ld')
        name = rdflib.URIRef('https://schema.org/name')
        self.assertGreaterEqual(len(set(g.subjects(name, None))), len(doc['hasPart']))
        own = {str(p)[len(model.TERMS):] for p in g.predicates() if str(p).startswith(model.TERMS)}
        self.assertLessEqual(own, {'scope', 'phase', 'span', 'stakeholders', 'dateBasis', 'dateSource', 'decision',
                                   'exclusionReason', 'coveredBy', 'manuscript', 'manuscriptEvidence',
                                   'fairsharingRecord', 'fairsharingMatch', 'evidence'})   # all else is standard


if __name__ == '__main__':
    unittest.main()
