"""The dataset of record: vocabularies, JSON-LD context, lane rule, load/save, validation and change log.

Every command reads and writes `data/fair-tox-ecosystem.jsonld` through this module, so every write is normalised,
validated and (for curated fields) logged in `data/changes.csv`. Paths are relative to the repository root, which is
where the commands are run.
"""
import copy
import csv
import datetime as dt
import functools
import hashlib
import json
import os
import re
import tempfile

import rdflib
from rdflib import DCTERMS, OWL, RDF, RDFS, SKOS, Literal, URIRef

from fairtox import __version__, web

DATASET = 'data/fair-tox-ecosystem.jsonld'
CHANGES = 'data/changes.csv'
BASE = 'https://w3id.org/fair-tox/dataset'
TERMS = 'https://w3id.org/fair-tox/terms#'
FIP = 'https://w3id.org/fair/fip/terms/'
# The FIP ontology, read from its IRI as Turtle (served by Nanodash) and kept in the local cache. The types were
# checked against FIP_ONTOLOGY_VERSION; check() warns when the ontology has moved on.
FIP_ONTOLOGY = 'build/fip/fip-ontology.ttl'
FIP_ONTOLOGY_VERSION = 'FIP Ontology version 20260227'
NANOPUB_RE = re.compile(r'^https?://(w3id|purl)\.org/np/')
COLLECTION_ID = 3496
COLLECTION_DOI = 'https://doi.org/10.25504/FAIRsharing.f60a10'
FAIRSHARING_CREDIT = ('Contains information from FAIRsharing (https://fairsharing.org), licensed CC BY-SA 4.0 '
                      '(https://creativecommons.org/licenses/by-sa/4.0/).')

# ---- controlled vocabularies: value -> definition ------------------------------------------------------------------

DECISION = {
    'include': 'Meets all inclusion criteria (I1-I5 in docs/inclusion-criteria.md).',
    'exclude': 'Fails a criterion; the exclusion reason says which.',
    'undecided': 'Not yet screened, or left for the co-authors to decide.',
}
EXCLUSION = {
    'E1': 'Organisation, project, initiative, consortium, community or event; its named product is listed instead.',
    'E2': 'Principle, framework, method or approach, or a publication only, rather than a resource that '
          'can be used directly; a standard, database, policy or tool that puts it into practice is listed instead.',
    'E3': 'Unnamed or not identifiable (no homepage or DOI).',
    'E4': 'Never publicly available.',
    'E5': 'No documented toxicology use.',
    'E6': 'Duplicate, version or component of another row (see Covered by).',
    'E7': 'Outside chemical toxicology, such as toxinology or clinical adverse-event grading.',
    'E8': 'Test method or guideline that standardises an experiment rather than data or metadata.',
}
# FAIRsharing registry and record type (id) behind each type label; Tool is ours, FAIRsharing registers no software.
TYPES = {
    'Standard: model/format': ('Standard', 'model_and_format', 4, 'Data or metadata model, schema, exchange format.'),
    'Standard: terminology artefact': ('Standard', 'terminology_artefact', 6,
                                       'Ontology, controlled vocabulary, thesaurus or glossary.'),
    'Standard: reporting guideline': ('Standard', 'reporting_guideline', 7,
                                      'Minimum information checklist or reporting template.'),
    'Standard: identifier schema': ('Standard', 'identifier_schema', 8, 'Identifier scheme or resolver.'),
    'Standard: principle': ('Standard', 'principle', 17, 'Published set of principles with a reusable artefact.'),
    'Database: repository': ('Database', 'repository', 1, 'Archive that accepts data deposits.'),
    'Database: knowledgebase': ('Database', 'knowledgebase', 2, 'Curated knowledge resource or data portal.'),
    'Database: knowledgebase and repository': ('Database', 'knowledgebase_and_repository', 3,
                                               'Both a curated knowledge resource and an archive.'),
    'Policy: journal': ('Policy', 'journal', 9, 'Data policy of a journal.'),
    'Policy: journal publisher': ('Policy', 'journal_publisher', 10, 'Data policy of a publisher.'),
    'Policy: society': ('Policy', 'society', 11, 'Policy or guidance of a learned society.'),
    'Policy: funder': ('Policy', 'funder', 12, 'Data policy of a funder.'),
    'Policy: project': ('Policy', 'project', 13, 'Policy or guidance issued by a project.'),
    'Policy: institution': ('Policy', 'institution', 14,
                            'Policy or guidance issued by an institution or agency, such as OECD guidance.'),
    'Collection': ('Collection', 'collection', 15, 'Curated collection of standards, databases and policies.'),
    'Tool': ('Tool', None, None, 'Software or service; FAIRsharing does not register these.'),
}
SCOPE = {
    'Generic': 'Infrastructure not specific to a research domain, including FAIR resources such as the FIP.',
    'Life Sciences': 'Life-science infrastructure, not specific to toxicology, that toxicology uses.',
    'Toxicology': 'Made for toxicology, including toxicology instances of generic resources.',
}
# Who created a toxicology resource; several may apply. Information, plotted as an alternative lane layout.
STAKEHOLDER = {
    'Wet-lab research': 'Made by experimental (wet-lab) researchers, mostly academic.',
    'In silico research': 'Made by computational researchers: modellers, AOP, PBK, QSAR, informatics and data '
                          'stewards.',
    'Regulator': 'Made by a regulatory agency or intergovernmental body, such as OECD, EFSA, ECHA or US EPA.',
}
# The lifecycle phase of a toxicology resource: the phase it acts on; if several, the earliest at which it must be
# applied. Every phase it acts on is recorded as its span.
PHASES = {
    'Data generation': 'Planning, producing and depositing primary records: datasets, protocols, method descriptions '
                       'and the publications reporting them.',
    'Data integration': 'Integrating and synthesising those records into secondary resources and evidence: curated '
                        'databases, knowledge bases, ontologies, pathway networks and models.',
    'Regulatory assessment': 'Assessing records and secondary resources for reliability and relevance in a regulatory '
                             'context and integrating them into weight of evidence and decisions.',
}
LANE_DEF = {
    'Generic infrastructure': 'Resources not specific to a research domain.',
    'Life sciences infrastructure': 'Life-science resources, not specific to toxicology, that toxicology uses.',
    'Data generation': 'Toxicology resources whose phase, the earliest they act on, is data generation.',
    'Data integration': 'Toxicology resources whose phase, the earliest they act on, is data integration.',
    'Regulatory assessment': 'Toxicology resources whose phase, the earliest they act on, is regulatory assessment.',
}
LANES = list(LANE_DEF)
TOX_LANES = LANES[2:]
LANE_OF_PHASE = dict(zip(PHASES, TOX_LANES))
# The alternative layout of the toxicology lanes: by creator type, with one lane for resources made jointly.
CREATOR_LANE_DEF = {
    'Made by wet-lab research': 'Toxicology resources made by wet-lab research only.',
    'Made by in silico research': 'Toxicology resources made by in silico research only.',
    'Made by regulators': 'Toxicology resources made by regulators only.',
    'Made jointly': 'Toxicology resources made by two or more creator types together.',
}
CREATOR_LANE_OF = dict(zip(STAKEHOLDER, CREATOR_LANE_DEF))
# Relation labels that make a toxicology resource count as building on FAIR when they point to a Generic resource.
BUILDS_ON = ('implements', 'extends', 'profiles', 'recommends')
FAIR_PUBLISHED = 2016   # the FAIR guiding principles: only later resources can build on FAIR
SUBDOMAINS = {
    'in vitro toxicology': 'Toxicology studied in vitro: in the laboratory, usually with isolated organ, tissue, cell or '
                           'biochemical systems (after IUPAC, 1993, doi:10.1351/pac199365092003).',
    'nanotoxicology': 'Data generation.',
    'exposome': 'Data generation.',
    'eco-toxicology': 'Data generation.',
    'toxicogenomics': 'Integration and tools.',
    'AOP-based mechanistic knowledge': 'Integration and tools.',
    'computational and predictive toxicology': 'Integration and tools.',
    'regulatory toxicology': 'Toxicology that collects, processes and evaluates experimental and epidemiological data as '
                             'the basis for decisions that protect health from the harmful effects of chemical '
                             'substances, and that develops standard protocols and new test methods for them (after '
                             'Schwenk et al., 2002, doi:10.1016/S0378-4274(01)00457-X).',
}
# The lane each sub-domain belongs to in the manuscript (Figure 2 caption): used to group the dashboard filters.
SUBDOMAIN_LANE = {s: ('Data generation' if i < 4 else 'Data integration' if i < 7 else 'Regulatory assessment')
                  for i, s in enumerate(SUBDOMAINS)}
DATE_BASIS = {
    'publication': 'Online publication of the paper that first describes the resource.',
    'release': 'First public release or launch.',
    'adoption': 'Official adoption or publication of guidance or policy.',
    'FAIRsharing year': "FAIRsharing's year of creation, used only when nothing better was found.",
}
MAINTAINED = {
    'active': 'Maintained and available.',
    'discontinued': 'No longer maintained or available (shown with a dagger).',
    'in development': 'Not yet released in a stable form.',
    'unknown': 'Status could not be established.',
}
MANUSCRIPT = {
    'cited': 'Named in the manuscript text with a reference.',
    'named': 'Named in the manuscript text without a reference.',
    'comment only': 'Named only in a comment or to-do note of the manuscript.',
    'absent': 'Not in the manuscript.',
}
# The ELIXIR Toxicology Community documents whose mentions curators tick (criteria, section 2).
ETC_DOCUMENTS = {
    'Whitepaper': 'Martens et al. 2023, "ELIXIR and Toxicology: a community in development", F1000Research, '
                  'doi 10.12688/f1000research.74502.2.',
    'FAIRSharing': "FAIRsharing's report on the ELIXIR Toxicology Community collection, 3 Jul 2025, "
                   'doi 10.5281/zenodo.15799783.',
    **{f'INTOXICOM {n}': f'Report of INTOXICOM workshop {n}.' for n in (1, 2, 3, 5)},
}
MATCH = {
    'confirmed': 'The FAIRsharing record is this resource.',
    'to check': 'A FAIRsharing record was proposed and needs a curator.',
    'no record': 'FAIRsharing has no record for this resource.',
}
# The FAIRsharing record-association labels used here (id, lineage, definition). Read "subject label target".
RELATIONS = {
    'implements': (1, True, 'The database implements the standard.'),
    'extends': (8, True, 'The subject builds on and extends the target.'),
    'profiles': (7, True, 'The standard is a profile of the target standard.'),
    'recommends': (11, True, 'The policy recommends the target.'),
    'deprecates': (9, True, 'The subject replaces the target.'),
    'related_to': (4, False, 'The resources are related without one building on the other.'),
}
# Registry pairs FAIRsharing allows per label (GET https://api.fairsharing.org/record_associations/allowed, 5 Oct 2026).
ALLOWED = {
    'implements': {('Database', 'Standard')},
    'extends': {('Database', 'Database'), ('Standard', 'Standard'), ('Policy', 'Policy')},
    'profiles': {('Standard', 'Standard')},
    'recommends': {('Policy', 'Database'), ('Policy', 'Standard'), ('Policy', 'Collection')},
    'deprecates': {('Database', 'Database'), ('Standard', 'Standard'), ('Policy', 'Policy'),
                   ('Collection', 'Collection')},
    'related_to': {('Database', 'Database'), ('Database', 'Standard'), ('Standard', 'Standard'),
                   ('Standard', 'Database'), ('Policy', 'Policy')},
}
# FIP ontology properties, used as is: a FIP row is declared-by its community, and each FIP Declaration added to it
# when the site is built (dct:hasPart) declares-...-of a target. Not lineage and not enterable in FAIRsharing.
FIP_PROPERTIES = {
    'declares-current-use-of': 'The FIP declares that its community uses the target.',
    'declares-planned-use-of': 'The FIP declares that its community plans to use the target.',
    'declares-planned-development-of': 'The FIP declares that its community plans to develop the target.',
    'declares-planned-replacement-of': 'The FIP declares that its community plans to replace the target.',
    'declared-by': 'The FIP is declared by the target, a FAIR Implementation Community.',
}
EVIDENCE = {
    'manuscript': 'Stated in the manuscript.',
    'FAIRsharing': 'Asserted by FAIRsharing.',
    'literature': 'Stated in the literature or on the resource website.',
    'curator': 'Added by a curator.',
    'FIP': 'Declared in a FAIR Implementation Profile.',
}
# FSR type (fsrType): a type of the FSR typology of the FIP ontology, or FAIR Implementation Community for a community
# (see fsr_offered). The typology, as the ontology draws it, has a column for each of these classes.
FSR, FER, FIC = FIP + 'FAIR-Supporting-Resource', FIP + 'FAIR-Enabling-Resource', FIP + 'FAIR-Implementation-Community'
TYPOLOGY = [FIP + t for t in ('FAIR-Data-Policy', 'FAIR-Specification', 'FAIR-Supporting-Technology')]

VOCABULARIES = {
    'decision': DECISION, 'exclusionReason': EXCLUSION, 'fairsharingType': {k: v[3] for k, v in TYPES.items()},
    'scope': SCOPE, 'phase': PHASES, 'creatorType': STAKEHOLDER, 'lane': LANE_DEF, 'creatorLane': CREATOR_LANE_DEF,
    'subdomains': SUBDOMAINS, 'dateBasis': DATE_BASIS, 'maintained': MAINTAINED, 'manuscript': MANUSCRIPT,
    'fairsharingMatch': MATCH, 'hadRole': {k: v[2] for k, v in RELATIONS.items()}, 'declaration': FIP_PROPERTIES,
    'evidence': EVIDENCE, 'mentionedIn': ETC_DOCUMENTS,
}

# ---- JSON-LD shape ---------------------------------------------------------------------------------------------------

SCHEMA = rdflib.Namespace('http://schema.org/')   # as schema.org's own JSON-LD context and CDIF write it
# Controlled values that are outside concepts: the graph uses their IRIs and the dataset defines no term for them.
NCIT_TOXICOLOGY = 'http://purl.obolibrary.org/obo/NCIT_C17206'
IUPAC = 'https://doi.org/10.1351/goldbook.'   # IUPAC Gold Book, which holds the IUPAC glossary of terms used in toxicology
T4FS, EDAM, MESH = 'http://purl.obolibrary.org/obo/T4FS_', 'http://edamontology.org/', 'http://id.nlm.nih.gov/mesh/'
WIKIDATA = 'http://www.wikidata.org/entity/'
VHP = 'https://vhp4safety.github.io/glossary#'   # VHP4Safety glossary
SAME = {
    'scope': {'Generic': 'http://www.fairsharing.org/ontology/subject/SRAO_0000401',   # FAIRsharing's subjects
              'Life Sciences': 'http://aims.fao.org/aos/agrovoc/c_4318', 'Toxicology': NCIT_TOXICOLOGY},
    'subdomains': {'in vitro toxicology': WIKIDATA + 'Q6013136', 'nanotoxicology': IUPAC + '15908', 'eco-toxicology': MESH + 'D054750',
                   'exposome': MESH + 'D000081413', 'toxicogenomics': 'http://purl.obolibrary.org/obo/NCIT_C20179',
                   'AOP-based mechanistic knowledge': MESH + 'D000073931',
                   'computational and predictive toxicology': IUPAC + '15583'},
    'creatorType': {'Wet-lab research': 'http://www.ebi.ac.uk/efo/EFO_0009741',       # experimental scientist
                     'In silico research': 'http://www.ebi.ac.uk/efo/EFO_0009742',     # computational scientist
                     'Regulator': 'http://semanticscience.org/resource/SIO_000619'},   # regulatory authority
    'maintained': {'in development': 'http://purl.org/adms/status/UnderDevelopment',
                   'discontinued': 'http://publications.europa.eu/resource/authority/dataset-status/DISCONT',
                   'unknown': 'http://purl.obolibrary.org/obo/NCIT_C17998'},   # left out of the published dataset
}
# Lists with values that have no outside concept, and so terms of ours, each list a concept scheme with this definition.
TERM_SETS = {
    'phase': 'Data life-cycle phases that a toxicology resource acts on.',
    'subdomains': 'Toxicology sub-domains that a resource serves, where no outside concept exists.',
    'maintained': 'Maintenance statuses of a resource, where no outside concept exists.',
    'hadRole': "FAIRsharing's labels for relations between records, read subject first.",
}
# A date is stored under the property of what it refers to, its basis (DataCite's date types Issued, Accepted and
# Created, as crosswalked to schema.org and DCTERMS; publication and release, both Issued, are told apart by schema.org's
# date of first publication and DCAT's release date); a date of unrecorded basis is a dct:date. The sheet shows each
# date as First published with its Date basis.
DATE_FIELDS = {'publication': 'datePublished', 'release': 'dateReleased', 'adoption': 'dateAdopted',
               'FAIRsharing year': 'dateCreated', '': 'date'}


def concept(name, value):
    """The IRI of a value of the list `name`: its outside concept, else a term of ours. A relation label names its
    term (terms#implements); any other value's term is <list>-<value> (terms#phase-data-generation)."""
    if value in SAME.get(name, {}):
        return SAME[name][value]
    if name == 'hadRole':
        return TERMS + value
    return f"{TERMS}{name}-{re.sub('[^a-z0-9]+', '-', value.lower()).strip('-')}"


def _values(term, name, vocab, **entry):
    """A context entry whose stored values expand to their concepts (a JSON-LD 1.1 property-scoped context)."""
    return {'@id': term, '@type': '@vocab', **entry, '@context': {v: concept(name, v) for v in vocab}}


# Every field the graph holds has an entry. There is no @vocab, so the others stay out of the graph: derived fields
# (phase is the earliest phase of the span; principles follow from the declarations), the curation fields, the sources
# and vocabularies, and the published FAIRsharing block (sources are linked through isBasedOn, terms by their IRIs).
CONTEXT = {
    '@version': 1.1,
    'schema': str(SCHEMA), 'dcat': 'http://www.w3.org/ns/dcat#', 'dct': 'http://purl.org/dc/terms/',
    'skos': 'http://www.w3.org/2004/02/skos/core#', 'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'fip': FIP,
    'prov': 'http://www.w3.org/ns/prov#', 'spdx': 'http://spdx.org/rdf/terms#',
    'identifier': {'@id': 'schema:identifier', '@type': '@id'},
    'name': 'schema:name', 'alternateName': {'@id': 'schema:alternateName', '@container': '@set'},
    'description': 'schema:description', 'url': 'schema:url',   # text, as CDIF requires
    'creator': 'schema:creator', 'version': 'schema:version', 'inLanguage': 'schema:inLanguage',
    'dateModified': 'schema:dateModified', 'license': {'@id': 'schema:license', '@type': '@id'},
    'creditText': 'schema:creditText', 'isBasedOn': {'@id': 'schema:isBasedOn', '@type': '@id'},
    'wasDerivedFrom': {'@id': 'prov:wasDerivedFrom', '@type': '@id'},
    'keywords': {'@id': 'schema:keywords', '@container': '@set'},
    'parentOrganization': {'@id': 'schema:parentOrganization', '@type': '@id'},
    'temporalCoverage': 'schema:temporalCoverage',
    'variableMeasured': {'@id': 'schema:variableMeasured', '@container': '@set'},
    'propertyID': {'@id': 'schema:propertyID', '@type': '@id'}, 'value': 'schema:value',
    'distribution': {'@id': 'schema:distribution', '@container': '@set'},
    'contentUrl': 'schema:contentUrl', 'encodingFormat': 'schema:encodingFormat',
    'conformsTo': {'@id': 'dct:conformsTo', '@type': '@id'},
    'checksum': 'spdx:checksum', 'algorithm': 'spdx:algorithm',
    'checksumValue': 'spdx:checksumValue',
    'subjectOf': 'schema:subjectOf', 'maintainer': 'schema:maintainer', 'theme': {'@id': 'dcat:theme', '@type': '@id'},
    'resource': {'@id': 'dcat:resource', '@type': '@id', '@container': '@set'}, 'about': {'@id': 'schema:about', '@type': '@id'},   # the catalog record
    'additionalType': {'@id': 'schema:additionalType', '@type': '@id'}, 'sdDatePublished': 'schema:sdDatePublished',
    'hasPart': {'@id': 'schema:hasPart', '@container': '@set'},
    'schemaType': '@type', 'key': 'dct:identifier', 'fairsharingType': 'schema:additionalType',
    'fsrType': {'@id': 'rdf:type', '@type': '@id', '@container': '@set'},
    'scope': _values('schema:about', 'scope', SCOPE),
    'subdomains': _values('schema:about', 'subdomains', SUBDOMAINS, **{'@container': '@set'}),
    'span': _values('dcat:theme', 'phase', PHASES, **{'@container': '@set'}),
    'qualifiedAttribution': {'@id': 'prov:qualifiedAttribution', '@container': '@set',   # derived from creatorType
                             '@context': {'hadRole': _values('dcat:hadRole', 'creatorType', STAKEHOLDER)}},
    'maintained': _values('schema:creativeWorkStatus', 'maintained', MAINTAINED),
    'datePublished': 'schema:datePublished', 'dateReleased': 'dct:issued', 'dateAdopted': 'dct:dateAccepted',
    'dateCreated': 'schema:dateCreated', 'date': 'dct:date',
    'dateSource': {'@id': 'schema:citation', '@type': '@id'},   # CDIF keeps subjectOf for the catalog record
    'fairsharingRecord': {'@id': 'schema:sameAs', '@type': '@vocab', '@context': {'@vocab': 'https://fairsharing.org/'}},
    'qualifiedRelation': {'@id': 'dcat:qualifiedRelation', '@container': '@set'},
    'relation': {'@id': 'dct:relation', '@type': '@id'},
    'hadRole': _values('dcat:hadRole', 'hadRole', RELATIONS),
    'fipDeclaration': {'@id': 'schema:hasPart', '@container': '@set'},
    'question': {'@id': 'fip:refers-to-question', '@type': '@id'}, 'considerations': 'fip:considerations',
    **{p: {'@id': 'fip:' + p, '@type': '@id'} for p in FIP_PROPERTIES},
    'fsr': {'@id': 'schema:sameAs', '@type': '@id', '@container': '@set'},
}
# Links from a value's concept to outside concepts: (list, value, SKOS mapping property, outside concept). Some link
# an outside concept the dataset uses to another one, such as the IUPAC entry of a MeSH concept.
TERM_LINKS = [
    ('phase', 'Data generation', SKOS.closeMatch, T4FS + '0000108'),              # data production
    ('phase', 'Data generation', SKOS.closeMatch, EDAM + 'topic_3077'),           # data acquisition
    ('phase', 'Data integration', SKOS.closeMatch, T4FS + '0000487'),             # data integration
    ('phase', 'Data integration', SKOS.closeMatch, EDAM + 'topic_3366'),          # data integration and warehousing
    ('phase', 'Regulatory assessment', SKOS.relatedMatch, MESH + 'D018570'),      # risk assessment
    ('phase', 'Regulatory assessment', SKOS.relatedMatch, EDAM + 'topic_3394'),   # regulatory affairs
    ('phase', 'Regulatory assessment', SKOS.relatedMatch, T4FS + '0000507'),      # data quality
    ('phase', 'Regulatory assessment', SKOS.relatedMatch, IUPAC + '16194'),       # weight-of-evidence for toxicity
    ('phase', 'Regulatory assessment', SKOS.relatedMatch, VHP + 'VHP0000103'),    # safety assessment
    ('phase', 'Regulatory assessment', SKOS.relatedMatch, VHP + 'VHP0000159'),    # IATA
    ('phase', 'Regulatory assessment', SKOS.relatedMatch, VHP + 'VHP0000101'),    # risk assessment
    ('subdomains', 'regulatory toxicology', SKOS.relatedMatch, WIKIDATA + 'Q2448782'),   # regulatory science
    ('subdomains', 'regulatory toxicology', DCTERMS.source, 'https://doi.org/10.1016/S0378-4274(01)00457-X'),
    *[('subdomains', s, SKOS.broadMatch, o) for s in ('in vitro toxicology', 'regulatory toxicology')
      for o in (NCIT_TOXICOLOGY, IUPAC + 'T06417')],
    ('subdomains', 'eco-toxicology', SKOS.exactMatch, IUPAC + '14399'),
    ('subdomains', 'toxicogenomics', SKOS.exactMatch, IUPAC + '16156'),
    ('creatorType', 'Regulator', SKOS.closeMatch, 'http://purl.obolibrary.org/obo/OBI_0000450'),   # regulatory agency
    ('maintained', 'active', SKOS.closeMatch,
     'http://publications.europa.eu/resource/authority/distribution-status/ONGOING'),
    ('hadRole', 'implements', SKOS.closeMatch, FIP + 'implements'),
    ('hadRole', 'implements', SKOS.closeMatch, 'http://semanticscience.org/resource/SIO_000233'),
    ('hadRole', 'implements', SKOS.closeMatch, DCTERMS.conformsTo),
    ('hadRole', 'profiles', SKOS.exactMatch, 'http://www.w3.org/ns/dx/prof/isProfileOf'),
    ('hadRole', 'profiles', SKOS.broadMatch, DCTERMS.conformsTo),
    ('hadRole', 'extends', SKOS.closeMatch, 'http://purl.org/spar/cito/extends'),
    ('hadRole', 'extends', SKOS.broadMatch, SCHEMA.isBasedOn),
    ('hadRole', 'deprecates', SKOS.exactMatch, DCTERMS.replaces),
    ('hadRole', 'related_to', SKOS.exactMatch, DCTERMS.relation),
    ('hadRole', 'recommends', SKOS.broadMatch, DCTERMS.relation),
]


def term(field):
    """The term a field maps to, as the context writes it (schema:url); None for a field out of the graph."""
    entry = CONTEXT.get(field)
    return entry.get('@id') if isinstance(entry, dict) else entry


def iri(curie):
    """A compact IRI of the context (schema:url) in full."""
    prefix, _, local = curie.partition(':')
    return CONTEXT[prefix] + local


# Curated fields, in file order; edited in the Sheet. '@id', 'identifier', 'schemaType', 'buildsOnFair', 'fsrCategory',
# 'declaredIn' and 'principles' are derived, 'fsr' (a declared resource's IRIs in the FIPs) is imported; 'declared-by' and
# 'fipDeclaration' exist only in the built site, 'fairsharing' only in the site, the sheet and the submission export.
CURATED = ['key', 'name', 'alternateName', 'decision', 'exclusionReason', 'coveredBy', 'fairsharingType', 'fsrType', 'scope',
           'phase', 'span', 'creatorType', 'subdomains', *DATE_FIELDS.values(), 'dateSource', 'creator', 'url',
           'description', 'maintained', 'manuscript', 'manuscriptEvidence', 'mentionedIn', 'fairsharingRecord',
           'fairsharingMatch', 'reviewedBy', 'note']
FIELD_ORDER = ['@id', 'identifier', 'schemaType'] + CURATED + ['buildsOnFair', 'fsrCategory', 'declaredIn', 'principles',
                                                               'qualifiedAttribution', 'fsr', 'qualifiedRelation',
                                                               'declared-by', 'fipDeclaration',
                                                               'fairsharing']
RELATION_ORDER = ['relation', 'hadRole', 'evidence', 'source', 'reviewedBy', 'note']
LIST_FIELDS = {'alternateName', 'subdomains', 'creatorType', 'fsrType', 'span', 'mentionedIn'}
# Curated fields added after the Sheet went live count in the row fingerprint only once set: Row versions stay valid.
LATER = ('mentionedIn',)
KEY_RE = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
DATE_RE = re.compile(r'^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$')
FS_CODE_RE = re.compile(r'FAIRsharing\.[A-Za-z0-9]+')


def new_document(resources=()):
    return {
        '@context': CONTEXT, '@id': BASE, '@type': 'schema:Dataset',
        'name': 'FAIR implementation ecosystem for toxicology',
        'description': 'Standards, databases, policies and tools used in toxicology, each typed as a FAIR-Enabling '
                       'Resource or another FAIR Supporting Resource, curated '
                       'by the ELIXIR Toxicology Community together with the FAIRsharing Toxicology collection, with '
                       'first publication dates, FAIRsharing types, lifecycle phases, sub-domains and relations.',
        'version': __version__, 'dateModified': '', 'inLanguage': 'en', 'license': LICENSE, 'creator': CREATOR,
        'keywords': KEYWORDS, 'creditText': FAIRSHARING_CREDIT, 'isBasedOn': [COLLECTION_DOI],
        'sources': {}, 'vocabularies': VOCABULARIES, 'hasPart': list(resources),
    }


# The dataset header that does not change between saves (normalise() keeps it current).
LICENSE = {'@id': 'https://creativecommons.org/licenses/by-sa/4.0/', '@type': 'schema:CreativeWork', 'name': 'CC BY-SA 4.0',
           'url': 'https://creativecommons.org/licenses/by-sa/4.0/'}
CREATOR = {'@type': 'schema:Organization', 'name': 'ELIXIR Toxicology Community',
           'url': 'https://elixir-europe.org/communities/toxicology',
           'parentOrganization': {'@id': 'https://ror.org/044rwnt51', '@type': 'schema:Organization', 'name': 'ELIXIR'}}
KEYWORDS = [{'@id': i, '@type': 'schema:DefinedTerm', 'name': n, 'identifier': i} for n, i in (
    ('Toxicology', NCIT_TOXICOLOGY), ('FAIR Supporting Resource', FSR),
    ('FAIR Implementation Profile', FIP + 'FAIR-Implementation-Profile'), ('Data management', EDAM + 'topic_3071'))]
HEADER = ('description', 'inLanguage', 'license', 'creator', 'keywords')


def vocabulary(doc):
    """Our terms as RDF, for terms.ttl and terms.jsonld: each list in TERM_SETS as a schema:DefinedTermSet and
    skos:ConceptScheme <list>-values, with a term (schema:DefinedTerm and skos:Concept, named by concept()) for each
    value that has no outside concept. Its name is the stored value; its definition comes from the document."""
    t, head = rdflib.Namespace(TERMS), URIRef(TERMS[:-1])
    g = rdflib.Graph(bind_namespaces='none')
    for prefix, ns in (('terms', TERMS), ('fip', FIP), ('schema', SCHEMA), ('dct', DCTERMS), ('skos', SKOS),
                       ('rdf', RDF), ('rdfs', RDFS), ('owl', OWL)):
        g.bind(prefix, ns)
    g += [(head, RDF.type, OWL.Ontology), (head, RDFS.label, Literal(f"Terms of the {doc['name']}")),
          (head, OWL.versionInfo, Literal(doc['version'])), (head, DCTERMS.license, URIRef(LICENSE['@id']))]
    for name, about in TERM_SETS.items():           # each a concept scheme of the CDIF Concept Scheme profile
        s = t[name + '-values']
        g += [(s, RDF.type, SCHEMA.DefinedTermSet), (s, RDF.type, SKOS.ConceptScheme), (s, SCHEMA.name, Literal(name + ' values')),
              (s, SKOS.prefLabel, Literal(name + ' values')), (s, SKOS.definition, Literal(about)),
              (s, DCTERMS.conformsTo, URIRef('https://w3id.org/cdif/conceptscheme/1.1'))]
        for value, definition in doc['vocabularies'][name].items():
            if value not in SAME.get(name, {}):
                c = URIRef(concept(name, value))
                g += [(c, RDF.type, SCHEMA.DefinedTerm), (c, RDF.type, SKOS.Concept), (c, SCHEMA.name, Literal(value)),
                      (c, SKOS.prefLabel, Literal(value)), (c, SCHEMA.description, Literal(definition)),
                      (c, SKOS.definition, Literal(definition)), (c, SCHEMA.termCode, Literal(c[len(TERMS):])),
                      (c, SCHEMA.inDefinedTermSet, s), (c, SKOS.inScheme, s), (s, SKOS.hasTopConcept, c)]
    g += [(URIRef(concept(name, value)), p, URIRef(o)) for name, value, p, o in TERM_LINKS]
    return g


# ---- derived values --------------------------------------------------------------------------------------------------

def lane(r):
    """Dashboard lane by phase (display only, never stored): generic and life-science resources have
    their own lanes; a toxicology resource sits in the lane of its phase."""
    if r.get('scope') == 'Generic':
        return 'Generic infrastructure'
    if r.get('scope') == 'Life Sciences':
        return 'Life sciences infrastructure'
    return LANE_OF_PHASE.get(r.get('phase'), '')


def creator_lane(r):
    """Dashboard lane by creator: the toxicology lanes follow the creator types, 'Made jointly' for several."""
    if r.get('scope') != 'Toxicology':
        return lane(r)
    types = r.get('creatorType') or []
    if len(types) > 1:
        return 'Made jointly'
    return CREATOR_LANE_OF.get(types[0], '') if types else ''


def registry(r):
    t = TYPES.get(r.get('fairsharingType'))
    return t[0] if t else None


@functools.cache
def fip_ontology():
    """The FIP ontology as a graph: from the local cache, read from its IRI first when the cache has none."""
    if not os.path.exists(FIP_ONTOLOGY):
        text = web.get(FIP, 'text/turtle')
        os.makedirs(os.path.dirname(FIP_ONTOLOGY), exist_ok=True)
        with open(FIP_ONTOLOGY, 'w', encoding='utf-8') as f:
            f.write(text)
    return rdflib.Graph().parse(FIP_ONTOLOGY, format='turtle')


def fip_ontology_version():
    g = fip_ontology()
    return str(g.value(g.value(None, DCTERMS.isVersionOf, URIRef(FIP + 'FIP-Ontology')), RDFS.label))


@functools.cache
def fsr_types():
    """Every class under FAIR Supporting Resource in the FIP ontology: IRI -> (label, direct FSR subclass, FER).
    FAIR-Enabling Resource does not count as a direct FSR subclass here: an FER type keeps its other one, such as
    FAIR specification."""
    sub, fsr, fer = rdflib.RDFS.subClassOf, rdflib.URIRef(FSR), rdflib.URIRef(FER)
    g, out = fip_ontology(), {}
    direct = set(g.subjects(sub, fsr)) - {fer}
    for c in set(g.transitive_subjects(sub, fsr)) - {fsr}:
        up = set(g.transitive_objects(c, sub)) - {c}
        out[str(c)] = (str(g.value(c, rdflib.RDFS.label)), str(next(iter(up & direct), c)), c == fer or fer in up)
    return out


@functools.cache
def fsr_offered():
    """The FSR types offered: the FSR typology as the ontology draws it, the classes under a TYPOLOGY class and one
    level below that are not deprecated, and FAIR Implementation Community."""
    g, sub = fip_ontology(), rdflib.RDFS.subClassOf
    gone = set(g.subjects(rdflib.RDF.type, rdflib.OWL.DeprecatedClass))
    first = {c for b in TYPOLOGY for c in g.subjects(sub, URIRef(b))} - gone
    second = {c for m in first for c in g.subjects(sub, m)} - gone
    return sorted({str(c) for c in first | second} | {FIC})


def fs_ref(value):
    """Normalise a FAIRsharing reference (DOI, URL, code, numeric id or legacy bsg- id) to 'FAIRsharing.xxx', a numeric
    string or 'bsg-xxx'."""
    value = str(value or '').strip()
    m = FS_CODE_RE.search(value)
    if m:
        return m.group(0)
    m = re.fullmatch(r'(?:https?://(?:www\.)?fairsharing\.org/(?:fairsharing_records/)?)?(\d+|bsg-[a-z]?\d+)/?', value)
    return m.group(1) if m else value


def slug(text, taken=()):
    """A new key from a name or abbreviation, unique among `taken`."""
    words = [w for w in re.split(r'[^a-z0-9]+', str(text).lower()) if w]
    base = ''
    for w in words:                                   # whole words only, at most 32 characters
        if base and len(base) + 1 + len(w) > 32:
            break
        base = f'{base}_{w}' if base else w[:32]
    base = base or 'resource'
    key, n = base, 2
    while key in taken:
        key, n = f'{base}_{n}', n + 1
    return key


def iri_of(r):
    if FIC in r.get('fsrType', []) and NANOPUB_RE.match(r.get('@id') or ''):
        return r['@id']                                     # a FIC is identified by its FIC nanopublication
    code = fs_ref(r.get('fairsharingRecord'))
    if r.get('fairsharingMatch') == 'confirmed' and code.startswith('FAIRsharing.'):
        return 'https://doi.org/10.25504/' + code
    return BASE + '#' + r['key']


def normalise(doc):
    """Derive @id, buildsOnFair and the FSR and FIP fields, order fields, sort resources and relations, keep relation
    targets in step with @ids."""
    old_ids = {r.get('@id'): r['key'] for r in doc['hasPart']}
    for r in doc['hasPart']:
        for f in CURATED:                                   # no stray spaces in curated text
            if isinstance(r.get(f), str):
                r[f] = r[f].strip()
            elif isinstance(r.get(f), list):
                r[f] = [x.strip() if isinstance(x, str) else x for x in r[f]]
        for f, vocab in (('subdomains', SUBDOMAINS), ('creatorType', STAKEHOLDER), ('span', PHASES),
                         ('mentionedIn', ETC_DOCUMENTS)):
            if r.get(f):                                    # one canonical order, so round trips are exact
                known = [x for x in vocab if x in r[f]]
                r[f] = known + [x for x in r[f] if x not in vocab]
        if r.get('fairsharingRecord'):
            r['fairsharingRecord'] = fs_ref(r['fairsharingRecord'])
        if 'dateBasis' in r and (r['dateBasis'] or '') in DATE_FIELDS:   # a date as the sheet and the imports give
            date, basis = r.pop('datePublished', ''), r.pop('dateBasis') or ''   # it: first published, date basis
            for f in DATE_FIELDS.values():
                r.pop(f, None)
            if date:
                r[DATE_FIELDS[basis]] = date
        r['@id'] = iri_of(r)
        r['identifier'] = r['@id']
        r['schemaType'] = 'schema:SoftwareApplication' if r.get('fairsharingType') == 'Tool' else 'schema:CreativeWork'
    new_ids = {r['key']: r['@id'] for r in doc['hasPart']}
    target = lambda v: new_ids.get(old_ids.get(v, v.removeprefix(BASE).lstrip('#')), v)   # an @id, or #key
    declared = {}                                           # target @id -> [(FIP @id, principle)]
    for r in doc['hasPart']:
        for q in r.get('qualifiedRelation', []):
            q['relation'] = target(q['relation'])
        for d in r.get('fipDeclaration', []):
            for p in FIP_PROPERTIES.keys() & d.keys():
                declared.setdefault(d[p], []).append((r['@id'], d.get('principle')))
    by_id = {r['@id']: r for r in doc['hasPart']}
    for r in doc['hasPart']:                                # derived: a toxicology resource building on FAIR
        fair = r.get('scope') == 'Toxicology' and (_year(r) or 0) >= FAIR_PUBLISHED and any(
            q.get('hadRole') in BUILDS_ON and (by_id.get(q['relation']) or {}).get('scope') == 'Generic'
            for q in r.get('qualifiedRelation', []))
        if fair:
            r['buildsOnFair'] = True
        else:
            r.pop('buildsOnFair', None)
        types = [fsr_types()[t] for t in r.get('fsrType', []) if t in fsr_types()]
        r['fsrCategory'] = (FER if types[0][2] else FSR) if types else ''
        r['qualifiedAttribution'] = [{'@type': 'prov:Attribution', 'hadRole': t} for t in r.get('creatorType', [])]
        r['declaredIn'] = sorted({fip for fip, _ in declared.get(r['@id'], [])})
        r['principles'] = sorted({p for _, p in declared.get(r['@id'], []) if p})
    doc['hasPart'] = sorted((_ordered(r) for r in doc['hasPart']), key=lambda r: r['key'])
    doc['@context'] = CONTEXT
    doc['@id'] = BASE
    doc['vocabularies'] = VOCABULARIES
    doc['version'] = __version__
    doc.update({k: new_document()[k] for k in HEADER})
    return doc


def _ordered(r):
    out = {k: r[k] for k in FIELD_ORDER if r.get(k) not in (None, '', [], {})}
    out.update({k: v for k, v in r.items() if k not in out and v not in (None, '', [], {})})
    if 'qualifiedRelation' in out:
        rels = [{k: q[k] for k in RELATION_ORDER if q.get(k) not in (None, '')} for q in out['qualifiedRelation']]
        out['qualifiedRelation'] = sorted(rels, key=lambda q: (q['relation'].removeprefix(BASE), q['hadRole']))   # own
        # targets first, as when their @ids were relative, so the sheet keeps its row order
    return out


# ---- validation ------------------------------------------------------------------------------------------------------

def check(doc):
    """Return (errors, warnings). Errors block a save; warnings fail only `fairtox validate --strict`."""
    errors, warnings = [], []
    if fip_ontology_version() != FIP_ONTOLOGY_VERSION:
        warnings.append(f'the FIP ontology is now {fip_ontology_version()!r}; the types were checked against '
                        f'{FIP_ONTOLOGY_VERSION!r}')
    rs = doc.get('hasPart', [])
    keys = [r.get('key') for r in rs]
    by_key = {r.get('key'): r for r in rs}
    by_id = {r.get('@id'): r for r in rs}
    for k in {k for k in keys if keys.count(k) > 1}:
        errors.append(f'{k}: duplicate key')
    ids = [r.get('@id') for r in rs]
    for k in {r.get('key') for r in rs if ids.count(r.get('@id')) > 1}:
        errors.append(f'{k}: has the same identifier as another row')
    today = dt.date.today()
    for r in rs:
        k = r.get('key')
        e = errors.append
        if not isinstance(k, str) or not KEY_RE.match(k):
            e(f'{k!r}: key must be lowercase letters, digits, _ or -')
            continue
        if not r.get('name'):
            e(f'{k}: name is empty')
        for field, vocab in (('decision', DECISION), ('fairsharingType', TYPES), ('scope', SCOPE), ('phase', PHASES),
                             ('dateBasis', DATE_BASIS), ('maintained', MAINTAINED), ('manuscript', MANUSCRIPT),
                             ('fairsharingMatch', MATCH), ('exclusionReason', EXCLUSION)):
            if r.get(field) not in (None, '') and r[field] not in vocab:
                e(f'{k}: {field} {r[field]!r} is not an allowed value')
        if r.get('decision') not in DECISION:
            e(f'{k}: decision is required')
        if (r.get('decision') == 'exclude') != bool(r.get('exclusionReason')):
            e(f'{k}: an exclusion reason is required exactly when the decision is exclude')
        if r.get('exclusionReason') == 'E6' and r.get('coveredBy') not in by_key:
            e(f'{k}: exclusion reason E6 needs Covered by naming another row')
        if r.get('coveredBy') and (r['coveredBy'] not in by_key or r['coveredBy'] == k):
            e(f'{k}: covered by {r["coveredBy"]!r} is not another row')
        if r.get('decision') != 'exclude' and FIC not in r.get('fsrType', []):   # excluded rows and communities
            if (r.get('scope') == 'Toxicology') != bool(r.get('phase')):            # are not plotted
                e(f'{k}: a phase is required exactly when the scope is Toxicology')
            if (r.get('scope') == 'Toxicology') != bool(r.get('creatorType')):
                e(f'{k}: at least one creator type is required exactly when the scope is Toxicology')
        for s in r.get('creatorType', []) if isinstance(r.get('creatorType'), list) else []:
            if s not in STAKEHOLDER:
                e(f'{k}: creator type {s!r} is not an allowed value')
        for d in r.get('mentionedIn', []):
            if d not in ETC_DOCUMENTS:
                e(f'{k}: community document {d!r} is not an allowed value')
        for s in r.get('subdomains', []):
            if s not in SUBDOMAINS:
                e(f'{k}: sub-domain {s!r} is not an allowed value')
        span = r.get('span') or []
        for s in span:
            if s not in PHASES:
                e(f'{k}: span {s!r} is not a phase')
        if (span or r.get('phase')) and next((p for p in PHASES if p in span), None) != r.get('phase'):
            e(f'{k}: the span must contain the phase as its earliest phase')
        types = r.get('fsrType') or []
        for t in types:
            if t not in fsr_offered():
                e(f'{k}: FSR type {t!r} is not an allowed value')
        if len(types) > 1:
            e(f'{k}: one FSR type only')
        if FIC in types and not NANOPUB_RE.match(r.get('@id') or ''):
            e(f'{k}: FAIR Implementation Community needs its FIC nanopublication as @id')
        for field in LIST_FIELDS:
            if not isinstance(r.get(field, []), list):
                e(f'{k}: {field} must be a list')
        dates = [f for f in DATE_FIELDS.values() if r.get(f)]
        if len(dates) > 1:
            e(f'{k}: one date only, under the field of its basis, not {", ".join(dates)}')
        d = first_date(r)[0]
        if d:
            m = DATE_RE.match(str(d))
            try:
                ok = bool(m) and 1900 <= int(m.group(1)) <= today.year and \
                    dt.date(int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1)) <= today
            except ValueError:
                ok = False
            if not ok:
                e(f'{k}: first published {d!r} must be YYYY, YYYY-MM or YYYY-MM-DD and not in the future')
        for field in ('url', 'dateSource'):
            if r.get(field) and not re.match(r'^https?://\S+$', r[field]):
                e(f'{k}: {field} {r[field]!r} must be an http(s) URL')
        seen = set()
        for q in r.get('qualifiedRelation', []):
            t = by_id.get(q.get('relation'))
            role = q.get('hadRole')
            if t is None:
                e(f'{k}: relation target {q.get("relation")!r} is not in the dataset')
                continue
            if t is r:
                e(f'{k}: relation to itself')
            if role not in RELATIONS:
                e(f'{k}: relation {role!r} is not an allowed label')
            if q.get('evidence') not in EVIDENCE:
                e(f'{k}: relation evidence {q.get("evidence")!r} is not an allowed value')
            if (t['key'], role) in seen:
                e(f'{k}: duplicate relation {role} {t["key"]}')
            seen.add((t['key'], role))
            if role in RELATIONS and RELATIONS[role][1] and q.get('evidence') != 'FAIRsharing' and \
                    _year(r) and _year(t) and _year(r) < _year(t):
                warnings.append(f'{k}: {role} {t["key"]} points to a resource first published later')
        if r.get('decision') == 'include':
            missing = (['first published'] if not first_date(r)[0] else []) + \
                [f for f in ('dateSource', 'url', 'fairsharingType', 'fsrType', 'scope') if not r.get(f)]
            if r.get('fairsharingMatch') != 'confirmed' and not r.get('description'):
                missing.append('description')
            if missing:
                warnings.append(f'{k}: included but missing {", ".join(missing)}')
            if r.get('fairsharingMatch') == 'to check':
                warnings.append(f'{k}: FAIRsharing match still to check')
    return errors, warnings


def first_date(r):
    """(date, basis): when the resource first became public, and what that date refers to; ('', '') when unknown."""
    return next(((r[f], basis) for basis, f in DATE_FIELDS.items() if r.get(f)), ('', ''))


def _year(r):
    m = DATE_RE.match(str(first_date(r)[0]))
    return int(m.group(1)) if m else None


# ---- load, save, change log ------------------------------------------------------------------------------------------

def load(path=DATASET):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def dumps(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + '\n'


def _stable(doc):
    """The document without dateModified, to decide whether a save changes anything."""
    d = copy.deepcopy(doc)
    d.pop('dateModified', None)
    return d


def save(doc, path=DATASET):
    """Normalise, validate and write atomically. Returns False when nothing but timestamps would change."""
    doc = normalise(doc)
    errors, _ = check(doc)
    if errors:
        raise ValueError('dataset not saved:\n  ' + '\n  '.join(errors))
    if os.path.exists(path) and _stable(load(path)) == _stable(doc):
        return False
    doc['dateModified'] = dt.date.today().isoformat()
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(dumps(doc))
    os.replace(tmp, path)
    return True


def row_hash(r):
    """Short fingerprint of a resource's curated fields. The Sheet carries it per row, so ingest can refuse an edit
    to a row that changed in the dataset after the Sheet was built, while rows nobody touched merge cleanly."""
    fields = [r.get(k) for k in CURATED if k not in LATER] + [[k, r[k]] for k in LATER if r.get(k)]
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()[:10]


def relation_hash(x):
    """Short fingerprint of a relation row (relation_rows): the Sheet carries it per line, like a row's version."""
    fields = [x[k] for k in ('subject', 'hadRole', 'target', 'evidence', 'source', 'reviewedBy', 'note')]
    return hashlib.sha256(json.dumps(fields).encode()).hexdigest()[:10]


def relation_of(field, old, new):
    """The label and target that a change-log line about a relation names: field 'relation' adds or removes one
    ('label target' as new or old), 'relation label target field' changes one of its fields."""
    return tuple((old if new == '(removed)' else new).split()[:2] if field == 'relation' else field.split()[1:3])


def relation_rows(doc):
    """Relations as flat rows: subject key, label, target key, evidence, source, reviewedBy, note."""
    key_of = {r['@id']: r['key'] for r in doc['hasPart']}
    return [{'subject': r['key'], 'hadRole': q['hadRole'], 'target': key_of.get(q['relation'], q['relation']),
             'evidence': q.get('evidence', ''), 'source': q.get('source', ''), 'reviewedBy': q.get('reviewedBy', ''),
             'note': q.get('note', '')}
            for r in doc['hasPart'] for q in r.get('qualifiedRelation', [])]


def diff(old, new):
    """Field-level differences in curated fields and relations: (key, field, old, new)."""
    out = []
    a = {r['key']: r for r in old['hasPart']}
    b = {r['key']: r for r in new['hasPart']}
    for k in sorted(a.keys() - b.keys()):
        out.append((k, '(row)', a[k].get('name', ''), '(removed)'))
    for k in sorted(b.keys() - a.keys()):
        out.append((k, '(row)', '(new)', b[k].get('name', '')))
    for k in sorted(a.keys() & b.keys()):
        for f in CURATED[1:]:
            x, y = _text(a[k].get(f)), _text(b[k].get(f))
            if x != y:
                out.append((k, f, x, y))
    ra = {(x['subject'], x['hadRole'], x['target']): x for x in relation_rows(old)}
    rb = {(x['subject'], x['hadRole'], x['target']): x for x in relation_rows(new)}
    for t in sorted(ra.keys() - rb.keys()):
        out.append((t[0], 'relation', f'{t[1]} {t[2]}', '(removed)'))
    for t in sorted(rb.keys() - ra.keys()):
        out.append((t[0], 'relation', '(new)', f'{t[1]} {t[2]}'))
    for t in sorted(ra.keys() & rb.keys()):
        for f in ('evidence', 'source', 'reviewedBy', 'note'):
            if ra[t][f] != rb[t][f]:
                out.append((t[0], f'relation {t[1]} {t[2]} {f}', ra[t][f], rb[t][f]))
    return out


def _text(v):
    return '; '.join(v) if isinstance(v, list) else ('' if v is None else str(v))


def log_changes(changes, round_name, source, by=None, path=CHANGES):
    """Append (key, field, old, new) rows to the change log; `by` maps key -> curator initials. A change with a fifth
    item, such as a relation read back with its own Reviewed by, is logged under that name."""
    if not changes:
        return
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    today = dt.date.today().isoformat()
    with open(path, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['date', 'round', 'key', 'field', 'old', 'new', 'by', 'source'])
        for key, field, old, new_value, *who in changes:
            w.writerow([today, round_name, key, field, old, new_value, who[0] if who else (by or {}).get(key, ''),
                        source])
