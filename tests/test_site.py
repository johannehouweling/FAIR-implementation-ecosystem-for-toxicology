"""Tests of fairtox.site: the dashboard, the published dataset and its terms."""
import csv
import io
import json
import pathlib
import re
import unittest
import warnings

import rdflib

from fairtox import fairsharing, model, site
from test_fairtox import TempDir, fixture


class SiteTest(TempDir):
    FILES = ('index.html', 'fair-tox-ecosystem.jsonld', 'resources.csv', 'relations.csv', 'terms.ttl', 'terms.jsonld',
             'context.jsonld')

    def build(self, doc=None):
        doc = doc or fixture()
        doc['sources'] = {'manuscript': {'name': 'ELIXIR Toxicology Community paper, draft (8)'},
                          'previous': {'name': 'inventory'},
                          'inventory': {'name': 'repository list of example.org', 'resources': ['ctd']}}
        p = self.path('d.jsonld')
        model.save(doc, p)
        out = self.path('site')
        doc = fairsharing.enrich(model.load(p), fairsharing.read(None, None, offline=True))
        counts = site.build(doc, out, offline=True)
        return counts, {f: pathlib.Path(out, f).read_text(encoding='utf-8') for f in self.FILES}

    def test_page_facts_come_from_the_build(self):
        counts, text = self.build()
        html = text['index.html']
        meta = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))['meta']
        # the year of the FAIR principles is the model's rule for Builds on FAIR; the data licence is the dataset's
        self.assertEqual((meta.get('fairPublished'), (meta.get('license') or {}).get('name')),
                         (model.FAIR_PUBLISHED, model.LICENSE['name']))
        self.assertIn(str(model.FAIR_PUBLISHED), dict((f, d) for f, d, v in site.FIELDS)['buildsOnFair'])
        self.assertNotIn('FAIR principles published, 2016', html)   # the marker is drawn from META.fairPublished
        for code in ('const fair = META.fairPublished;', '`FAIR principles published, ${fair}`',
                     "$('lic').innerHTML = link(META.license.url, META.license.name);"):
            self.assertIn(code, html)

    def test_public_build_holds_included_resources_only(self):
        doc = fixture()
        doc['hasPart'][0]['mentionedIn'] = ['Whitepaper']           # a curation field
        counts, text = self.build(doc)
        self.assertEqual(counts, (3, 1))
        for name, t in text.items():
            for word in ('manuscript', 'draft', 'undecided', 'exclusion', 'screened', 'PARC', 'A FAIR tool',
                         'Whitepaper', 'example.org'):
                self.assertNotIn(word.lower(), t.lower(), name)
        html = text['index.html']
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
        included = {'exo', 'ctd', 'oecd_gd'}
        self.assertEqual({x['key'] for x in data['nodes']}, included)
        self.assertEqual({x['src'] for x in data['links']}, {'exo'})
        self.assertEqual(set(data['meta']['sources']), {'fairsharing', 'fip'})
        self.assertEqual(data['meta']['lanes'], model.FIGURE_LANES)
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
        rows = {r['key']: r for r in csv.DictReader(io.StringIO(text['resources.csv']))}
        self.assertEqual(set(rows), included)
        self.assertEqual((rows['exo']['identifier'], rows['exo']['date'], rows['exo']['dateBasis']),
                         ('https://doi.org/10.25504/FAIRsharing.6hna78', '2012-01', 'publication'))
        self.assertEqual([(r['subject'], r['hadRole'], r['target']) for r in csv.DictReader(io.StringIO(text['relations.csv']))],
                         [('ctd', 'implements', 'exo')])

    def test_lanes_by_phase_or_by_creator(self):
        doc = fixture()
        next(r for r in doc['hasPart'] if r['key'] == 'tool')['decision'] = 'include'
        next(r for r in doc['hasPart'] if r['key'] == 'oecd_gd')['qualifiedRelation'] = [
            {'relation': '#tool', 'hadRole': 'implements', 'evidence': 'curator'}]     # builds on a FAIR resource
        _, text = self.build(doc=doc)
        html = text['index.html']
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
        nodes = {n['key']: n for n in data['nodes']}
        self.assertEqual({k: (n['lane'], n['creatorLane'], n['buildsOnFair']) for k, n in nodes.items()}, {
            'exo': ('Data integration', 'Made by in silico research', False),
            'ctd': ('Data integration', 'Made jointly', False),
            'oecd_gd': ('Regulatory assessment', 'Made by regulators', True),
            'tool': ('Generic infrastructure', 'Generic infrastructure', False)})
        self.assertEqual((nodes['ctd']['phase'], nodes['ctd']['creatorType']),
                         ('Data integration', ['Wet-lab research', 'In silico research']))
        self.assertEqual((nodes['tool']['phase'], nodes['tool']['creatorType']), ('', []))
        self.assertEqual(data['meta']['creatorLanes'], list(model.CREATOR_LANE_DEF))
        self.assertEqual(data['meta']['creatorLaneDef'], model.CREATOR_LANE_DEF)
        self.assertLessEqual({'phase', 'creatorType', 'creatorLane'}, set(data['meta']['vocab']))
        rows = {r['key']: r for r in csv.DictReader(io.StringIO(text['resources.csv']))}
        self.assertEqual((rows['ctd']['creatorType'], rows['oecd_gd']['buildsOnFair'], rows['ctd']['buildsOnFair']),
                         ('Wet-lab research; In silico research', 'True', 'False'))
        # the two-option layout toggle, the creator lanes, and italics from buildsOnFair rather than the origin
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
        nodes = {n['key']: n for n in data['nodes']}
        self.assertEqual({k for k, n in nodes.items() if n['fromCollection']}, {'newtox'})
        self.assertEqual(nodes['newtox']['sources'], [site.COLLECTION])   # its only source; exo is also curated
        self.assertEqual(nodes['exo']['sources'][:2], [data['meta']['creator'], site.COLLECTION])
        self.assertEqual(data['meta']['sourceList'][:2], [data['meta']['creator'], site.COLLECTION])
        self.assertIn("(!state.src || n.sources.includes(state.src))", html)

    def test_resources_outside_the_manuscript_scope_are_listed_but_not_drawn(self):
        html = self.build()[1]['index.html']
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(data['meta']['outOfScope'], list(model.OUTSIDE_MANUSCRIPT_SCOPE))
        self.assertLessEqual(set(model.OUTSIDE_MANUSCRIPT_SCOPE), set(model.SUBDOMAINS))   # a misspelt one would leave nothing out

    def test_build_follows_the_journal_figure_rules(self):
        # Scientific Data: white only, one sans-serif face, sentence-case labels, the 183 mm export, a data dictionary
        html = self.build()[1]['index.html']
        self.assertNotIn('prefers-color-scheme', html)
        self.assertNotIn('data-theme', html)
        self.assertIn('"Helvetica Neue", Helvetica, Arial, sans-serif', html)
        for text in ('Generic infrastructure', 'Life sciences infrastructure', 'Data generation', 'Data integration',
                     'Regulatory assessment', 'Toxicology infrastructure', 'b.lane !== META.toxLanes.at(-1)',
                     'Year first published',
                     'Before 2000', 'window.publicationSVG', '183mm', 'Data dictionary',
                     'as required by the FAIRsharing data they include', 'Toxicology lanes', '> Phase</label>',
                     'life-cycle phase they act on (the earliest, if several)', "row('Phase'", "row('Span'",
                     "{t: 'Span'", "{t: 'FSR type'", 'FIP declarations', 'All sources',
                     'Magagna et al. 2024, CEUR-WS Vol-3882', 'are read when the page is built',
                     *model.CREATOR_LANE_DEF):
            self.assertIn(text, html, text)

    def test_vocabulary_context_and_anchors_resolve_our_iris(self):
        import rdflib
        from rdflib import DCAT, DCTERMS, PROV, RDF, SKOS, Literal, URIRef
        self.enterContext(warnings.catch_warnings(action='ignore', category=DeprecationWarning))   # rdflib's own code
        S, t, ds = model.SCHEMA, rdflib.Namespace(model.TERMS), rdflib.Namespace(model.BASE + '#')
        fields = {'@context': model.CONTEXT, **dict.fromkeys(model.CURATED + model.RELATION_ORDER, 'x')}
        own = {p for p in rdflib.Graph().parse(data=json.dumps(fields), format='json-ld').predicates()
               if p.startswith(model.TERMS)}
        self.assertEqual(own, set())                           # every field is a schema.org, DCAT or FIP term, or none
        doc = fixture()
        by = {r['key']: r for r in doc['hasPart']}
        by['ctd']['dateBasis'], by['oecd_gd']['maintained'] = 'release', 'unknown'
        by['ctd']['contactPoint'] = ['https://orcid.org/0000-0002-1825-0097']
        text = self.build(doc)[1]
        terms = rdflib.Graph().parse(data=text['terms.ttl'], format='turtle')
        self.assertEqual(set(terms), set(rdflib.Graph().parse(data=text['terms.jsonld'], format='json-ld')))
        self.assertEqual(json.loads(text['context.jsonld']), {'@context': model.CONTEXT})
        self.assertEqual(set(terms.subjects(RDF.type, RDF.Property)), set())
        data = rdflib.Graph().parse(data=text['fair-tox-ecosystem.jsonld'], format='json-ld')
        used = {x for triple in data for x in triple if x.startswith(model.TERMS)}
        self.assertLessEqual(used, set(terms.subjects(RDF.type, S.DefinedTerm)))   # every term of ours is defined
        root, exo, ctd = URIRef(model.BASE), URIRef('https://doi.org/10.25504/FAIRsharing.6hna78'), ds.ctd
        for triple in ((root, RDF.type, S.Dataset), (root, S.url, Literal(site.PAGES)),
                       (exo, S.about, URIRef(model.NCIT_TOXICOLOGY)),        # FAIRsharing's subject
                       (exo, S.about, URIRef('http://id.nlm.nih.gov/mesh/D000081413')),
                       (ctd, DCAT.theme, t['phase-regulatory-assessment']),
                       (exo, S.creativeWorkStatus, t['maintained-active']),
                       (exo, S.datePublished, Literal('2012-01')), (ctd, DCTERMS.issued, Literal('2004')),
                       (ds.oecd_gd, DCTERMS.date, Literal('2026')),
                       (exo, S.citation, URIRef('https://doi.org/10.1021/es2033857')),
                       (exo, S.sameAs, URIRef('https://fairsharing.org/FAIRsharing.6hna78')),
                       (exo, S.identifier, exo), (ctd, S.identifier, ctd), (exo, RDF.type, S.CreativeWork),
                       (exo, S.url, Literal('https://github.com/CTDbase/exposure-ontology')),
                       (exo, S.additionalType, Literal('Standard: terminology artefact')),
                       (ctd, DCAT.contactPoint, URIRef('https://orcid.org/0000-0002-1825-0097'))):
            self.assertIn(triple, data, triple)
        self.assertIsNone(data.value(ds.oecd_gd, S.creativeWorkStatus))   # unknown: nothing is stated
        for p in (S.about, DCAT.theme, S.creativeWorkStatus, DCAT.hadRole):   # controlled values are IRIs
            self.assertTrue(all(isinstance(o, URIRef) for o in data.objects(None, p)), p)
        record = data.value(root, S.subjectOf)                 # the catalog record of the CDIF Discovery profile
        self.assertEqual(set(data.objects(record, DCTERMS.conformsTo)), set(map(URIRef, site.CDIF)))
        self.assertEqual(data.value(data.value(record, S.maintainer), S.name), Literal(model.CREATOR['name']))
        attributions = set(data.objects(ctd, PROV.qualifiedAttribution))   # creator types, as qualified attributions
        self.assertEqual({data.value(a, RDF.type) for a in attributions}, {PROV.Attribution})
        self.assertIn(URIRef('http://www.ebi.ac.uk/efo/EFO_0009742'), {data.value(a, DCAT.hadRole) for a in attributions})
        self.assertEqual(data.value(record, S.about), root)
        self.assertEqual(str(data.value(data.value(root, S.identifier), S.value)), model.BASE)
        self.assertEqual(len(set(data.objects(root, S.distribution))), len(site.DOWNLOADS))
        fields = set(data.objects(root, S.variableMeasured))          # each field with its term and description
        self.assertTrue(fields and all(data.value(v, S.propertyID) and data.value(v, S.description) for v in fields))
        sets = {name: t[name + '-values'] for name in model.TERM_SETS}
        self.assertEqual(set(terms.subjects(RDF.type, S.DefinedTermSet)), set(sets.values()))
        for name, s in sets.items():                           # a term of ours only where no outside concept exists
            mine = set(terms.subjects(S.inDefinedTermSet, s))
            self.assertEqual({str(terms.value(c, S.name)) for c in mine},
                             set(model.VOCABULARIES[name]) - set(model.SAME.get(name, {})), name)
            self.assertEqual(set(terms.objects(s, SKOS.hasTopConcept)), mine)   # the CDIF Concept Scheme profile
            self.assertTrue(terms.value(s, SKOS.definition), name)
            for c in mine:
                self.assertEqual(set(terms.objects(c, RDF.type)), {S.DefinedTerm, SKOS.Concept})
                self.assertTrue(terms.value(c, SKOS.definition), c)
                self.assertIn((c, SKOS.inScheme, s), terms)
        for triple in ((t['subdomains-conventional-toxicology'], SKOS.broadMatch, URIRef(model.NCIT_TOXICOLOGY)),
                       (t.implements, SKOS.closeMatch, URIRef(model.FIP + 'implements')),
                       (t.deprecates, SKOS.closeMatch, DCTERMS.replaces),
                       (t.uses, SKOS.broadMatch, DCTERMS.relation)):
            self.assertIn(triple, terms, triple)
        html = text['index.html']                              # each field shows its term; a fragment opens its resource
        meta = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))['meta']
        self.assertEqual((meta['terms']['url'], meta['terms']['span'], meta['terms']['dateReleased']),
                         ('schema:url', 'dcat:theme', 'dct:issued'))
        anchors = {a for values in meta['termAnchors'].values() for a in values.values()}   # every term of ours
        self.assertEqual(anchors, {str(c)[len(model.TERMS):] for c in terms.subjects(RDF.type, S.DefinedTerm)})
        self.assertEqual((meta['termAnchors']['phase']['Data generation'], meta['termAnchors']['hadRole']['implements']),
                         ('phase-data-generation', 'implements'))
        for code in ("""<dt id="${esc(f.split(',')[0])}">""", """${(anchors[v] || {})[k] ? ` id="${esc(anchors[v][k])}"` : ''}""",
                     'if (Object.hasOwn(byKey, hash)) select(hash);'):
            self.assertIn(code, html, code)


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
