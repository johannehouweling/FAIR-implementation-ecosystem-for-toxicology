"""Tests of fairtox.fip: reading the toxicology FIPs and matching their declarations."""
import copy
import csv
import json
import pathlib
import re
from unittest import mock

from fairtox import fairsharing, fip, model, sheet, site
from test_fairtox import ROOT, TempDir, fixture, np_iri


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
        x = self.data['fsrs'][self.X]   # superseded where it was minted: its latest valid description is read,
                                        # where FAIRsharing's legacy id bsg-s000512 resolves to the same record
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
                         sorted([by['wlic']['@id'], by['exo']['@id']]))   # wlic through its fsr link
        self.assertEqual((by['exo']['declaredIn'], by['exo']['principles']),
                         ([by['oecd_gd']['@id'], by['tool']['@id']], ['F1']))
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
        self.assertEqual(by['exo']['declaredIn'], [by['oecd_gd']['@id']])
        credit = model.load(self.path('site/fair-tox-ecosystem.jsonld'))['creditText']   # FAIRsharing, then the FIPs
        self.assertTrue(credit.startswith(model.FAIRSHARING_CREDIT))
        for iri in (np_iri('fipA'), np_iri('fipB')):
            self.assertIn(iri, credit)

    def test_dashboard_shows_types_and_declarations_and_never_draws_communities(self):
        doc = self.curated()
        by = {r['key']: r for r in doc['hasPart']}
        by['exo']['fsrType'], by['ctd']['fsrType'] = [model.FIP + 'Structured-vocabulary'], [model.FIP + 'Editor']
        built = fairsharing.enrich(copy.deepcopy(doc), fairsharing.read(None, None, offline=True))
        site.build(built, self.path('site'), offline=True)
        html = pathlib.Path(self.path('site'), 'index.html').read_text(encoding='utf-8')
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
        nodes = {n['key']: n for n in data['nodes']}
        self.assertEqual([(nodes[k]['fsrType'], nodes[k]['fsrCategory']) for k in ('exo', 'ctd')],
                         [(['Structured vocabulary'], 'FAIR-Enabling Resource'), (['Editor'], 'FAIR Supporting Resource')])
        self.assertEqual((nodes['exo']['principles'], nodes['exo']['declaredIn'], nodes['oecd_gd']['declaredBy']),
                         (['F1'], ['oecd_gd'], ''))   # its community, tox, is not included
        self.assertEqual(data['declarations'], [{'src': 'oecd_gd', 'dst': 'exo',
                                                 'q': [['F1-D', np_iri('decD') + '/declaration']]}])
        self.assertEqual(set(data['meta']['classDef']), set(data['meta']['classes']))
        # a FIP is a source of what it declares and of itself
        self.assertEqual(nodes['oecd_gd']['sources'][-1], nodes['oecd_gd']['label'])
        self.assertIn(nodes['oecd_gd']['label'], nodes['exo']['sources'])
        self.assertEqual((data['meta']['classes'], data['meta']['communities']),
                         (['FAIR-Enabling Resource', 'FAIR Supporting Resource'],
                          ['Emerging community', 'FAIR Implementation Community', 'Mature community']))
        # the Class filter; the FIP switches, off on load, the lines never in the export; communities never drawn
        for code in ('(!n.fsrCategory || state.cls.has(n.fsrCategory))', '<input type="checkbox" id="t-fip">',
                     "const fipOn = !G.print && $('t-fip').checked", '<select id="f-src"',
                     'n.fsrType.some(t => META.communities.includes(t))',
                     "=> dated(n) && laneNames().includes(laneOf(n)) && !community(n) && !outOfScope(n);"):
            self.assertIn(code, html)
        nodes, _, declarations = site.nodes_links(model.normalise(fip.enrich(built, fip.read(offline=True))))
        nodes = {n['key']: n for n in nodes}   # every row, before the build leaves out what is not included
        self.assertEqual((nodes['oecd_gd']['declaredBy'], nodes['tox']['fsrType']),
                         ('tox', ['FAIR Implementation Community']))
        self.assertEqual(len(declarations), 3)   # tool and oecd_gd declare exo, oecd_gd declares wlic

    def test_convergence_rows(self):
        principle, version = fip.ontology()       # since 19 Oct 2026 the FIP ontology gives supporting questions a
        principle = {**principle, model.FIP + 'FIP-S-Question-F2-E': 'F2'}       # principle too: not a core question
        with mock.patch.object(fip, 'ontology', return_value=(principle, version)):
            fip.convergence(self.data)
        with open(fip.CONVERGENCE, encoding='utf-8') as f:
            text = f.read()
        for row in ('| Question | Principle | Test FIP A | Test FIP B | Shared |', '| F1-D | F1 | XYZ | XYZ | yes |',
                    '| A1.2-D | A1.2 | no choice | not answered | no |', '| R1.1-D | R1.1 | not answered | WLic | no |',
                    'share a choice on 1 of 21 core questions (F1-D)'):
            self.assertIn(row, text)
        self.assertLess(text.index('| F4-MD |'), text.index('| A1.1-D |'))   # F, A, I, R
