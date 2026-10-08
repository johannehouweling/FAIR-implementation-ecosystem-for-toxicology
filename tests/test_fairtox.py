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
from unittest import mock

from openpyxl import load_workbook

from fairtox import __version__, fairsharing, fip, model, sheet, site

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
            ('exo', 'fsrType', [model.FIP + 'Structured-vocabulary', model.FIP + 'Registry'], 'direct FSR subclass'),
            ('exo', 'fsrType', [model.DIGITAL_OBJECT, model.FIP + 'Structured-vocabulary'], 'Digital object alone'),
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
        doc = fixture()
        by = {r['key']: r for r in doc['hasPart']}
        by['exo']['fsrType'] = [model.FIP + 'Structured-vocabulary', model.FIP + 'Crosswalk']   # both specifications
        by['ctd']['fsrType'] = [model.DIGITAL_OBJECT]
        by['tool']['declared-by'] = '#parc'
        by['tool']['fipDeclaration'] = [{'@id': 'https://w3id.org/np/RAx', '@type': 'fip:FIP-Declaration',
                                         'declares-current-use-of': '#exo', 'question': model.FIP + 'FIP-Question-I2-D',
                                         'principle': 'I2'}]
        by = {r['key']: r for r in model.normalise(doc)['hasPart']}
        self.assertEqual((by['exo']['fsrCategory'], by['exo']['fsrParent']),
                         (model.FER, model.FIP + 'FAIR-Specification'))
        self.assertEqual((by['ctd']['fsrCategory'], 'fsrParent' in by['ctd']), (model.DIGITAL_OBJECT, False))
        self.assertEqual((by['exo']['declaredIn'], by['exo']['principles']), (['#tool'], ['I2']))
        self.assertNotIn('declaredIn', by['parc'])   # declared-by names the FIP's community, not a resource it uses
        self.assertEqual(model.check(doc)[0], [])

    def test_fair_implementation_community_needs_a_valid_fic_nanopublication(self):
        doc = model.normalise(fixture())
        parc = next(r for r in doc['hasPart'] if r['key'] == 'parc')
        parc.update({'@id': 'https://w3id.org/np/RAexample#PARC', 'fsrType': [model.FIC]})
        lookup = self.path('fic-lookup.json')
        with mock.patch.object(model, 'FIC_LOOKUP', lookup):
            self.assertTrue(any('FAIR Implementation Community' in e for e in model.check(doc)[0]))   # no lookup
            with open(lookup, 'w', encoding='utf-8') as f:
                json.dump({'valid': [parc['@id']]}, f)
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


# The REST shape as served on 5 Oct 2026 (abridged from a real response).
REST_LINKED = {'data': {'id': '3496', 'type': 'fairsharing_records', 'attributes': {
    'name': 'FAIRsharing record for: ELIXIR Toxicology Community', 'fairsharing_registry': 'Collection',
    'record_type': 'collection', 'doi': '10.25504/FAIRsharing.f60a10',
    'metadata': {'name': 'ELIXIR Toxicology Community', 'year_creation': 2020, 'status': 'ready'},
    'linked_records': [{'linked_record_name': 'WikiPathways', 'linked_record_id': 1698, 'relation': 'collects',
                        'relation_id': 10, 'linked_record_registry': 'Database'},
                       {'linked_record_name': 'X', 'linked_record_id': 9, 'relation': 'accepts', 'relation_id': 2}],
    'linking_records': [{'linking_record_name': 'Y', 'linking_record_id': 7, 'relation': 'recommends'}]}}}


class FairsharingTest(unittest.TestCase):
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
    FILES = ('index.html', 'fair-tox-ecosystem.jsonld', 'resources.csv', 'relations.csv')

    def build(self, internal=False, doc=None):
        doc = doc or fixture()
        doc['sources'] = {'manuscript': {'name': 'ELIXIR Toxicology Community paper, draft (8)'},
                          'previous': {'name': 'inventory'}, 'fairsharing': {'members': 74, 'retrieved': '2026-10-05'}}
        p = self.path('d.jsonld')
        model.save(doc, p)
        out = self.path('internal' if internal else 'site')
        counts = site.build(model.load(p), out, dataset_path=p, internal=internal)
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
        self.assertEqual(set(data['meta']['sources']), {'fairsharing'})
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

    def test_lanes_by_intended_use_or_by_creator(self):
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
        for name in ('Intended use', 'Creator', *model.CREATOR_LANE_DEF):
            self.assertIn(name, html)
        self.assertRegex(html, r'const italic = n => n\.buildsOnFair\b')
        self.assertIn('label: toxicology resource building on FAIR', html)
        for name, t in text.items():   # no single stakeholder field is left
            self.assertNotRegex(t, r'(?i)\bstakeholder\b', name)
            self.assertNotIn('Toxicology building on FAIR', t, name)

    def test_collection_switch_hides_collection_members_the_manuscript_does_not_name(self):
        doc = fixture()
        for r in doc['hasPart']:
            if r['key'] in ('exo', 'ctd'):                       # exo is named in the manuscript, ctd is absent
                r['fairsharing'] = {'inCollection': True}
        html = self.build(doc=doc)[1]['index.html']
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual({n['key'] for n in data['nodes'] if n['fromCollection']}, {'ctd'})
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
                         'as required by the FAIRsharing data they include', 'Toxicology lanes', 'Intended use',
                         *model.CREATOR_LANE_DEF):
                self.assertIn(text, html, (internal, text))


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
        fixtures = os.path.join(ROOT, 'tests', 'fixtures', 'fip')
        for obj, name, value in ((fip, 'CACHE', fixtures), (model, 'FIC_LOOKUP', os.path.join(fixtures, 'fic-lookup.json')),
                                 (fip, 'FIPS', {'tool': np_iri('fipA'), 'oecd_gd': np_iri('fipB')}),
                                 (fip, 'REPORT', self.path('report.csv')), (fip, 'CONVERGENCE', self.path('fip.md'))):
            patcher = mock.patch.object(obj, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
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
        next(r for r in rows if r['key'] == 'ctd')['fsr'] = [self.X]   # linked by an earlier import
        self.assertEqual(find(codes=['FAIRsharing.6hna78']), ('ctd', 'fsr'))

    def test_report_then_apply_twice_changes_nothing_the_second_time(self):
        doc = model.normalise(fixture())
        rows = fip.report(doc, self.data, fip.match(doc, self.data))
        self.assertEqual([(r['label'], r['key'], r['method']) for r in rows], [
            ('XYZ | X Resource Name', 'exo', 'doi'), ('W Licence | WLic', '', 'none'),
            ('TOX | Toxicology Community', '', 'none'),           # the FIPs' own FIC
            ('PARC | Partnership for testing', 'parc', 'name')])  # a valid FIC named like an E1 row: identity check
        with open(fip.REPORT, encoding='utf-8') as f:
            self.assertEqual(len(list(csv.DictReader(f))), 4)
        one = model.normalise(fip.apply(doc, self.data, fip.match(doc, self.data)))
        self.assertEqual(model.check(one)[0], [])
        self.assertEqual([c[0] for c in model.diff(model.normalise(fixture()), one)], ['tox', 'wlic'])   # new rows
        two = model.normalise(fip.apply(copy.deepcopy(one), self.data, fip.match(one, self.data)))
        self.assertEqual(model.dumps(two), model.dumps(one))
        by = {r['key']: r for r in one['hasPart']}
        self.assertEqual((by['exo']['fsr'], by['exo']['declaredIn'], by['exo']['principles']),
                         ([self.X], ['#oecd_gd', '#tool'], ['F1']))
        self.assertEqual((by['wlic']['decision'], by['wlic']['alternateName'], by['wlic']['url'], by['wlic']['fsr']),
                         ('undecided', ['WLic'], 'https://w.example.org/licence', [self.W]))
        self.assertTrue(by['wlic']['note'].endswith('screen against I1-I5. Retrieved 2026-10-08.'))
        fic = np_iri('ficA') + '#TOX'
        self.assertEqual((by['tox']['@id'], by['tox']['fsrType'], by['tool']['declared-by']), (fic, [model.FIC], fic))
        self.assertEqual(by['tool']['fipDeclaration'], [{
            '@id': np_iri('decA') + '/declaration', '@type': 'fip:FIP-Declaration',
            'declares-current-use-of': by['exo']['@id'], 'question': model.FIP + 'FIP-Question-F1-D', 'principle': 'F1',
            'considerations': 'Used for test data.'}])
        self.assertEqual(one['sources']['fip']['oecd_gd']['declarations'], 2)

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
