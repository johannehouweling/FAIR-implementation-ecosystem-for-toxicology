# Data dictionary

The dataset is one JSON-LD file, `data/fair-tox-ecosystem.jsonld`, licensed CC BY-SA 4.0. It is a schema.org `Dataset` whose `hasPart` lists the resources. Each resource has its curated fields and its relations to other resources. The file stores only what is curated: FAIRsharing record data are added when the dashboard, the curation sheet or the FAIRsharing export is built, and the declarations of the toxicology FAIR Implementation Profiles (FIPs) when the dashboard or the sheet is built (see Fields added at build time). The file is written only by the `fairtox` commands, which validate every change and log curated changes in `data/changes.csv`.

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
| `creator` | The ELIXIR Toxicology Community, an organisation within ELIXIR (ROR `https://ror.org/044rwnt51`). |
| `creditText` | Attribution to FAIRsharing; the published dataset adds the nanopublications of the two FIPs. |
| `isBasedOn` | The FAIRsharing Toxicology collection; the published dataset adds the profiles of the two FIPs. |
| `sources` | What each source contributed, with versions and checksums. The published dataset adds `fairsharing` and `fip`, each with its retrieval date (see Fields added at build time). |
| `vocabularies` | Every controlled list with its definitions, so the file can be read on its own. |
| `hasPart` | The resources. |

The published dataset also has the fields that CODATA's CDIF Discovery profile 1.1 asks of a dataset; CI checks every build with CODATA's SHACL rules for the profile.

| Field | Meaning |
|---|---|
| `identifier` | Persistent identifier, as a `schema:PropertyValue`: the Zenodo DOI once deposited, until then `https://w3id.org/fair-tox/dataset`. |
| `url` | The dashboard. |
| `datePublished` | Release date (`date-released` in CITATION.cff). |
| `temporalCoverage` | Years in which the resources were first published, such as `1965/2026`. |
| `wasDerivedFrom` | The sources in `isBasedOn` (`prov:wasDerivedFrom`). |
| `variableMeasured` | Each resource field with its term and definition. |
| `distribution` | The JSON-LD file, the two CSV files and `terms.ttl`, each with its media type, the standard it follows and, except the dataset file itself, a SHA-256 checksum. |
| `subjectOf` | The catalog record (`dcat:CatalogRecord`), which names its maintainer, the ELIXIR Toxicology Community, and declares conformance to CDIF Core 1.1 and CDIF Discovery 1.1. |

## Resource fields

Curated fields are edited in the curation sheet; the column is given. `@id`, `identifier`, `schemaType`, `buildsOnFair` and `fsrCategory` are derived on every save; `declaredIn`, `principles`, `fipDeclaration`, `declared-by` and `fairsharing` are added at build time and never stored. The term is the one the JSON-LD context maps the field to. A field without a term stays out of the RDF graph, as the context has no `@vocab`: the derived fields are there for people and the dashboard, the curation fields for the curators.

| Field | Sheet column | Term | Content |
|---|---|---|---|
| `@id` |  |  | FIC nanopublication of a FAIR Implementation Community, else the FAIRsharing DOI when the match is confirmed, else `https://w3id.org/fair-tox/dataset#key`. |
| `identifier` | Identifier | `schema:identifier` | Derived: the `@id` as an absolute IRI, the resource's persistent identifier. |
| `schemaType` |  | `rdf:type` | Derived: `schema:SoftwareApplication` for a tool, else `schema:CreativeWork`, next to the FSR type. |
| `key` | Key | `dct:identifier` | Stable short identifier: lowercase letters, digits, `_` or `-`. Never changes. |
| `name` | Name | `schema:name` | Full name. |
| `alternateName` | Aliases | `schema:alternateName` | Abbreviations and other names; the first short one is shown in the figure. |
| `decision` | Decision |  | Screening decision (list below). |
| `exclusionReason` | Exclusion reason |  | Code E1-E8, required when the decision is exclude. |
| `coveredBy` | Covered by |  | Key of the row that covers this one (exclusion reason E6). |
| `fairsharingType` | FAIRsharing type | `schema:additionalType` | FAIRsharing registry and record type, or Tool (list below), as text. |
| `fsrType` | FSR type | `rdf:type` | FAIR Supporting Resource (FSR) type: one type of the FSR typology of the FIP ontology (list below). FAIR Implementation Community only on a row whose `@id` is a valid FIC nanopublication. |
| `scope` | Scope | `schema:about` | What the resource was made for (list below). |
| `phase` | the earliest phase chosen in Phase |  | For toxicology resources: the phase it acts on; when it acts on several, the earliest at which it must be applied (list below). Required for included and undecided toxicology resources. Not in the graph: it is the earliest phase of `span`. |
| `span` | Phase (multi-select) | `dcat:theme` | For toxicology resources: every phase it acts on, in phase order, starting with `phase`. |
| `creatorType` | one "Made by" column per creator type | via `qualifiedAttribution` | For toxicology resources: the kind of creator; several may apply (list below). Required for included and undecided toxicology resources. |
| `qualifiedAttribution` |  | `prov:qualifiedAttribution` | Derived from `creatorType`: one `prov:Attribution` per creator type, whose `dcat:hadRole` is its concept. |
| `buildsOnFair` | Builds on FAIR |  | Derived: true for a toxicology resource first published in 2016 or later that implements, extends, profiles or recommends a generic resource. |
| `fsrCategory` | Class |  | Derived from `fsrType`: FAIR-Enabling Resource when the type is one, else FAIR Supporting Resource. |
| `declaredIn`, `principles` | Declared in, Principles |  | Added at build time from the FIP declarations: the FIPs that declare the resource and the principles of the questions it is declared for (below). |
| `fsr` | FIP identifiers | `schema:sameAs` | Stored by `fairtox fip --apply`: the IRIs under which the FIPs declare the resource, when they differ from its `@id`. Replaced on each import. |
| `subdomains` | one column per sub-domain | `schema:about` | Sub-domains that apply (list below). |
| `datePublished`, `dateReleased`, `dateAdopted`, `dateCreated`, `date` | First published, Date basis | `schema:datePublished`, `dct:issued`, `dct:dateAccepted`, `schema:dateCreated`, `dct:date` | When the resource first became public: `YYYY`, `YYYY-MM` or `YYYY-MM-DD`, in the one field of what the date refers to, its date basis (list below). |
| `dateSource` | Citation | `schema:citation` | DOI or URL that shows the date. |
| `creator` | Creator | `schema:creator` | Organisation(s) that made the resource, as information. |
| `url` | URL | `schema:url` | Main web address. |
| `description` | Description | `schema:description` | One to three sentences; needed to register the resource in FAIRsharing. |
| `maintained` | Maintained | `schema:creativeWorkStatus` | Maintenance status (list below); not published when unknown. |
| `manuscript` | In manuscript |  | Whether and how the manuscript names it (list below). Not published. |
| `manuscriptEvidence` | Manuscript evidence |  | Section and line numbers in the frozen manuscript draft. Not published. |
| `mentionedIn` | one "ETC" column per document |  | ELIXIR Toxicology Community documents that mention the resource, ticked by curators (list below); a mention documents toxicology use (I4). Not published. |
| `fairsharingRecord` | FAIRsharing record | `schema:sameAs` | FAIRsharing record code (`FAIRsharing.xxxxxx`), or the numeric id of a record without a DOI; in the graph, its record page `https://fairsharing.org/<code>`. For a confirmed record, the page carries FAIRsharing's subjects (subject areas) as `schema:about`, the property of `scope`, and its domains (kinds of data, entities and activities) as `dcat:theme`, the property of `span`: FAIRsharing's statements, read when the dataset is built and not curated. The sheet shows them in the grey columns FAIRsharing subjects, after Scope, and FAIRsharing domains, after Phase. |
| `resource` |  | `dcat:resource` | On the FAIRsharing Toxicology collection only, in the published dataset: the included resources that FAIRsharing lists as its members, read when the dataset is built. |
| `fairsharingMatch` | FAIRsharing match |  | Whether that record is this resource (list below). |
| `reviewedBy` | Reviewed by |  | Initials of the curator who checked the row as it stands, up to Note: they confirm its values, which are proposals until then. A process that changes a confirmed value empties it. A relation has its own. |
| `note` | Note |  | Free text for the next curator. |
| `qualifiedRelation` | Relations tab | `dcat:qualifiedRelation` | Relations to other resources (below). |
| `fipDeclaration` | grey rows on the Relations tab | `schema:hasPart` | On a FIP row: its declarations, read from its nanopublications at build time (below). Never stored. |
| `declared-by` |  | `fip:declared-by` | On a FIP row: the FAIR Implementation Community that declares it, added at build time (below). Never stored. |
| `fairsharing` |  |  | FAIRsharing record data, added at build time (below). Never stored. |

## Lanes

The dashboard lane is derived and not stored. Scope Generic gives Generic infrastructure and scope Life Sciences gives Life sciences infrastructure. A toxicology resource sits in the lane named after its phase; the dashboard can instead arrange the toxicology lanes by creator type, with one lane for resources made jointly. The toxicology lanes together form the toxicology infrastructure. FAIR Implementation Communities are listed but not drawn.

| Lane (by phase) | Meaning |
|---|---|
| Generic infrastructure | Resources not specific to a research domain. |
| Life sciences infrastructure | Life-science resources, not specific to toxicology, that toxicology uses. |
| Data generation | Toxicology resources whose phase, the earliest they act on, is data generation. |
| Data integration | Toxicology resources whose phase, the earliest they act on, is data integration. |
| Regulatory assessment | Toxicology resources whose phase, the earliest they act on, is regulatory assessment. |

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

| Value | Meaning |
|---|---|
| E1 | Organisation, project, initiative, consortium, community or event; its named product is listed instead. |
| E2 | Principle, framework, method or approach, or a publication only, rather than a resource that can be used directly; a standard, database, policy or tool that puts it into practice is listed instead. |
| E3 | Unnamed or not identifiable (no homepage or DOI). |
| E4 | Never publicly available. |
| E5 | No documented toxicology use. |
| E6 | Duplicate, version or component of another row (see Covered by). |
| E7 | Outside chemical toxicology, such as toxinology or clinical adverse-event grading. |
| E8 | Test method or guideline that standardises an experiment rather than data or metadata. |

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

One type per resource, stored as its IRI, such as `https://w3id.org/fair/fip/terms/Registry`: a type of the FSR typology of the FIP ontology (`https://w3id.org/fair/fip/terms/FIP-Ontology`, version 20260227: `https://w3id.org/fair/fip/terms/FIP-Ontology_20260227`), or FAIR Implementation Community for a community. The typology is read from `https://w3id.org/fair/fip/terms/` when the dashboard and the curation sheet are built, as the ontology draws it: the classes under FAIR Data Policy, FAIR specification and FAIR Supporting Technology, and one level below, that are not deprecated. `fsrCategory` is FAIR-Enabling Resource when the type is a subclass of `fip:FAIR-Enabling-Resource` (gray in the typology), else FAIR Supporting Resource. The curation sheet's Lists tab gives each type with its direct FSR subclass and category; on 18 Oct 2026 they were:

| Direct FSR subclass | Types offered |
|---|---|
| FAIR Data Policy | Data usage license (FER); FAIR practice; Metadata preservation policy (FER); Persistency Policy (FER) |
| FAIR Implementation Community | FAIR Implementation Community |
| FAIR specification | Communication protocol (FER); Crosswalk; FAIR Assessment Specification; FAIR Implementation Profile (FER); Knowledge representation language (FER); Metadata schema (FER); Metadata-data linking schema (FER); Open Digital Rights Language Specification; Provenance model (FER); Reference FAIR Implementation Profile (FER); Semantic model (FER); Structured vocabulary (FER) |
| FAIR Supporting Technology | Authentication and authorization service (FER); Domain-specific registry (FER); Editor; FAIR Analysis Service; FAIR Enrichment Service; FAIR Publishing Service; FAIR Representation Service; FAIR Visualization Service; FAIRification Workflow; Generalist registry (FER); Identifier service (FER); Integration Service; Provenance tracking service; Registry (FER); Validation service |

### Scope (`scope`)

The IRIs are FAIRsharing's subject terms.

| Value | Meaning | IRI |
|---|---|---|
| Generic | Infrastructure not specific to a research domain, including FAIR resources such as the FIP. | [SRAO_0000401](http://www.fairsharing.org/ontology/subject/SRAO_0000401) Subject Agnostic |
| Life Sciences | Life-science infrastructure, not specific to toxicology, that toxicology uses. | [AGROVOC c_4318](http://aims.fao.org/aos/agrovoc/c_4318) Life Science |
| Toxicology | Made for toxicology, including toxicology instances of generic resources. | [NCIT_C17206](http://purl.obolibrary.org/obo/NCIT_C17206) Toxicology |

### Phase (`phase`)

| Value | Meaning | IRI |
|---|---|---|
| Data generation | Planning, producing and depositing primary records: datasets, protocols, method descriptions and the publications reporting them. | `terms:phase-data-generation` |
| Data integration | Integrating and synthesising those records into secondary resources and evidence: curated databases, knowledge bases, ontologies, pathway networks and models. | `terms:phase-data-integration` |
| Regulatory assessment | Assessing records and secondary resources for reliability and relevance in a regulatory context and integrating them into weight of evidence and decisions. | `terms:phase-regulatory-assessment` |

### Creator types (`creatorType`)

In the graph each creator type is the role (`dcat:hadRole`) of a qualified attribution (`prov:qualifiedAttribution` to a `prov:Attribution`), the DCAT pattern for the role an agent has in a resource: the concepts are kinds of creator, not creators.

| Value | Meaning | IRI |
|---|---|---|
| Wet-lab research | Made by experimental (wet-lab) researchers, mostly academic. | [EFO_0009741](http://www.ebi.ac.uk/efo/EFO_0009741) experimental scientist |
| In silico research | Made by computational researchers: modellers, AOP, PBK, QSAR, informatics and data stewards. | [EFO_0009742](http://www.ebi.ac.uk/efo/EFO_0009742) computational scientist |
| Regulator | Made by a regulatory agency or intergovernmental body, such as OECD, EFSA, ECHA or US EPA. | [SIO_000619](http://semanticscience.org/resource/SIO_000619) regulatory authority, `skos:closeMatch` OBI regulatory agency |

### Sub-domains (`subdomains`)

The group is the part of the toxicology life cycle under which the figure lists the sub-domain. Two sub-domains are entries of the IUPAC Gold Book, which holds the IUPAC glossary of terms used in toxicology. Regulatory toxicology, for which no concept exists, is a term of the dataset; it and in vitro toxicology are `skos:broadMatch` NCIT and IUPAC Toxicology.

| Value | Group | IRI |
|---|---|---|
| in vitro toxicology | Data generation (definition below). | [Wikidata Q6013136](http://www.wikidata.org/entity/Q6013136) In vitro toxicology |
| nanotoxicology | Data generation. | [IUPAC 10.1351/goldbook.15908](https://doi.org/10.1351/goldbook.15908) nanotoxicology |
| exposome | Data generation. | [MeSH D000081413](http://id.nlm.nih.gov/mesh/D000081413) Exposome |
| eco-toxicology | Data generation. | [MeSH D054750](http://id.nlm.nih.gov/mesh/D054750) Ecotoxicology, `skos:exactMatch` IUPAC ecotoxicology |
| toxicogenomics | Integration and tools. | [NCIT_C20179](http://purl.obolibrary.org/obo/NCIT_C20179) Toxicogenomics, FAIRsharing's subject term, `skos:exactMatch` IUPAC toxicogenomics |
| AOP-based mechanistic knowledge | Integration and tools. | [MeSH D000073931](http://id.nlm.nih.gov/mesh/D000073931) Adverse Outcome Pathways |
| computational and predictive toxicology | Integration and tools. | [IUPAC 10.1351/goldbook.15583](https://doi.org/10.1351/goldbook.15583) computational toxicology |
| regulatory toxicology | Application (definition below). | `terms:subdomains-regulatory-toxicology`, `skos:relatedMatch` Wikidata regulatory science |

In vitro toxicology is toxicology studied in vitro: in the laboratory, usually with isolated organ, tissue, cell or biochemical systems, after the IUPAC definitions of toxicology and in vitro (Duffus, 1993, [doi:10.1351/pac199365092003](https://doi.org/10.1351/pac199365092003)). Regulatory toxicology collects, processes and evaluates experimental and epidemiological data as the basis for decisions that protect health from the harmful effects of chemical substances, and develops standard protocols and new test methods for them, after the working group on regulatory toxicology of the German Society for Experimental and Clinical Pharmacology and Toxicology (Schwenk et al., 2002, [doi:10.1016/S0378-4274(01)00457-X](https://doi.org/10.1016/S0378-4274(01)00457-X)).

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
| INTOXICOM 1 | Report of INTOXICOM workshop 1. |
| INTOXICOM 2 | Report of INTOXICOM workshop 2. |
| INTOXICOM 3 | Report of INTOXICOM workshop 3. |
| INTOXICOM 4 | Report of INTOXICOM workshop 4. |
| INTOXICOM 5 | Report of INTOXICOM workshop 5. |

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

A relation sits on its subject as a DCAT qualified relation and reads the FAIRsharing way, subject first: "CTD implements ExO". Fields: `relation` (the target's `@id`, `dct:relation`), `hadRole` (the label, `dcat:hadRole`), and the curation fields `evidence`, `source`, `reviewedBy` and `note`, which stay out of the graph. Each label is a term of the dataset named after it (`terms:implements`). Six of FAIRsharing's fourteen labels are used. Lineage labels are drawn as arrows from the earlier resource to the one building on it; related_to has no arrowhead. A lineage relation normally points to an earlier resource; it may point to a later one only when FAIRsharing asserts it.

| Label (`hadRole`) | FAIRsharing id | Lineage | Meaning | Allowed in FAIRsharing between |
|---|---|---|---|---|
| implements | 1 | yes | The database implements the standard. | Database to Standard |
| extends | 8 | yes | The subject builds on and extends the target. | Database to Database, Policy to Policy, Standard to Standard |
| profiles | 7 | yes | The standard is a profile of the target standard. | Standard to Standard |
| recommends | 11 | yes | The policy recommends the target. | Policy to Collection, Policy to Database, Policy to Standard |
| deprecates | 9 | yes | The subject replaces the target. | Collection to Collection, Database to Database, Policy to Policy, Standard to Standard |
| related_to | 4 | no | The resources are related without one building on the other. | Database to Database, Database to Standard, Policy to Policy, Standard to Database, Standard to Standard |

Relations FAIRsharing does not allow between the two types are kept and flagged as not enterable in FAIRsharing.

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

Read from the FAIRsharing API and added to each resource with a confirmed FAIRsharing record: `id`, `doi`, `name`, `abbreviation`, `registry`, `recordType`, `status`, `yearCreation`, `homepage`, `inCollection` (member of the Toxicology collection, record 3496), `associations` (FAIRsharing's own relations of this record: label and record id) and `retrieved` (the retrieval date). `sources.fairsharing` gives the retrieval date and the number of collection members. `fairtox fairsharing --apply` adds each new collection member as an undecided row, its curated fields filled from its record and logged in `data/changes.csv`. FAIRsharing contact details are left out.

### FIP declarations

Read through each FIP's declaration index from the nanopublications of the two toxicology FIPs (CC0, or as stated in each); invalidated declarations are skipped. A declaration is kept only when its target has a row, found through the row's `@id`, `fsr` or FAIRsharing record; the public dataset keeps only declarations to included resources.

| Field | Content |
|---|---|
| `fipDeclaration` | On a FIP row, one entry per declaration: `@id` (the declaration in its nanopublication), `@type` (`fip:FIP-Declaration`), one of the `declares-…` properties above with the target's `@id`, `question` (the FIP question, such as `fip:FIP-Question-F1-D`), `principle` (its FAIR principle in the FIP ontology, whose version 20260227 validation checks, such as F1) and `considerations` (the community's remarks, when given). |
| `declared-by` | On a FIP row: the `@id` of the FAIR Implementation Community that declares the FIP, when it has a row. |
| `declaredIn` | On a declared resource: the `@id`s of the FIPs that declare it. |
| `principles` | On a declared resource: the principles of the questions it is declared for; absent when no FIP declares it. |
| `sources.fip` | Per FIP: `label`, `profile`, `nanopub`, `index` (its declaration index), `fic` (its community), `created`, `licence`, `retrieved`, `declarations` (count, without the no-choice ones), `noChoice` (questions declared with no choice), `invalidated` (declarations skipped), `ontology` (FIP ontology version) and `method`. |
| `isBasedOn` | The profile of each FIP is added. |
| `creditText` | Names the nanopublication of each FIP after FAIRsharing (CC0, or as stated in each). |

## Terms

Every field in the RDF graph uses a term of schema.org, written `http://schema.org/` as in schema.org's own JSON-LD context, else of DCAT (with the DCTERMS and SKOS terms DCAT uses), and of the FIP ontology (`https://w3id.org/fair/fip/terms/`) for FSR types and FIP declarations. The dataset defines no properties of its own.

The JSON-LD context (JSON-LD 1.1) maps each field to its term (Resource fields) and, through property-scoped contexts, each controlled value to its IRI, so the stored file and the sheet keep readable values. A value is an outside concept where one exists: FAIRsharing's subject terms for the scopes; MeSH, NCIT, the IUPAC Gold Book and Wikidata for seven sub-domains; EFO and SIO for the creator types; the ADMS and EU status lists for in development and discontinued. The other 11 values are the dataset's own terms, under `https://w3id.org/fair-tox/terms#`: the three phases, one sub-domain, one maintenance status and FAIRsharing's six relation labels. The dataset defines no properties.

Each list with terms of the dataset (phase, sub-domains, maintained, relation labels) is a `schema:DefinedTermSet` and a `skos:ConceptScheme` of the CDIF Concept Scheme profile 1.1, such as `terms:phase-values`, with a definition and its terms as top concepts. Each term is a `schema:DefinedTerm` and `skos:Concept` in its set, named by the stored value and defined by its definition above; a relation label names its term (`terms:implements`), any other value's term is `<list>-<value>` (`terms:phase-data-generation`). Each term links to the closest outside concepts:

| Term | Links |
|---|---|
| Data generation | `skos:closeMatch` Terms4FAIRskills data production, EDAM Data acquisition |
| Data integration | `skos:closeMatch` Terms4FAIRskills data integration, EDAM Data integration and warehousing |
| Regulatory assessment | `skos:relatedMatch` MeSH Risk Assessment, EDAM Regulatory affairs, Terms4FAIRskills data quality, IUPAC weight-of-evidence for toxicity, VHP4Safety glossary Safety Assessment, IATA and Risk Assessment |
| regulatory toxicology | `skos:broadMatch` NCIT and IUPAC Toxicology; `skos:relatedMatch` Wikidata regulatory science; `dct:source` Schwenk et al. (2002) |
| active | `skos:closeMatch` EU distribution status Ongoing |
| implements | `skos:closeMatch` `fip:implements`, SIO is implementation of, `dct:conformsTo` |
| profiles | `skos:exactMatch` W3C PROF `prof:isProfileOf`; `skos:broadMatch` `dct:conformsTo` |
| extends | `skos:closeMatch` CiTO extends; `skos:broadMatch` `schema:isBasedOn` |
| deprecates, related_to | `skos:exactMatch` `dct:replaces`, `dct:relation` |
| recommends | `skos:broadMatch` `dct:relation` |

The FAIRsharing type stays text (`schema:additionalType`), as FAIRsharing publishes no IRIs for its registries and record types.

`fairtox site <outdir>` writes the terms as `terms.ttl` and `terms.jsonld`, and the context as `context.jsonld`, next to the dashboard's `index.html`; CI publishes them with the dashboard. In the dashboard's data dictionary each field shows its term and has an anchor, its name; each term of the dataset has an anchor, its name, where its IRI lands (`#phase-data-generation`, `#implements`); and a resource's `#key` opens that resource (`#ctd`).

## Change log

`data/changes.csv` has one row per changed field: `date`, `round` (the curation round, import or process), `key`, `field`, `old`, `new`, `by` (the Reviewed by initials from the sheet, or the command or process that made the change) and `source` (workbook file name, FAIRsharing Toxicology collection, FIP nanopublications, or the basis of the change). A change read back from the sheet is logged under the Reviewed by of its row or, for a relation, of the relation itself; `by` is empty when the curator gave no initials. Changes by research, verification, classification, relation check, phase proposal, screening, review, fairtox fip and fairtox fairsharing are proposals; JH marks a decision of a corresponding author; migration, rename, cleanup and labels only rename or move values, and model change also re-derived phases and creator types on 5 Oct 2026, as proposals. The log starts with the first version of the dataset, whose values have no line; a row or relation added later is one line (`(row)` or `relation`), and older lines may use field names renamed since (`type`, `stakeholder`, `stakeholders`). A change of `reviewedBy` to initials is a confirmation, and so is a row added in the sheet with initials (its `(row)` line). FIP identifiers (`fsr`) are replaced on each FIP import and not logged. The log is published with the code; it cites the manuscript drafts by section and line.
