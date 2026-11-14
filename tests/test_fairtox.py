"""The shared fixture and the checks of the repository as a whole. Run every test with the standard library:
uv run python -m unittest discover -s tests -v"""
import csv
import json
import os
import re
import tempfile
import unittest
from unittest import mock

import rdflib

from fairtox import __version__, fairsharing, fip, model, pids, sheet, site

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fixture():
    rs = [
        {'key': 'exo', 'name': 'Exposure Ontology', 'alternateName': ['ExO'], 'decision': 'include',
         'fairsharingType': 'Standard: terminology artefact', 'origin': 'Toxicology', 'phase': 'Data integration',
         'span': ['Data integration'],
         'creatorType': ['In silico research'], 'subdomains': ['exposome'], 'datePublished': '2012-01', 'dateBasis': 'publication',
         'dateSource': 'https://doi.org/10.1021/es2033857', 'url': 'https://github.com/CTDbase/exposure-ontology',
         'manuscript': 'named', 'manuscriptEvidence': 'Data generation; L100', 'fairsharingRecord': 'FAIRsharing.6hna78',
         'fairsharingMatch': 'confirmed', 'maintained': 'active'},
        {'key': 'ctd', 'name': 'Comparative Toxicogenomics Database', 'alternateName': ['CTD'], 'decision': 'include',
         'fairsharingType': 'Database: knowledgebase', 'origin': 'Toxicology', 'phase': 'Data integration',
         'span': ['Data integration', 'Regulatory assessment'],
         'creatorType': ['In silico research', 'Wet-lab research'], 'datePublished': '2004', 'dateBasis': 'publication', 'dateSource': 'https://doi.org/10.1093/nar/gkg044',
         'url': 'https://ctdbase.org', 'description': 'Curated chemical-gene-disease interactions.',
         'manuscript': 'absent', 'maintained': 'active',
         'qualifiedRelation': [{'relation': '#exo', 'hadRole': 'implements', 'evidence': 'FAIRsharing'}]},
        {'key': 'oecd_gd', 'name': 'OECD guidance on research data', 'decision': 'include', 'fairsharingType': 'Policy: institution',
         'origin': 'Toxicology', 'phase': 'Regulatory assessment', 'span': ['Regulatory assessment'],
         'creatorType': ['Regulator'],
         'date': '2026', 'manuscript': 'cited',
         'manuscriptEvidence': 'L190'},
        {'key': 'parc', 'name': 'PARC', 'decision': 'exclude', 'exclusionReason': 'E1', 'manuscript': 'named'},
        {'key': 'tool', 'name': 'A FAIR tool', 'decision': 'undecided', 'fairsharingType': 'Tool', 'origin': 'Generic'},
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
                                    (fairsharing, 'CACHE', os.path.join(ROOT, 'tests', 'fixtures', 'fairsharing')),
                                    (pids, 'CACHE', os.path.join(ROOT, 'tests', 'fixtures', 'pids'))):
            patcher = mock.patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)


def np_iri(tag, base='https://w3id.org/np/'):
    """A fixture nanopublication IRI (tests/fixtures/fip/<code>.trig)."""
    return base + 'RA' + tag + '0' * (43 - len(tag))


class RepositoryTest(unittest.TestCase):
    def test_one_version_everywhere(self):
        with open(os.path.join(ROOT, 'pyproject.toml')) as f:
            self.assertIn(f'version = "{__version__}"', f.read())
        with open(os.path.join(ROOT, 'CITATION.cff')) as f:
            self.assertIn(f'version: {__version__}', f.read())
        with open(os.path.join(ROOT, '.release-please-manifest.json')) as f:
            self.assertEqual(json.load(f), {'.': __version__})
        dataset = os.path.join(ROOT, model.DATASET)
        if os.path.exists(dataset):
            self.assertEqual(model.load(dataset)['version'], __version__)

    def test_the_same_authors_in_citation_cff_and_the_dataset(self):
        # CITATION.cff, which Zenodo and GitHub read, names the dataset's creators in the same order with the same iDs
        with open(os.path.join(ROOT, 'CITATION.cff'), encoding='utf-8') as f:
            cff = f.read().split('\nauthors:\n', 1)[1].split('\nversion:', 1)[0]
        people = re.findall(r'given-names: (.+)\n +family-names: (.+)\n +orcid: (\S+)\n +affiliation: (.+)', cff)
        self.assertEqual([(a['givenName'], a['familyName'], a['identifier'], '; '.join(o['name'] for o in a['affiliation']))
                          for a in model.AUTHORS], people)
        self.assertTrue(cff.rstrip().endswith(f'- name: {model.CREATOR["name"]}'))
        creator = model.load(os.path.join(ROOT, model.DATASET))['creator']['@list']
        self.assertEqual(creator, [*model.AUTHORS, model.CREATOR])
        self.assertEqual(model.citation_authors(), 'Houweling, J. et al.')

    def test_every_vocabulary_value_is_documented_as_the_code_defines_it(self):
        docs = {}
        for name in ('data-dictionary.md', 'inclusion-criteria.md'):
            with open(os.path.join(ROOT, 'docs', name), encoding='utf-8') as f:
                docs[name] = f.read()
        for name, vocab in model.VOCABULARIES.items():
            text = docs['inclusion-criteria.md' if name == 'exclusionReason' else 'data-dictionary.md']   # E1-E8: criteria
            for value, meaning in vocab.items():
                self.assertIn(value, text, f'{name}: {value}')
                self.assertIn(meaning, text, f'{name}: {value}')

    def test_a_signed_row_was_not_changed_elsewhere_after_its_signature(self):
        # A signature covers the columns up to Note; a process that changes one of them on a signed row empties
        # Reviewed by. Changes that only rename or move values do not count; a model change can propose values.
        signed = set(model.CURATED) - {f for _, f, *_ in sheet.CONTEXT_COLUMNS} - {'key', 'reviewedBy', 'note'}
        sign, outside = {}, {}
        with open(os.path.join(ROOT, model.CHANGES), newline='', encoding='utf-8') as f:
            for i, r in enumerate(csv.DictReader(f)):
                if (r['field'] == 'reviewedBy' and r['new']
                        or r['field'] == '(row)' and r['source'] == 'curation-sheet.xlsx'):   # added with initials
                    sign[r['key']] = i
                elif r['field'] in signed and r['source'] != 'curation-sheet.xlsx' and r['by'] not in (
                        'migration', 'rename', 'cleanup', 'labels'):
                    outside[r['key']] = i
        for r in model.load(os.path.join(ROOT, model.DATASET))['hasPart']:
            if r.get('reviewedBy'):
                self.assertGreater(sign.get(r['key'], -1), outside.get(r['key'], -1), r['key'])

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
        name = model.SCHEMA.name
        self.assertGreaterEqual(len(set(g.subjects(name, None))), len(doc['hasPart']))
        own = {str(p) for p in g.predicates() if str(p).startswith(model.TERMS)}
        self.assertEqual(own, set())                           # every field is a standard term, or out of the graph

    def test_queries_run_and_count_the_resources_in_the_figure(self):
        import contextlib
        import io
        from fairtox import cli
        self.assertEqual([r['key'] for r in fixture()['hasPart'] if model.in_figure(r)], ['ctd', 'oecd_gd'])  # exo: exposome
        folder = os.path.join(ROOT, 'queries')
        for name in sorted(os.listdir(folder)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as end:
                cli.main(['query', os.path.join(folder, name)])
            self.assertEqual(end.exception.code, 0, name)
            rows = list(csv.DictReader(io.StringIO(out.getvalue())))
            self.assertTrue(rows, name)
            if name == 'resources-by-origin.rq':                # SPARQL agrees with the rule the dashboard draws by
                drawn = sum(model.in_figure(r) for r in model.normalise(model.load(model.DATASET))['hasPart'])
                self.assertEqual(sum(int(r['resources']) for r in rows), drawn)


if __name__ == '__main__':
    unittest.main()
