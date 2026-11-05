"""Tests of fairtox.pids: the registered names of creators given as ORCID or ROR links."""
import json
from unittest import mock

from fairtox import pids
from test_fairtox import TempDir

ORCID, ROR = 'https://orcid.org/0000-0002-1825-0097', 'https://ror.org/04wxnsj81'   # ORCID's example record; DataCite


class PidsTest(TempDir):
    def test_cached_names_are_read_offline_and_unknown_links_get_none(self):
        self.assertEqual(pids.names([ORCID, ROR, 'https://ror.org/000000000', 'DataCite'], offline=True),
                         {ORCID: 'Josiah Carberry', ROR: 'DataCite'})

    def test_names_are_read_from_the_registries_once_and_cached(self):
        orcid, ror = 'https://orcid.org/0000-0001-5109-3700', 'https://ror.org/02twcfp32'
        answers = {'https://pub.orcid.org/v3.0/0000-0001-5109-3700/person':
                   {'name': {'given-names': {'value': 'Sofia Maria'}, 'family-name': {'value': 'Hernandez Garcia'},
                             'credit-name': None}},
                   'https://api.ror.org/v2/organizations/02twcfp32':
                   {'names': [{'value': 'Crossref', 'types': ['ror_display', 'label']},
                              {'value': 'CrossRef', 'types': ['alias']}]}}
        with mock.patch.object(pids, 'CACHE', self.path('pids')), \
                mock.patch.object(pids.web, 'get', side_effect=lambda url, accept: json.dumps(answers[url])):
            got = pids.names([orcid, ror, 'A name'])
            self.assertEqual(got, {orcid: 'Sofia Maria Hernandez Garcia', ror: 'Crossref'})
            with open(self.path('pids/names.json'), encoding='utf-8') as f:
                self.assertEqual(json.load(f), got)
            with mock.patch.object(pids.web, 'get', side_effect=AssertionError('asked the registry again')):
                self.assertEqual(pids.names([ror]), {ror: 'Crossref'})
