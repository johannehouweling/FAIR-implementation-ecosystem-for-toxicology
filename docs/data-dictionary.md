# Data dictionary

The dataset is one JSON-LD file, `data/fair-tox-ecosystem.jsonld`, licensed CC BY-SA 4.0. It is a schema.org `Dataset` whose `hasPart` lists the resources. Each resource has its curated fields and its relations to other resources. The file stores only what is curated: FAIRsharing record data and the declarations of the toxicology FAIR Implementation Profiles (FIPs) are added when the outputs are built (see Fields added at build time). The file is written only by the `fairtox` commands, which validate every change and log curated changes in `data/changes.csv`.

## Identifiers

- A FAIR Implementation Community is identified by its FIC nanopublication, for example `http://purl.org/np/RAgsbUg4xWCe6Jgjm6aDAiHiRqb4U6PYbrRvqO3PrDxTk#FAIR-AOPs`.
- A resource with a confirmed FAIRsharing record is identified by the record DOI, for example `https://doi.org/10.25504/FAIRsharing.6hna78`, as in the FIP Wizard and the two toxicology FIPs. This follows the FIP ontology, for which a FAIR Supporting Resource has an identifier that resolves to machine-readable metadata about it; FAIRsharing notes that its DOI identifies its record rather than the resource itself.
- Any other resource is identified by `https://w3id.org/fair-tox/dataset#<key>`. These identifiers are provisional until the resource is registered in FAIRsharing or the namespace is registered at w3id.org.
- Each resource also states its identifier as `identifier`, and its homepage as `url`.
- Every identifier is written in full: the context sets no `@base`, which a context loaded by URL may not set.

## Dataset header

| Field | Meaning |
|---|---|
| `name, description` | Title and summary. |
| `version` | Semantic version, the same as the software and CITATION.cff, set by release-please from the commits: a release with new features is a minor version, one with only fixes or data refreshes a patch version. |
| `dateModified` | Date of the last change to the content. |
| `inLanguage` | `en`. |
| `license` | CC BY-SA 4.0 (name and URL), required because the dataset contains FAIRsharing data. |
| `creator` | An ordered list (`@list`): the authors in the order of the paper, each a `schema:Person` with `givenName`, `familyName`, their ORCID iD as `@id` and `identifier`, and their affiliations as `schema:Organization` with their ROR ID; then the ELIXIR Toxicology Community, an organisation within ELIXIR (ROR `https://ror.org/044rwnt51`). `CITATION.cff` lists the same people in the same order. |
| `funding` | The grants behind the dataset, its dashboard and the paper, each a `schema:MonetaryGrant` with a `name`, its `identifier` (the grant's DOI where the funder mints one, else its number as text) and its `funder` as a `schema:Organization` with its ROR ID. |
| `creditText` | Attribution to FAIRsharing; the published dataset adds the nanopublications of the two FIPs. |
| `isBasedOn` | The FAIRsharing Toxicology collection; the published dataset adds the profiles of the two FIPs. |
| `sources` | What each source contributed, with versions and checksums; `inventory` names a co-author's repository list and the keys of the resources taken from it. The published dataset keeps only `fairsharing` and `fip`, each with its retrieval date (see Fields added at build time). |
| `vocabularies` | Every controlled list with its definitions, so the file can be read on its own. |
| `hasPart` | The resources. |

The published dataset also has the fields that CODATA's CDIF Discovery profile 1.1 asks of a dataset; CI checks every build with CODATA's SHACL rules for the profile.

| Field | Meaning |
|---|---|
| `identifier` | Persistent identifier, as a `schema:PropertyValue`: the Zenodo DOI that stands for all versions, `https://doi.org/10.5281/zenodo.24215047`. |
| `url` | The dashboard. |
| `datePublished` | Release date (`date-released` in CITATION.cff). |
| `temporalCoverage` | Years in which the resources were first published, such as `1965/2026`. |
| `wasDerivedFrom` | The sources in `isBasedOn` (`prov:wasDerivedFrom`). |
| `variableMeasured` | Each resource field with its term and definition. |
| `distribution` | The JSON-LD file, the two CSV files and `terms.ttl`, each with its media type, the standard it follows and, except the dataset file itself, a SHA-256 checksum. |
| `subjectOf` | The catalog record (`dcat:CatalogRecord`), which names its maintainer, the ELIXIR Toxicology Community, and declares conformance to CDIF Core 1.1 and CDIF Discovery 1.1. |

## Resource fields

Curated fields are edited in the curation sheet; the column is given. `@id`, `identifier`, `schemaType`, `buildsOnFair`, `fsrCategory` and `principles` are derived on every save; `declaredIn`, `fipDeclaration`, `declared-by`, `fsrNanopublication` and `fairsharing` are added at build time and never stored. The term is the one the JSON-LD context maps the field to. A field without a term stays out of the RDF graph, as the context has no `@vocab`: the derived fields are there for people and the dashboard, the curation fields for the curators.

| Field | Sheet column | Term | Content |
|---|---|---|---|
| `@id` |  |  | FIC nanopublication of a FAIR Implementation Community, else the FAIRsharing DOI when the match is confirmed, else `https://w3id.org/fair-tox/dataset#key`. |
| `identifier` | Identifier | `schema:identifier` | Derived: the `@id` as an absolute IRI, the resource's persistent identifier. |
| `schemaType` |  | `rdf:type` | Derived: `schema:SoftwareApplication` for a tool, else `schema:CreativeWork`, next to the FSR types. |
| `key` | Key | `dct:identifier` | Stable short identifier: lowercase letters, digits, `_` or `-`. Never changes. |
| `name` | Name | `schema:name` | Full name. |
| `alternateName` | Aliases | `schema:alternateName` | Abbreviations and other names; the first short one is shown in the figure. |
| `decision` | Decision |  | Screening decision (list below). |
| `exclusionReason` | Exclusion reason |  | Code E1-E8 (criteria, section 4), required when the decision is exclude. |
| `coveredBy` | Covered by |  | Key of the row that covers this one; required when the exclusion reason is E6. |
| `fairsharingType` | FAIRsharing type | `schema:additionalType` | FAIRsharing registry and record type, or Tool (list below), as text. |
| `fsrType` | FSR type (multi-select) | `rdf:type` | FAIR Supporting Resource (FSR) types of the FIP ontology (list below; criteria, sections 5 and 6). |
| `origin` | Origin | `schema:about` | Where the resource comes from, what it was made for (list below). |
| `phase` | the earliest phase chosen in Phase |  | For toxicology resources: the earliest phase of `span` (list below; criteria, section 6). Required for included and undecided toxicology resources. Not in the graph. |
| `span` | Phase (multi-select) | `dcat:theme` | For toxicology resources: every phase it acts on, in phase order, starting with `phase`. |
| `creatorType` | one "Made by" column per creator type | via `qualifiedAttribution` | For toxicology resources: the kind of creator; several may apply (list below). Required for included and undecided toxicology resources. |
| `qualifiedAttribution` |  | `prov:qualifiedAttribution` | Derived from `creatorType`: one `prov:Attribution` per creator type, whose `dcat:hadRole` is its concept. |
| `buildsOnFair` | Builds on FAIR |  | Derived: true for a toxicology resource that builds on FAIR (criteria, section 6). |
| `fsrCategory` | Class |  | Derived from `fsrType`: FAIR-Enabling Resource or FAIR Supporting Resource (criteria, section 6). |
| `principles` | Principles |  | Derived: the FAIR principles the resource's FSR types enable in the FIP ontology, in FAIR order; empty when they enable none. The sheet's Principles tab counts them. |
| `declaredIn` | Declared in |  | Added at build time from the FIP declarations: the FIPs that declare the resource (below). |
| `fsr` | FIP identifiers | `schema:sameAs` | Stored by `fairtox fip --apply`: the IRIs under which the FIPs declare the resource, when they differ from its `@id`. Replaced on each import. |
| `subdomains` | Sub-domains (multi-select) | `schema:about` | Sub-domains that apply (list below). |
| `datePublished`, `dateReleased`, `dateAdopted`, `dateCreated`, `date` | First published, Date basis | `schema:datePublished`, `dct:issued`, `dct:dateAccepted`, `schema:dateCreated`, `dct:date` | When the resource first became public: `YYYY`, `YYYY-MM` or `YYYY-MM-DD`, in the one field of what the date refers to, its date basis (list below). |
| `dateSource` | Citation | `schema:citation` | DOI or URL that shows the date. |
| `creator` | Creator | `schema:creator` | Organisation(s) that made the resource, as information, or their ORCID or ROR links; the dashboard shows the names registered there, read when the page is built. |
| `contactPoint` | Contact | `dcat:contactPoint` | Who to contact about the resource: the ORCID of a person (`https://orcid.org/…`) or the ROR of an organisation (`https://ror.org/…`), as a link; several may be given. DCAT's term, as schema.org has no contact point for a creative work. Published in the JSON-LD only, not in resources.csv; the dashboard's details link each creator to its ROR when the RORs match the creators one to one, in order. |
| `url` | URL | `schema:url` | Main web address. |
| `description` | Description | `schema:description` | One to three sentences; needed to register the resource in FAIRsharing. |
| `maintained` | Maintained | `schema:creativeWorkStatus` | Maintenance status (list below); not published when unknown. |
| `manuscript` | In manuscript |  | Whether and how the manuscript names it (list below). Not published. |
| `manuscriptEvidence` | Manuscript evidence |  | Section and line numbers in the frozen manuscript draft. Not published. |
| `mentionedIn` | one "ETC" column per document |  | ELIXIR Toxicology Community documents that mention the resource, ticked by curators (list below). Not published. |
| `fairsharingRecord` | FAIRsharing record | `schema:sameAs` | FAIRsharing record code (`FAIRsharing.xxxxxx`), or the numeric id of a record without a DOI; in the graph, its record page `https://fairsharing.org/<code>`. For a confirmed record, the page carries FAIRsharing's subjects (subject areas) as `schema:about`, the property of `origin`, and its domains (kinds of data, entities and activities) as `dcat:theme`, the property of `span`: FAIRsharing's statements, read when the dataset is built and not curated. The sheet shows them in the grey columns FAIRsharing subjects, after Origin, and FAIRsharing domains, after Phase. |
| `resource` |  | `dcat:resource` | On the FAIRsharing Toxicology collection only, in the published dataset: the included resources that FAIRsharing lists as its members, read when the dataset is built. |
| `fairsharingMatch` | FAIRsharing match |  | Whether that record is this resource (list below). |
| `reviewedBy` | Reviewed by |  | Initials of the curator who confirmed the row (criteria, section 7). A relation has its own. |
| `note` | Note |  | Free text for the next curator. |
| `qualifiedRelation` | Relations tab | `dcat:qualifiedRelation` | Relations to other resources (below). |
| `fipDeclaration` | grey rows on the Relations tab | `schema:hasPart` | On a FIP row: its declarations, read from its nanopublications at build time (below). Never stored. |
| `declared-by` |  | `fip:declared-by` | On a FIP row: the FAIR Implementation Community that declares it, added at build time (below). Never stored. |
| `fsrNanopublication` |  | `schema:mainEntityOfPage` | On a declared resource: the nanopublication that declares it as a FAIR Supporting Resource, added at build time (below). Never stored. |
| `fairsharing` |  |  | FAIRsharing record data, added at build time (below). Never stored. |

## Lanes

The dashboard lane is derived and not stored; the criteria (section 6) say which lane a resource takes.

| Lane (by phase) | Meaning |
|---|---|
| Generic infrastructure | Resources not specific to a research domain. |
| Life sciences infrastructure | Life-science resources, not specific to toxicology, that toxicology uses. |
| Data generation | Toxicology resources whose earliest phase is data generation; it supports the planning of individual toxicology studies, the recording of their results and study context (metadata, protocols, data processing) and the deposition of study-level datasets linked to that context. |
| Data integration | Toxicology resources whose earliest phase is data integration; it supports the linking of existing research output from different studies across test systems, stressors, exposures and endpoints, with mechanistic knowledge and models; includes the derivative objects this produces. |
| Regulatory assessment | Toxicology resources whose earliest phase is regulatory assessment; it supports the reporting of studies for regulatory submission and the identification and evaluation of toxicology research outputs for a specified regulatory question. |

| Lane (by creator) | Meaning |
|---|---|
| Made by wet-lab research | Toxicology resources made by wet-lab research only. |
| Made by in silico research | Toxicology resources made by in silico research only. |
| Made by regulators | Toxicology resources made by regulators only. |
| Made jointly | Toxicology resources made by two or more creator types together. |

## Controlled lists

### Decision (`decision`)

| Value | Meaning |
|---|---|
| include | Meets all inclusion criteria (I1-I5 in docs/inclusion-criteria.md). |
| exclude | Fails a criterion; the exclusion reason says which. |
| undecided | Not yet screened, or left for the co-authors to decide. |

### Exclusion reason (`exclusionReason`)

The codes E1-E8 and their meanings are the exclusion reasons of the criteria (section 4).

### FAIRsharing type (`fairsharingType`)

| Value | FAIRsharing registry | Record type (id) | Meaning |
|---|---|---|---|
| Standard: model/format | Standard | model_and_format (4) | Data or metadata model, schema, exchange format. |
| Standard: terminology artefact | Standard | terminology_artefact (6) | Ontology, controlled vocabulary, thesaurus or glossary. |
| Standard: reporting guideline | Standard | reporting_guideline (7) | Minimum information checklist or reporting template. |
| Standard: identifier schema | Standard | identifier_schema (8) | Identifier scheme or resolver. |
| Standard: principle | Standard | principle (17) | Published set of principles with a reusable artefact. |
| Database: repository | Database | repository (1) | Archive that accepts data deposits. |
| Database: knowledgebase | Database | knowledgebase (2) | Curated knowledge resource or data portal. |
| Database: knowledgebase and repository | Database | knowledgebase_and_repository (3) | Both a curated knowledge resource and an archive. |
| Policy: journal | Policy | journal (9) | Data policy of a journal. |
| Policy: journal publisher | Policy | journal_publisher (10) | Data policy of a publisher. |
| Policy: society | Policy | society (11) | Policy or guidance of a learned society. |
| Policy: funder | Policy | funder (12) | Data policy of a funder. |
| Policy: project | Policy | project (13) | Policy or guidance issued by a project. |
| Policy: institution | Policy | institution (14) | Policy or guidance issued by an institution or agency, such as OECD guidance. |
| Collection | Collection | collection (15) | Curated collection of standards, databases and policies. |
| Tool | (not registered) | - | Software or service; FAIRsharing does not register these. |

### FSR type (`fsrType`)

The types are stored as IRIs, such as `https://w3id.org/fair/fip/terms/Registry`, in IRI order: types of the FSR typology of the FIP ontology (`https://w3id.org/fair/fip/terms/FIP-Ontology`, version 20260227: `https://w3id.org/fair/fip/terms/FIP-Ontology_20260227`), or FAIR Implementation Community. The typology is read from `https://w3id.org/fair/fip/terms/` when the dashboard and the curation sheet are built, as the ontology draws it: the classes under FAIR Data Policy, FAIR specification and FAIR Supporting Technology, and one level below, that are not deprecated. A type marked FER is a subclass of `fip:FAIR-Enabling-Resource` (gray in the typology). A type's label is its sentence-case label in the ontology, the one with the fewest capitals. The curation sheet's FSR type column takes several types; its Lists tab gives each type with its direct FSR subclass and category; on 18 Oct 2026 they were:

| Direct FSR subclass | Types offered |
|---|---|
| FAIR Data Policy | Data usage license (FER); FAIR practice; Metadata preservation policy (FER); Persistency Policy (FER) |
| FAIR Implementation Community | FAIR Implementation Community |
| FAIR specification | Communication protocol (FER); Crosswalk; FAIR Assessment Specification; FAIR Implementation Profile (FER); Knowledge representation language (FER); Metadata schema (FER); Metadata-data linking schema (FER); Open Digital Rights Language Specification; Provenance model (FER); Reference FAIR Implementation Profile (FER); Semantic model (FER); Structured vocabulary (FER) |
| FAIR Supporting Technology | Authentication and authorization service (FER); Domain-specific registry (FER); Editor; FAIR Analysis Service; FAIR Enrichment Service; FAIR Publishing Service; FAIR Representation Service; FAIR Visualization Service; FAIRification Workflow; Generalist registry (FER); Identifier service (FER); Integration Service; Provenance tracking service; Registry (FER); Validation service |

### Origin (`origin`)

The IRIs are FAIRsharing's subject terms. Until 5 Nov 2026 the field was called `scope`.

| Value | Meaning | IRI |
|---|---|---|
| Generic | Infrastructure not specific to a research domain, including FAIR resources such as the FIP. | [SRAO_0000401](http://www.fairsharing.org/ontology/subject/SRAO_0000401) Subject Agnostic |
| Life Sciences | Life-science infrastructure, not specific to toxicology, that toxicology uses. | [AGROVOC c_4318](http://aims.fao.org/aos/agrovoc/c_4318) Life Science |
| Toxicology | Made for toxicology, including toxicology instances of generic resources. | [NCIT_C17206](http://purl.obolibrary.org/obo/NCIT_C17206) Toxicology |

### Phase (`phase`)

| Value | Meaning | IRI |
|---|---|---|
| Data generation | Supports the planning of individual toxicology studies, the recording of their results and study context (metadata, protocols, data processing) and the deposition of study-level datasets linked to that context. | `terms:phase-data-generation` |
| Data integration | Supports the linking of existing research output from different studies across test systems, stressors, exposures and endpoints, with mechanistic knowledge and models; includes the derivative objects this produces. | `terms:phase-data-integration` |
| Regulatory assessment | Supports the reporting of studies for regulatory submission and the identification and evaluation of toxicology research outputs for a specified regulatory question. | `terms:phase-regulatory-assessment` |

### Creator types (`creatorType`)

In the graph each creator type is the role (`dcat:hadRole`) of a qualified attribution (`prov:qualifiedAttribution` to a `prov:Attribution`), the DCAT pattern for the role an agent has in a resource: the concepts are kinds of creator, not creators.

| Value | Meaning | IRI |
|---|---|---|
| Wet-lab research | Made by experimental (wet-lab) researchers, mostly academic. | [EFO_0009741](http://www.ebi.ac.uk/efo/EFO_0009741) experimental scientist |
| In silico research | Made by computational researchers: modellers, AOP, PBK, QSAR, informatics and data stewards. | [EFO_0009742](http://www.ebi.ac.uk/efo/EFO_0009742) computational scientist |
| Regulator | Made by a regulatory agency or intergovernmental body, such as OECD, EFSA, ECHA or US EPA. | [SIO_000619](http://semanticscience.org/resource/SIO_000619) regulatory authority, `skos:closeMatch` OBI regulatory agency |

### Sub-domains (`subdomains`)

The group is the part of the toxicology life cycle under which the figure lists the sub-domain. Two sub-domains are entries of the IUPAC Gold Book, which holds the IUPAC glossary of terms used in toxicology. Conventional toxicology, for which no concept exists, is a term of the dataset: `skos:broadMatch` NCIT and IUPAC Toxicology and `skos:narrowMatch` Wikidata In vitro toxicology.

| Value | Group | IRI |
|---|---|---|
| conventional toxicology | Data generation (definition below). | `terms:subdomains-conventional-toxicology`, `skos:narrowMatch` [Wikidata Q6013136](http://www.wikidata.org/entity/Q6013136) In vitro toxicology |
| nanotoxicology | Data generation. | [IUPAC 10.1351/goldbook.15908](https://doi.org/10.1351/goldbook.15908) nanotoxicology |
| exposome | Data generation. | [MeSH D000081413](http://id.nlm.nih.gov/mesh/D000081413) Exposome |
| eco-toxicology | Data generation. | [MeSH D054750](http://id.nlm.nih.gov/mesh/D054750) Ecotoxicology, `skos:exactMatch` IUPAC ecotoxicology |
| toxicogenomics | Integration and tools. | [NCIT_C20179](http://purl.obolibrary.org/obo/NCIT_C20179) Toxicogenomics, FAIRsharing's subject term, `skos:exactMatch` IUPAC toxicogenomics |
| AOP-based mechanistic knowledge | Integration and tools. | [MeSH D000073931](http://id.nlm.nih.gov/mesh/D000073931) Adverse Outcome Pathways |
| computational and predictive toxicology | Integration and tools. | [IUPAC 10.1351/goldbook.15583](https://doi.org/10.1351/goldbook.15583) computational toxicology |

| Sub-domain | Definition |
|---|---|
| conventional toxicology | Toxicology studied in vivo, in living organisms, or in vitro, in the laboratory, usually with isolated organ, tissue, cell or biochemical systems (after IUPAC, 1993, doi:10.1351/pac199365092003). |

The definition combines the entries toxicology, in vivo and in vitro of Duffus's IUPAC glossary (1993).

### Date basis (`dateBasis`)

The basis decides the field, and so the term, that holds the date, following DataCite's date types and their crosswalks to schema.org and DCTERMS. Publication and release are both DataCite's Issued; the dataset keeps them apart with schema.org's date of first publication and DCAT's release date. The sheet shows the date as First published with its Date basis.

| Value | Meaning | Field | Term (DataCite date type) |
|---|---|---|---|
| publication | Online publication of the paper that first describes the resource. | `datePublished` | `schema:datePublished` (Issued) |
| release | First public release or launch. | `dateReleased` | `dct:issued`, DCAT's release date (Issued) |
| adoption | Official adoption or publication of guidance or policy. | `dateAdopted` | `dct:dateAccepted` (Accepted) |
| FAIRsharing year | FAIRsharing's year of creation, used only when nothing better was found. | `dateCreated` | `schema:dateCreated` (Created) |
| (none) | No basis recorded. | `date` | `dct:date` (Other) |

### Maintained (`maintained`)

| Value | Meaning | IRI |
|---|---|---|
| active | Maintained and available. | `terms:maintained-active`, `skos:closeMatch` EU distribution status Ongoing |
| discontinued | No longer maintained or available (shown with a dagger). | [EU dataset status DISCONT](http://publications.europa.eu/resource/authority/dataset-status/DISCONT) |
| in development | Not yet released in a stable form. | [ADMS UnderDevelopment](http://purl.org/adms/status/UnderDevelopment) |
| unknown | Status could not be established. | Not published; [NCIT_C17998](http://purl.obolibrary.org/obo/NCIT_C17998) Unknown in the stored file. |

### In manuscript (`manuscript`)

| Value | Meaning |
|---|---|
| cited | Named in the manuscript text with a reference. |
| named | Named in the manuscript text without a reference. |
| comment only | Named only in a comment or to-do note of the manuscript. |
| absent | Not in the manuscript. |

### Community documents (`mentionedIn`)

| Value | Document |
|---|---|
| Whitepaper | Martens et al. 2023, "ELIXIR and Toxicology: a community in development", F1000Research, doi 10.12688/f1000research.74502.2. |
| FAIRSharing | FAIRsharing's report on the ELIXIR Toxicology Community collection, 3 Jul 2025, doi 10.5281/zenodo.15799783. |
| INTOXICOM 1 | Report of INTOXICOM workshop 1: Martens et al. 2024, BioHackrXiv, doi 10.37044/osf.io/un2rw. |
| INTOXICOM 2 | Report of INTOXICOM workshop 2: Bonatto Minella et al. 2026, BioHackrXiv, doi 10.37044/osf.io/64dfv_v1. |
| INTOXICOM 3 | Report of INTOXICOM workshop 3: Bünger et al. 2026, BioHackrXiv, doi 10.37044/osf.io/u3fnh_v1. |
| INTOXICOM 4 | Report of INTOXICOM workshop 4: Martens et al., draft, github.com/TGX-UM/INTOXICOM_Workshop_4. |
| INTOXICOM 5 | Report of INTOXICOM workshop 5: Evelo et al. 2026, BioHackrXiv, doi 10.37044/osf.io/zf2qj_v1. |

### FAIRsharing match (`fairsharingMatch`)

| Value | Meaning |
|---|---|
| confirmed | The FAIRsharing record is this resource. |
| to check | A FAIRsharing record was proposed and needs a curator. |
| no record | FAIRsharing has no record for this resource. |

### Relation evidence (`evidence`)

| Value | Meaning |
|---|---|
| manuscript | Stated in the manuscript. |
| FAIRsharing | Asserted by FAIRsharing. |
| literature | Stated in the literature or on the resource website. |
| curator | Added by a curator. |
| FIP | Declared in a FAIR Implementation Profile. |

## Relations

A relation sits on its subject as a DCAT qualified relation and reads the FAIRsharing way, subject first: "CTD implements ExO". Fields: `relation` (the target's `@id`, `dct:relation`), `hadRole` (the label, `dcat:hadRole`), and the curation fields `evidence`, `source`, `reviewedBy` and `note`, which stay out of the graph. Each label is a term of the dataset named after it (`terms:implements`). Six of FAIRsharing's fourteen labels are used, with one label of the dataset's own, uses. Their ids and parents come from FAIRsharing's label list (`GET https://api.fairsharing.org/record_association_labels`) and their pairs from its allowed list (`GET https://api.fairsharing.org/record_associations/allowed`), both read on 18 Oct 2026; their meanings come from FAIRsharing's pages on relations from [database](https://fairsharing.gitbook.io/fairsharing/associated-records/from-database-records), [standard](https://fairsharing.gitbook.io/fairsharing/associated-records/from-standards-records), [data policy](https://fairsharing.gitbook.io/fairsharing/associated-records/from-data-policy-records), [collection](https://fairsharing.gitbook.io/fairsharing/associated-records/from-collections) and [FAIRassist](https://fairsharing.gitbook.io/fairsharing/associated-records/from-fairassist-records) records, read on 4 Nov 2026. Lineage labels are drawn as arrows from the earlier resource to the one building on it; recommends and related_to have no arrowhead.

The criteria (section 6) say which relations are possible and what happens to one that is not; the table's last column gives the registry pairs FAIRsharing allows for each label.

| Label (`hadRole`) | FAIRsharing id | Lineage | Meaning | Allowed in FAIRsharing between |
|---|---|---|---|---|
| implements | 1 | yes | The subject implements the standard or FAIR specification. | Database to Standard |
| extends | 8 | yes | The subject extends or builds upon the target. | Database to Database, Policy to Policy, Standard to Standard |
| profiles | 7 | yes | The standard is a profile of the target standard. | Standard to Standard |
| recommends | 11 | no | The data policy recommends the target. | Policy to Collection, Policy to Database, Policy to Standard |
| deprecates | 9 | yes | The target has been retired and is no longer actively maintained. | Collection to Collection, Database to Database, Policy to Policy, Standard to Standard |
| related_to | 4 | no | The resources are related; no more precise label applies. | Database to Database, Database to Standard, Policy to Policy, Standard to Database, Standard to Standard |
| uses | none: the dataset's own | yes | The subject uses the target. | not a FAIRsharing label |

FAIRsharing's other eight labels are not used; FAIRsharing publishes no IRIs for any of its labels.

| FAIRsharing label | Here |
|---|---|
| accepts, outputs | Not used: children of implements in FAIRsharing's label list (`parent_id`). |
| shares_code_with, shares_data_with | Not used: children of related_to in FAIRsharing's label list. |
| collects | Collection membership: read from FAIRsharing when the dashboard is built and published on the collection (`dcat:resource`), not stored. |
| part_of, measures_principle, has_associated_metric | Only between principles, metrics and benchmarks, which no included resource is. |

The label uses is the dataset's own: FAIRsharing has no label for a resource that uses another, so a uses relation cannot be entered in FAIRsharing (criteria, section 6 and decision record).

A FIP row's declarations (`fipDeclaration`) and `declared-by` use FIP ontology properties (`fip:` IRIs), read "FIP property target". They are read at build time (below), are not lineage and cannot be entered in FAIRsharing; the curation sheet shows the declarations as grey rows with evidence FIP.

| Property | Meaning |
|---|---|
| declares-current-use-of | The FIP declares that its community uses the target. |
| declares-planned-use-of | The FIP declares that its community plans to use the target. |
| declares-planned-development-of | The FIP declares that its community plans to develop the target. |
| declares-planned-replacement-of | The FIP declares that its community plans to replace the target. |
| declared-by | The FIP is declared by the target, a FAIR Implementation Community. |

## Fields added at build time

These fields are added to a copy of the dataset when the dashboard (with its published dataset and CSV files) or the curation sheet is built, and the `fairsharing` block also for the FAIRsharing export. They are published with their retrieval date and never stored in `data/`; with `--offline` they are read from the local caches in `build/fairsharing` and `build/fip`.

### The `fairsharing` block

Read from the FAIRsharing API and added to each resource with a confirmed FAIRsharing record: `id`, `doi`, `name`, `abbreviation`, `registry`, `recordType`, `status`, `yearCreation`, `homepage`, `inCollection` (member of the Toxicology collection, record 3496), `associations` (FAIRsharing's own relations of this record: label and record id) and `retrieved` (the retrieval date). `sources.fairsharing` gives the retrieval date and the number of collection members. FAIRsharing contact details are left out.

### FIP declarations

Read through each FIP's declaration index from the nanopublications of the two toxicology FIPs (CC0, or as stated in each); invalidated declarations are skipped. A declaration is kept only when its target has a row, found through the row's `@id`, `fsr` or FAIRsharing record; the public dataset keeps only declarations to included resources.

| Field | Content |
|---|---|
| `fipDeclaration` | On a FIP row, one entry per declaration: `@id` (the declaration in its nanopublication), `@type` (`fip:FIP-Declaration`), one of the `declares-…` properties above with the target's `@id`, `question` (the FIP question, such as `fip:FIP-Question-F1-D`), `principle` (its FAIR principle in the FIP ontology, whose version 20260227 validation checks, such as F1) and `considerations` (the community's remarks, when given). |
| `declared-by` | On a FIP row: the `@id` of the FAIR Implementation Community that declares the FIP, when it has a row. |
| `declaredIn` | On a declared resource: the `@id`s of the FIPs that declare it. |
| `fsrNanopublication` | On a declared resource: the nanopublication that declares it as a FAIR Supporting Resource, the latest valid one for each IRI it is declared under; absent when there is none. Also in resources.csv; the details link it as FSR declaration. |
| `sources.fip` | Per FIP: `label`, `profile`, `nanopub`, `index` (its declaration index), `fic` (its community), `created`, `licence`, `retrieved`, `declarations` (count, without the no-choice ones), `noChoice` (questions declared with no choice), `invalidated` (declarations skipped), `ontology` (FIP ontology version) and `method`. |
| `isBasedOn` | The profile of each FIP is added. |
| `creditText` | Names the nanopublication of each FIP after FAIRsharing (CC0, or as stated in each). |

## Terms

Every field in the RDF graph uses a term of schema.org, written `http://schema.org/` as in schema.org's own JSON-LD context, else of DCAT (with the DCTERMS and SKOS terms DCAT uses), and of the FIP ontology (`https://w3id.org/fair/fip/terms/`) for FSR types and FIP declarations. The dataset defines no properties of its own.

The JSON-LD context (JSON-LD 1.1) maps each field to its term (Resource fields) and, through property-scoped contexts, each controlled value to its IRI, so the stored file and the sheet keep readable values. A value is an outside concept where one exists: FAIRsharing's subject terms for the scopes; MeSH, NCIT and the IUPAC Gold Book for six sub-domains; EFO and SIO for the creator types; the ADMS and EU status lists for in development and discontinued. The other 11 values are the dataset's own terms, under `https://w3id.org/fair-tox/terms#`: the three phases, one sub-domain, one maintenance status and FAIRsharing's six relation labels. The dataset defines no properties.

Each list with terms of the dataset (phase, sub-domains, maintained, relation labels) is a `schema:DefinedTermSet` and a `skos:ConceptScheme` of the CDIF Concept Scheme profile 1.1, such as `terms:phase-values`, with a definition and its terms as top concepts. Each term is a `schema:DefinedTerm` and `skos:Concept` in its set, named by the stored value and defined by its definition above; a relation label names its term (`terms:implements`), any other value's term is `<list>-<value>` (`terms:phase-data-generation`). Each term links to the closest outside concepts:

| Term | Links |
|---|---|
| Data generation | `skos:closeMatch` Terms4FAIRskills data production, EDAM Data acquisition |
| Data integration | `skos:closeMatch` Terms4FAIRskills data integration, EDAM Data integration and warehousing |
| Regulatory assessment | `skos:relatedMatch` MeSH Risk Assessment, EDAM Regulatory affairs, Terms4FAIRskills data quality, IUPAC weight-of-evidence for toxicity, VHP4Safety glossary Safety Assessment, IATA and Risk Assessment |
| conventional toxicology | `skos:broadMatch` NCIT and IUPAC Toxicology; `skos:narrowMatch` Wikidata In vitro toxicology; `dct:source` IUPAC (1993) |
| active | `skos:closeMatch` EU distribution status Ongoing |
| implements | `skos:closeMatch` `fip:implements`, SIO is implementation of, `dct:conformsTo` |
| profiles | `skos:exactMatch` W3C PROF `prof:isProfileOf`; `skos:broadMatch` `dct:conformsTo` |
| extends | `skos:closeMatch` CiTO extends; `skos:broadMatch` `schema:isBasedOn` |
| deprecates | `skos:closeMatch` `dct:replaces` |
| related_to | `skos:exactMatch` `dct:relation` |
| recommends | `skos:broadMatch` `dct:relation` |
| uses | `skos:broadMatch` `dct:relation` |

The FAIRsharing type stays text (`schema:additionalType`), as FAIRsharing publishes no IRIs for its registries and record types.

`fairtox site <outdir>` writes the terms as `terms.ttl` and `terms.jsonld`, and the context as `context.jsonld`, next to the dashboard's `index.html`; CI publishes them with the dashboard. In the dashboard's data dictionary each field shows its term and has an anchor, its name; each term of the dataset has an anchor, its name, where its IRI lands (`#phase-data-generation`, `#implements`); and a resource's `#key` opens that resource (`#ctd`).

## Change log

`data/changes.csv` has one row per changed field: `date`, `round` (the curation round, import or process), `key`, `field`, `old`, `new`, `by` (the Reviewed by initials from the sheet, or the command or process that made the change) and `source` (workbook file name, FAIRsharing Toxicology collection, FIP nanopublications, or the basis of the change). A change read back from the sheet is logged under the Reviewed by of its row or, for a relation, of the relation itself; `by` is empty when the curator gave no initials. Changes by research, verification, classification, relation check, phase proposal, screening, review, fairtox fip and fairtox fairsharing are proposals; JH marks a decision of a corresponding author; migration, rename, cleanup and labels only rename or move values, and model change also re-derived phases and creator types on 5 Oct 2026, as proposals. The log starts with the first version of the dataset, whose values have no line; a row or relation added later is one line (`(row)` or `relation`), and older lines may use field names renamed since (`type`, `stakeholder`, `stakeholders`). A change of `reviewedBy` to initials is a confirmation, and so is a row added in the sheet with initials (its `(row)` line). FIP identifiers (`fsr`) are replaced on each FIP import and not logged. The log is published with the code; it cites the manuscript drafts by section and line.
