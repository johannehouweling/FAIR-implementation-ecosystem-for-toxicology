"""Tests of fairtox.model: vocabularies, normalising and checking the dataset, the change log."""
import copy
import warnings
from unittest import mock

import rdflib

from fairtox import model
from test_fairtox import TempDir, fixture


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
            ('exo', 'origin', 'Toxicologie', 'not an allowed value'),
            ('exo', 'datePublished', '2012-13', 'YYYY'),
            ('exo', 'datePublished', '2999', 'YYYY'),
            ('parc', 'exclusionReason', '', 'exclusion reason is required'),
            ('ctd', 'phase', '', 'phase is required'),
            ('ctd', 'creatorType', [], 'creator type is required'),
            ('tool', 'phase', 'Data generation', 'phase is required'),
            ('exo', 'creatorType', ['Lab'], 'creator type'),
            ('parc', 'exclusionReason', 'E6', 'E6 needs Covered by'),
            ('exo', 'subdomains', ['ecotox'], 'sub-domain'),
            ('exo', 'url', 'ctdbase.org', 'http(s) URL'),
            ('exo', 'span', ['Data generation', 'Data integration'], 'earliest phase'),
            ('ctd', 'span', [], 'earliest phase'),
            ('exo', 'fsrType', [model.FIC, model.FIP + 'Registry'], 'no other FSR type'),
            ('exo', 'fsrType', [model.FIP + 'FAIR-Training-Material'], 'not an allowed value'),   # outside the typology
            ('exo', 'mentionedIn', ['Blog'], 'community document'),
            ('exo', 'contactPoint', ['someone@example.org'], 'ORCID or ROR link'),
        ]
        for key, field, value, message in cases:
            doc = fixture()
            next(r for r in doc['hasPart'] if r['key'] == key)[field] = value
            errors, _ = model.check(model.normalise(doc))
            self.assertTrue(any(message in e for e in errors), (key, field, value, errors))

    def test_a_field_added_later_keeps_the_row_versions(self):
        exo = next(r for r in model.normalise(fixture())['hasPart'] if r['key'] == 'exo')
        self.assertEqual(model.row_hash(exo), '382d971423')        # as before mentionedIn existed
        self.assertNotEqual(model.row_hash({**exo, 'mentionedIn': ['Whitepaper']}), '382d971423')
        self.assertNotEqual(model.row_hash({**exo, 'contactPoint': ['https://ror.org/044rwnt51']}), '382d971423')

    def test_structural_errors(self):
        doc = fixture()
        doc['hasPart'].append(copy.deepcopy(doc['hasPart'][0]))
        self.assertTrue(any('duplicate key' in e for e in model.check(doc)[0]))
        doc = fixture()
        next(r for r in doc['hasPart'] if r['key'] == 'parc').update(fairsharingRecord='FAIRsharing.6hna78',
                                                                     fairsharingMatch='confirmed')   # exo's record
        self.assertTrue(any('same identifier' in e for e in model.check(model.normalise(doc))[0]))
        doc = fixture()
        doc['hasPart'][1]['qualifiedRelation'] = [{'relation': '#nothing', 'hadRole': 'implements', 'evidence': 'curator'}]
        self.assertTrue(any('not in the dataset' in e for e in model.check(model.normalise(doc))[0]))
        doc = fixture()
        doc['hasPart'][1]['qualifiedRelation'][0]['hadRole'] = 'part_of'
        self.assertTrue(any('not an allowed label' in e for e in model.check(model.normalise(doc))[0]))

    def test_a_relation_must_be_possible(self):
        def warns(subject, role, target, **types):
            doc = fixture()
            by = {r['key']: r for r in doc['hasPart']}
            for k, t in types.items():
                by[k]['fsrType'] = [model.FIP + x for x in t.split()]
            by[subject]['qualifiedRelation'] = [{'relation': '#' + target, 'hadRole': role, 'evidence': 'curator'}]
            return any(f'{subject}: {role} {target} is not possible' in w for w in model.check(model.normalise(doc))[1])
        self.assertFalse(warns('ctd', 'implements', 'exo'))                     # FAIRsharing: database to standard
        self.assertTrue(warns('oecd_gd', 'implements', 'exo'))                  # not from a policy
        self.assertFalse(warns('oecd_gd', 'implements', 'exo', oecd_gd='Data-usage-license',
                               exo='Structured-vocabulary'))                   # fip:implements: FER to FAIR specification
        self.assertFalse(warns('tool', 'related_to', 'ctd', tool='Registry'))   # a Tool counts as its FSR column
        self.assertTrue(warns('tool', 'recommends', 'ctd', tool='Registry'))
        self.assertFalse(warns('tool', 'recommends', 'ctd'))                    # not checked until typed
        self.assertFalse(warns('tool', 'recommends', 'ctd', tool='Editor Persistency-Policy'))   # each FSR column
        self.assertFalse(warns('oecd_gd', 'implements', 'exo', oecd_gd='FAIR-Practice Persistency-Policy',
                               exo='Editor Structured-vocabulary'))           # any FER type, any specification type
        self.assertEqual((model.RELATIONS['implements'][2], model.RELATIONS['recommends'][2]),
                         ('The subject implements the standard or FAIR specification.',
                          'The data policy recommends the target.'))            # FAIRsharing's wording

    def test_recommends_is_a_policy_pointing_at_a_resource(self):
        self.assertNotIn('uses', model.RELATIONS)                               # FAIRsharing's labels only
        self.assertFalse(model.RELATIONS['recommends'][1])                      # not lineage
        doc = fixture()
        tox = next(r for r in doc['hasPart'] if r['key'] == 'oecd_gd')
        tox['qualifiedRelation'] = [{'relation': '#tool', 'hadRole': 'recommends', 'evidence': 'curator'}]
        built = lambda: next(r for r in model.normalise(copy.deepcopy(doc))['hasPart'] if r['key'] == 'oecd_gd')
        self.assertNotIn('buildsOnFair', built())                               # not a derivation
        tox['qualifiedRelation'][0]['hadRole'] = 'implements'
        self.assertTrue(built()['buildsOnFair'])

    def test_lane_rules(self):
        self.assertEqual(model.lane({'origin': 'Generic'}), 'Generic infrastructure')
        self.assertEqual(model.lane({'origin': 'Life Sciences'}), 'Life sciences infrastructure')
        self.assertEqual(sorted(model.FIGURE_LANES), sorted(model.LANES))   # the figure reorders, never adds or drops
        for phase in model.PHASES:   # the toxicology lanes take the phase names
            self.assertEqual(model.lane({'origin': 'Toxicology', 'phase': phase}), phase)
        self.assertEqual(model.creator_lane({'origin': 'Toxicology', 'creatorType': ['Regulator']}), 'Made by regulators')
        self.assertEqual(model.creator_lane({'origin': 'Toxicology', 'creatorType': ['Regulator', 'Wet-lab research']}),
                         'Made jointly')
        self.assertEqual(model.creator_lane({'origin': 'Life Sciences'}), 'Life sciences infrastructure')

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

    def test_every_controlled_field_is_checked(self):
        for field, value in (('fairsharingType', 'Databank'), ('origin', 'Toxicologie'), ('maintained', 'alive')):
            doc = model.normalise(fixture())
            doc['hasPart'][0][field] = value
            self.assertTrue(any(repr(value) in e for e in model.check(doc)[0]), field)

    def test_ids_are_absolute_without_base(self):
        doc = model.normalise(fixture())                    # a context loaded by URL may not set @base
        self.assertNotIn('@base', model.CONTEXT)
        self.assertEqual(doc['@id'], model.BASE)
        self.assertEqual({r['key']: r['@id'] for r in doc['hasPart']}['oecd_gd'], model.BASE + '#oecd_gd')
        self.assertTrue(all(q['relation'].startswith('https://') for r in doc['hasPart'] for q in r.get('qualifiedRelation', [])))

    def test_fsr_and_fip_fields_are_derived(self):
        types = model.fsr_types()
        self.assertLessEqual(set(model.fsr_offered()), set(types))
        self.assertEqual([types[model.FIP + t][2] for t in ('Registry', 'Metadata-schema', 'Editor')], [True, True, False])
        doc = fixture()
        by = {r['key']: r for r in doc['hasPart']}
        by['exo']['fsrType'], by['ctd']['fsrType'] = [model.FIP + 'Structured-vocabulary'], [model.FIP + 'Editor']
        by['tool']['declared-by'] = '#parc'
        by['tool']['fipDeclaration'] = [{'@id': 'https://w3id.org/np/RAx', '@type': 'fip:FIP-Declaration',
                                         'declares-current-use-of': 'https://doi.org/10.25504/FAIRsharing.6hna78',
                                         'question': model.FIP + 'FIP-Question-F1-D', 'principle': 'F1'}]
        by = {r['key']: r for r in model.normalise(doc)['hasPart']}
        self.assertEqual((by['exo']['fsrCategory'], by['ctd']['fsrCategory']), (model.FER, model.FSR))
        # principles are what the FSR types enable in the FIP ontology (I2 for a structured vocabulary), not the
        # question of the declaration; an Editor, no FAIR-Enabling Resource, enables none
        self.assertEqual((by['exo']['declaredIn'], by['exo']['principles']), ([by['tool']['@id']], ['I2']))
        self.assertEqual(by['ctd'].get('principles', []), [])
        self.assertNotIn('declaredIn', by['parc'])   # declared-by names the FIP's community, not a resource it uses
        self.assertEqual(model.check(doc)[0], [])

    def test_a_resource_takes_every_fsr_type_that_applies(self):
        doc = fixture()
        next(r for r in doc['hasPart'] if r['key'] == 'ctd')['fsrType'] = [model.FIP + t for t in
                                                                         ('Registry', 'Editor', 'Registry')]
        ctd = next(r for r in model.normalise(doc)['hasPart'] if r['key'] == 'ctd')
        self.assertEqual((ctd['fsrType'], ctd['fsrCategory']),          # once each, in one order; an FER when one is
                         ([model.FIP + 'Editor', model.FIP + 'Registry'], model.FER))
        self.assertEqual(model.check(doc)[0], [])

    def test_fsr_types_are_the_typology_of_the_fip_ontology(self):
        offered = model.fsr_offered()
        self.assertIn(model.FIP + 'Crosswalk', offered)                   # under FAIR specification
        self.assertIn(model.FIP + 'Domain-Specific-Registry', offered)    # one level below, under Registry
        self.assertIn(model.FIC, offered)                                 # for communities
        self.assertNotIn(model.FIP + 'Web-API', offered)                  # deprecated
        self.assertNotIn(model.FIP + 'FAIR-Training-Material', offered)   # outside the typology

    def test_a_type_with_two_labels_keeps_its_sentence_case_label(self):
        g = model.fip_ontology()
        for t, labels in (('Communication-protocol', ('Communication Protocol', 'Communication protocol')),   # 19 Oct
                          ('FAIR-Practice', ('FAIR Practice', 'FAIR practice'))):                             # 23 Oct
            c = rdflib.URIRef(model.FIP + t)
            g.remove((c, rdflib.RDFS.label, None))
            for label in labels:
                g.add((c, rdflib.RDFS.label, rdflib.Literal(label)))
        model.fsr_types.cache_clear()
        self.addCleanup(model.fsr_types.cache_clear)
        with mock.patch.object(model, 'fip_ontology', return_value=g):
            self.assertEqual([model.fsr_types()[model.FIP + t][0] for t in ('Communication-protocol', 'FAIR-Practice')],
                             ['Communication protocol', 'FAIR practice'])

    def test_fair_implementation_community_needs_its_fic_nanopublication(self):
        doc = model.normalise(fixture())
        parc = next(r for r in doc['hasPart'] if r['key'] == 'parc')
        parc['fsrType'] = [model.FIC]
        self.assertTrue(any('FAIR Implementation Community' in e for e in model.check(doc)[0]))   # @id is #parc
        parc['@id'] = 'https://w3id.org/np/RAexample#PARC'
        self.assertEqual(model.check(doc)[0], [])

    def test_a_date_is_stored_under_the_field_of_its_basis(self):
        doc = fixture()
        next(r for r in doc['hasPart'] if r['key'] == 'ctd')['dateBasis'] = 'release'
        by = {r['key']: r for r in model.normalise(doc)['hasPart']}
        self.assertEqual({k: {f: r[f] for f in model.DATE_FIELDS.values() if f in r} for k, r in by.items()}, {
            'exo': {'datePublished': '2012-01'}, 'ctd': {'dateReleased': '2004'}, 'oecd_gd': {'date': '2026'},
            'parc': {}, 'tool': {}})
        self.assertFalse(any('dateBasis' in r for r in by.values()))
        self.assertEqual([model.first_date(by[k]) for k in ('exo', 'ctd', 'oecd_gd', 'tool')],
                         [('2012-01', 'publication'), ('2004', 'release'), ('2026', ''), ('', '')])
        self.assertEqual(model._year(by['ctd']), 2004)
        by['exo']['dateCreated'] = '2010'
        self.assertTrue(any('one date' in e for e in model.check(doc)[0]))

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
        model.log_changes([('ctd', 'relation implements exo reviewedBy', '', 'IM', 'IM')], 'round 2', 'test.xlsx',
                          {'ctd': 'JH'}, path=log)        # a fifth item names who made the change
        with open(log) as f:
            text = f.read()
        self.assertIn('round 1,ctd,datePublished,2004,2003,JH,test.xlsx', text)
        self.assertIn('round 2,ctd,relation implements exo reviewedBy,,IM,IM,test.xlsx', text)
