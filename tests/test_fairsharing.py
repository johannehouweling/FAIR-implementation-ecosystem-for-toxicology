"""Tests of fairtox.fairsharing and fairtox.web: reading FAIRsharing, curating its data, the submission export."""
import copy
import os
import unittest
import urllib.error
from unittest import mock

from fairtox import cli, fairsharing, model, site, web
from test_fairtox import TempDir, fixture


REST = {'data': {'id': '1716', 'type': 'fairsharing_records', 'attributes': {
    'name': 'Comparative Toxicogenomics Database', 'abbreviation': 'CTD', 'registry': 'Database',
    'record_type': 'knowledgebase', 'subjects': ['Toxicology'], 'domains': ['gene'],   # labels only, without IRIs
    'metadata': {'doi': '10.25504/FAIRsharing.h3tjtr', 'year_creation': 2004,
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
        self.assertEqual(e['subjects'], [{'iri': 'http://www.fairsharing.org/ontology/subject/SRAO_0000001', 'label': 'Toxicology'}])
        self.assertEqual((c['subjects'], c['domains']), ([{'iri': '', 'label': 'Toxicology'}], [{'iri': '', 'label': 'gene'}]))
        public = {'id': 1716, 'tags': {'subjects': [{'iri': 'http://aims.fao.org/aos/agrovoc/c_4318', 'label': 'Life Science'}]}}
        with mock.patch.multiple(fairsharing, PAUSE=0, sign_in=mock.DEFAULT, record=lambda rid, jwt: REST_LINKED if rid == 3496 else REST,
                                 lookup=lambda ref: public), mock.patch.object(model, 'load', return_value={'hasPart': []}):
            with mock.patch.object(fairsharing, 'CACHE', self.dir):
                rec = next(x for x in fairsharing.read('a', 'b')['records'] if x['id'] == 1716)
        self.assertEqual(rec['subjects'], public['tags']['subjects'])   # the IRIs come from the public record

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
        asked, load = [], model.load                     # the same day, only a record not read yet is read
        rows['hasPart'].append({'fairsharingRecord': '7'})
        api[7] = {'id': 7}
        with mock.patch.multiple(fairsharing, CACHE=self.dir, sign_in=mock.DEFAULT, lookup=lambda ref: api[7],
                                 record=lambda rid, jwt: asked.append(rid) or api[rid]), \
                mock.patch.object(model, 'load', side_effect=lambda *path: load(*path) if path else rows):
            fairsharing.read('login', 'password')
        self.assertEqual(asked, [7])

    def test_requests_are_paused_as_fairsharing_asked(self):
        clock = iter([100.0, 100.0, 103.0, 103.0])
        with mock.patch.object(fairsharing, '_last', float('-inf')), mock.patch('time.sleep') as sleep, \
                mock.patch('time.monotonic', lambda: next(clock)), \
                mock.patch.object(fairsharing.web, 'fetch', return_value=({}, b'{}')):
            fairsharing._request('GET', fairsharing.API)
            fairsharing._request('GET', fairsharing.API)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [0, fairsharing.PAUSE - 3])

    def test_curate_adds_a_new_member_once(self):
        doc = model.normalise(fixture())
        self.assertEqual(fairsharing.curate(doc, self.data), [
            'new collection member: newtox (New Tox Database)',
            'exo: first published 2012, FAIRsharing year of creation 2015',
            'FAIRsharing association, not a relation here: newtox implements exo',
            'two-hop: newtox related_to FAIRsharing 7777 Other record'])
        new = next(r for r in doc['hasPart'] if r['key'] == 'newtox')
        self.assertEqual((new['decision'], new['manuscript'], new['fairsharingType'], model.first_date(new),
                          new['fairsharingRecord'], new['fairsharingMatch']),
                         ('undecided', 'absent', 'Database: repository', ('2019', 'FAIRsharing year'),
                          'FAIRsharing.zzz999', 'confirmed'))
        self.assertEqual(new['dateCreated'], '2019')
        self.assertEqual(model.check(doc)[0], [])
        self.assertEqual([r['key'] for r in doc['hasPart'] if 'fairsharing' in r], [])   # nothing read is stored
        once = model.dumps(doc)
        self.assertEqual(len(fairsharing.curate(doc, self.data)), 3)                       # only the notes again
        self.assertEqual(model.dumps(model.normalise(doc)), once)
        doc = model.normalise(fixture())
        next(r for r in doc['hasPart'] if r['key'] == 'tool')['url'] = 'https://newtox.example.org'
        self.assertEqual(fairsharing.curate(doc, self.data)[0],
                         'proposed match: tool = FAIRsharing 9999 New Tox Database (same homepage)')

    def test_each_unchecked_row_is_searched_and_checked_once(self):
        doc = model.normalise(fixture())        # unchecked: ctd, oecd_gd and tool; exo is matched, parc excluded
        ctd = {'id': 1716, 'doi': '10.25504/FAIRsharing.h3tjtr', 'name': 'Comparative Toxicogenomics Database',
               'abbreviation': 'CTD', 'homepage': 'https://ctdbase.org/'}
        exo = {'id': 512, 'doi': '10.25504/FAIRsharing.6hna78', 'name': 'A FAIR tool'}   # exo's record: not proposed
        asked = []

        def search(q, jwt):
            asked.append(q)
            if q == 'oecd guidance research data':
                raise fairsharing.FairsharingError('HTTP 500')
            return {'ctd': [ctd], 'ctdbase.org': [ctd], 'fair tool': [exo]}.get(q, [])
        with mock.patch.multiple(fairsharing, CACHE=self.dir, PAUSE=0, sign_in=mock.DEFAULT, search=search,
                                 record=lambda rid, jwt: REST_LINKED if rid == 3496 else {'id': rid},
                                 lookup=lambda ref: {'id': 512}), mock.patch.object(model, 'load', return_value=doc):
            data = fairsharing.read('login', 'password')
        self.assertEqual(asked, ['comparative toxicogenomics database', 'ctd', 'ctdbase.org',   # name, other names,
                                 'oecd guidance research data', 'fair tool'])                    # homepage host
        self.assertEqual(data['searches'], {'ctd': [ctd], 'tool': [exo]})   # the search failed for oecd_gd only
        self.assertEqual(fairsharing.check(doc, data), [
            'proposed match: ctd = FAIRsharing 1716 Comparative Toxicogenomics Database (same homepage)',
            'not searched in FAIRsharing, still unchecked: oecd_gd', 'no FAIRsharing record found: tool'])
        by = {r['key']: (r.get('fairsharingRecord'), r.get('fairsharingMatch')) for r in model.normalise(doc)['hasPart']}
        self.assertEqual((by['ctd'], by['oecd_gd'], by['tool'], by['parc']),
                         (('FAIRsharing.h3tjtr', 'to check'), (None, None), (None, 'no record'), (None, None)))
        self.assertEqual(fairsharing.check(doc, data), ['not searched in FAIRsharing, still unchecked: oecd_gd'])
        self.assertEqual(fairsharing.queries({'name': 'OECD Guidance Document on the use of data (GD 417)',
                                              'url': 'https://www.oecd.org/a/b?c=1'}),   # the parts around brackets
                         ['oecd guidance document use data gd 417', 'oecd guidance document use data', 'gd 417',
                          'oecd.org'])
        long = 'eTRANSAFE: building a sustainable framework to share reproducible drug safety knowledge with the public'
        self.assertEqual(fairsharing.queries({'name': long}),                             # the first ten words
                         ['etransafe building sustainable framework share reproducible drug safety knowledge public'])
        self.assertEqual(fairsharing.propose({'name': 'AOP-DB (Adverse Outcome Pathway Database)'},
                                             [{'id': 1, 'name': 'Adverse Outcome Pathway Database'}])[1],
                         'same name or abbreviation')

    def test_enrich_adds_the_published_block(self):
        doc = fairsharing.enrich(model.normalise(fixture()), self.data)
        self.assertEqual([(r['key'], r['fairsharing']) for r in doc['hasPart'] if 'fairsharing' in r], [('exo', {
            'id': 512, 'doi': '10.25504/FAIRsharing.6hna78', 'name': 'Exposure Ontology', 'abbreviation': 'ExO',
            'registry': 'Standard', 'recordType': 'terminology_artefact', 'status': 'ready', 'yearCreation': 2015,
            'homepage': 'https://github.com/CTDbase/exposure-ontology',
            'subjects': [{'iri': 'http://purl.obolibrary.org/obo/NCIT_C20179', 'label': 'Toxicogenomics'}],
            'domains': [{'iri': 'http://purl.obolibrary.org/obo/OBI_0500000', 'label': 'study design'},
                        {'iri': '', 'label': 'exposure'}],
            'inCollection': True, 'associations': [], 'retrieved': '2026-10-09'})])
        published = {r['key']: r for r in site.public(doc)['hasPart']}
        record = published['exo']['fairsharingRecord']   # inherited: FAIRsharing's statements, on its record
        self.assertEqual(record, {'@id': 'https://fairsharing.org/FAIRsharing.6hna78',
            'about': [{'@id': 'http://purl.obolibrary.org/obo/NCIT_C20179', 'name': 'Toxicogenomics'}],   # its subjects: scope
            'theme': [{'@id': 'http://purl.obolibrary.org/obo/OBI_0500000', 'name': 'study design'}]})   # its domains:
        # the life cycle; a term without an IRI ('exposure') is left out
        unconfirmed = copy.deepcopy(doc)
        next(r for r in unconfirmed['hasPart'] if r['key'] == 'exo')['fairsharingMatch'] = 'to check'
        self.assertNotIn('fairsharingRecord', {r['key']: r for r in site.public(unconfirmed)['hasPart']}['exo'])
        self.assertNotIn('keywords', published['exo'])
        self.assertEqual(doc['sources']['fairsharing'], {'retrieved': '2026-10-09', 'members': 2})

    def test_the_collection_lists_its_included_members(self):
        doc = model.normalise(fixture())
        doc['hasPart'].append({'key': 'toxcoll', 'name': 'ELIXIR Toxicology FAIRsharing collection', 'decision': 'include',
                               'fairsharingRecord': 'FAIRsharing.f60a10', 'fairsharingMatch': 'confirmed'})
        doc = fairsharing.enrich(model.normalise(doc), self.data)
        published = {r['key']: r for r in site.public(doc)['hasPart']}   # inherited from FAIRsharing, not stored
        self.assertEqual(published['toxcoll']['@id'], model.COLLECTION_DOI)
        self.assertEqual(published['toxcoll']['resource'], [published['exo']['@id']])   # 9999 has no row
        self.assertNotIn('resource', published['exo'])

    def test_commands_stop_when_fairsharing_cannot_be_read(self):
        with mock.patch.dict(os.environ, {'FAIRSHARING_LOGIN': '', 'FAIRSHARING_PASSWORD': ''}):
            for argv in (['site', self.path('site')], ['sheet', self.path('c.xlsx')], ['export-fairsharing', self.dir],
                         ['fairsharing', '--apply']):
                with self.assertRaises(SystemExit) as stop:
                    cli.main(argv)
                self.assertIn('Nothing was built or changed: FAIRSHARING_LOGIN', str(stop.exception.code))
        self.assertEqual(os.listdir(self.dir), [])

    def test_submission_proposes_only_what_was_checked_and_is_allowed(self):
        doc = model.normalise(fixture())
        by = {r['key']: r for r in doc['hasPart']}
        by['oecd_gd'].update(description='Guidance on sharing research data.', url='https://www.oecd.org')
        by['ctd']['qualifiedRelation'].append({'relation': by['exo']['@id'], 'hadRole': 'related_to',
                                               'evidence': 'literature'})
        by['oecd_gd']['qualifiedRelation'] = [
            {'relation': by['ctd']['@id'], 'hadRole': 'recommends', 'evidence': 'literature'},
            {'relation': by['exo']['@id'], 'hadRole': 'recommends', 'evidence': 'manuscript'},
            {'relation': by['exo']['@id'], 'hadRole': 'implements', 'evidence': 'literature'},   # not for a policy
            {'relation': by['ctd']['@id'], 'hadRole': 'uses', 'evidence': 'literature'}]         # not FAIRsharing's
        read = lambda: fairsharing.submission(fairsharing.enrich(copy.deepcopy(doc), dict(self.data, members=[9999])))
        sub = read()                                      # FAIRsharing was never checked for ctd and oecd_gd
        self.assertEqual((sub['records'], sub['associations']), ([], []))
        self.assertEqual(sub['heldBack'][0], {'item': 'ctd', 'name': 'Comparative Toxicogenomics Database',
                                              'reason': 'FAIRsharing not yet checked for a record of it'})
        self.assertEqual(sub['collectionAdditions'], [{'key': 'exo', 'name': 'Exposure Ontology',
                                                       'record': by['exo']['@id']}])   # not a member
        by['ctd']['fairsharingMatch'] = by['oecd_gd']['fairsharingMatch'] = 'no record'
        sub = read()
        self.assertEqual([(x['key'], x['fairsharing_record']['record_type_id']) for x in sub['records']],
                         [('ctd', 2), ('oecd_gd', 14)])
        self.assertEqual(set(sub['records'][0]['fairsharing_record']['metadata']),
                         {'name', 'homepage', 'description', 'status', 'abbreviation', 'year_creation'})
        self.assertEqual([(x['record'], x['relation'], x['linked_record'], x['linked_record_id'],
                           x['record_assoc_label_id']) for x in sub['associations']],
                         [('new: ctd', 'related_to', by['exo']['@id'], 512, 4),
                          ('new: oecd_gd', 'recommends', 'new: ctd', None, 11)])
        self.assertEqual({x['item']: x['reason'] for x in sub['heldBack']},
                         {'oecd_gd recommends exo': 'the only evidence is the unpublished manuscript',
                          'oecd_gd implements exo': 'FAIRsharing does not allow this label between these record types',
                          'oecd_gd uses ctd': 'not a FAIRsharing label'})


class WebTest(unittest.TestCase):
    def test_busy_servers_and_failed_connections_are_retried_other_errors_are_not(self):
        answer = mock.MagicMock()
        answer.__enter__.return_value.headers, answer.__enter__.return_value.read.return_value = {}, b'ok'
        busy = urllib.error.HTTPError('u', 503, 'busy', {}, None)
        with mock.patch('time.sleep'), mock.patch('urllib.request.urlopen', side_effect=[busy, TimeoutError(), answer]):
            self.assertEqual(web.get('https://example.org', 'text/plain'), 'ok')
        with mock.patch('time.sleep'), mock.patch('urllib.request.urlopen', side_effect=urllib.error.URLError('down')):
            with self.assertRaisesRegex(web.Unreadable, 'could not be read: down'):
                web.get('https://example.org', 'text/plain')
        gone = urllib.error.HTTPError('u', 404, 'gone', {}, None)
        with mock.patch('urllib.request.urlopen', side_effect=gone) as urlopen:
            with self.assertRaisesRegex(web.Unreadable, 'answered HTTP 404'):
                web.get('https://example.org', 'text/plain')
            self.assertEqual(urlopen.call_count, 1)
