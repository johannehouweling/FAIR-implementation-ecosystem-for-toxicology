# Data dictionary

The dataset is one JSON-LD file, `data/fair-tox-ecosystem.jsonld`, licensed CC BY-SA 4.0. It is a schema.org `Dataset` whose `hasPart` lists the resources. Each resource has its curated fields, an optional `fairsharing` block with data read from FAIRsharing, and its relations to other resources. The file is written only by the `fairtox` commands, which validate every change and log curated changes in `data/changes.csv`.

## Identifiers

- A resource with a confirmed FAIRsharing record is identified by the record DOI, for example `https://doi.org/10.25504/FAIRsharing.6hna78`.
- Any other resource is identified by `#<key>` relative to `https://w3id.org/fair-tox/dataset`. These identifiers are provisional until the resource is registered in FAIRsharing or the namespace is registered at w3id.org.
- Terms without a standard property use `https://w3id.org/fair-tox/terms#`. Standard terms come from schema.org, DCAT and DCTERMS.

## Dataset header

| Field | Meaning |
|---|---|
| `name, description` | Title and summary. |
| `version` | Semantic version, the same as the software and CITATION.cff. A minor version marks a curation round. |
| `dateModified` | Date of the last change to the content. |
| `license` | CC BY-SA 4.0, required because the dataset contains FAIRsharing data. |
| `creator` | ELIXIR Toxicology Community. |
| `creditText` | Attribution to FAIRsharing. |
| `isBasedOn` | The FAIRsharing Toxicology collection (and, later, the toxicology FAIR Implementation Profiles). |
| `sources` | What each source contributed: manuscript version and checksum, FAIRsharing retrieval time and member count. |
| `vocabularies` | Every controlled list with its definitions, so the file can be read on its own. |
| `hasPart` | The resources. |

## Resource fields

Curated fields are edited in the curation Sheet; the column is given. `@id` and `phase` are derived; `fairsharing` is written by `fairtox fetch`.

| Field | Sheet column | Content |
|---|---|---|
| `@id` |  | FAIRsharing DOI when the match is confirmed, else `#key`. |
| `key` | Key | Stable short identifier: lowercase letters, digits, `_` or `-`. Never changes. |
| `name` | Name | Full name. |
| `alternateName` | Aliases | Abbreviations and other names; the first is shown in the figure. |
| `decision` | Decision | Screening decision (list below). |
| `exclusionReason` | Exclusion reason | Code E1-E8, required when the decision is exclude. |
| `coveredBy` | Covered by | Key of the row that covers this one (exclusion reason E6). |
| `type` | Type | FAIRsharing registry and record type, or Tool (list below). |
| `scope` | Scope | What the resource was made for (list below). |
| `stakeholder` | Stakeholder | Who created a toxicology resource; required exactly when the scope is Toxicology. |
| `phase` |  | Toxicology lifecycle phase, derived from the stakeholder. |
| `subdomains` | one column per sub-domain | Sub-domains of the manuscript that apply (list below). |
| `datePublished` | First published | When the resource first became public: `YYYY`, `YYYY-MM` or `YYYY-MM-DD`. |
| `dateBasis` | Date basis | What the date refers to (list below). |
| `dateSource` | Date source | DOI or URL that shows the date. |
| `creator` | Creator | Organisation(s) that made the resource. |
| `url` | Homepage | Main web address. |
| `description` | Description | One to three sentences; needed to register the resource in FAIRsharing. |
| `maintained` | Maintained | Maintenance status (list below). |
| `manuscript` | In manuscript | Whether and how the manuscript names it (list below). |
| `manuscriptEvidence` | Manuscript evidence | Section and line numbers in the frozen manuscript draft. |
| `fairsharingRecord` | FAIRsharing record | FAIRsharing record code (`FAIRsharing.xxxxxx`) or numeric id. |
| `fairsharingMatch` | FAIRsharing match | Whether that record is this resource (list below). |
| `reviewedBy` | Reviewed by | Initials of the curator who checked the row. |
| `note` | Note | Free text for the next curator. |
| `qualifiedRelation` | Relations tab | Relations to other resources (below). |
| `fairsharing` |  | Data read from FAIRsharing (below). Never curated. |

## Lanes

The dashboard lane is derived and not stored: scope FAIR or Toxicology building on FAIR gives FAIR infrastructure, scope Life Sciences gives Life Sciences infrastructure, and scope Toxicology gives the lane of the stakeholder's phase. The last three lanes together form the toxicology infrastructure.

| Lane | Meaning |
|---|---|
| FAIR infrastructure | Generic FAIR resources, and toxicology resources that build on them. |
| Life Sciences infrastructure | Generic life-science resources that toxicology uses. |
| Data Generation | Toxicology infrastructure made by wet-lab research. |
| Tools & Integration | Toxicology infrastructure made by in silico research. |
| Application (regulatory) | Toxicology infrastructure made by regulators. |

| Stakeholder | Phase | Lane |
|---|---|---|
| Wet-lab research | Data Generation | Data Generation |
| In silico research | Data Integration | Tools & Integration |
| Regulator | Application (Regulatory Use) | Application (regulatory) |

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
| E2 | Principle, framework or concept without a reusable artefact, or a publication only. |
| E3 | Unnamed or not identifiable (no homepage or DOI). |
| E4 | Never publicly available. |
| E5 | No documented toxicology use. |
| E6 | Duplicate, version or component of another row (see Covered by). |
| E7 | Outside chemical toxicology, such as toxinology or clinical adverse-event grading. |
| E8 | Test method or guideline that standardises an experiment rather than data or metadata. |

### Type (`type`)

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
| Collection | Collection | collection (15) | Curated collection of FAIR-enabling resources. |
| Tool | (not registered) | - | Software or service; FAIRsharing does not register these. |

### Scope (`scope`)

| Value | Meaning |
|---|---|
| FAIR | Generic FAIR infrastructure, not specific to a research domain. |
| Life Sciences | Generic life-science infrastructure that toxicology uses. |
| Toxicology | Made for toxicology. |
| Toxicology building on FAIR | A toxicology-specific instance of a FAIR resource, such as a toxicology FAIR Implementation Profile or the RDMkit toxicology page. |

### Stakeholder (`stakeholder`)

| Value | Meaning |
|---|---|
| Wet-lab research | Made by experimental (wet-lab) researchers, mostly academic. |
| In silico research | Made by computational researchers: modellers, AOP, PBK, QSAR and nano-informatics. |
| Regulator | Made by a regulatory agency or intergovernmental body, such as OECD, EFSA, ECHA or US EPA. |

### Phase (`phase`)

| Value | Meaning |
|---|---|
| Data Generation | Toxicology lifecycle phase of resources made by wet-lab research. |
| Data Integration | Toxicology lifecycle phase of resources made by in silico research. |
| Application (Regulatory Use) | Toxicology lifecycle phase of resources made by regulators. |

### Sub-domains (`subdomains`)

| Value | Meaning |
|---|---|
| in vitro toxicology | Data generation (manuscript Figure 2 caption and section III). |
| nanotoxicology | Data generation. |
| exposome | Data generation. |
| eco-toxicology | Data generation. |
| toxicogenomics | Integration and tools. |
| AOP-based mechanistic knowledge | Integration and tools. |
| computational and predictive toxicology | Integration and tools. |
| regulatory toxicology | Application. |

### Date basis (`dateBasis`)

| Value | Meaning |
|---|---|
| publication | Online publication of the paper that first describes the resource. |
| release | First public release or launch. |
| adoption | Official adoption or publication of guidance or policy. |
| FAIRsharing year | FAIRsharing's year of creation, used only when nothing better was found. |

### Maintained (`maintained`)

| Value | Meaning |
|---|---|
| active | Maintained and available. |
| discontinued | No longer maintained or available (shown with a dagger). |
| in development | Not yet released in a stable form. |
| unknown | Status could not be established. |

### In manuscript (`manuscript`)

| Value | Meaning |
|---|---|
| cited | Named in the manuscript text with a reference. |
| named | Named in the manuscript text without a reference. |
| comment only | Named only in a comment or to-do note of the manuscript. |
| absent | Not in the manuscript. |

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

## Relations

A relation sits on its subject as a DCAT qualified relation and reads the FAIRsharing way, subject first: "CTD implements ExO". Fields: `relation` (the target's `@id`), `hadRole` (the label), `evidence`, `source`, `reviewedBy`, `note`. Only six of FAIRsharing's fourteen labels are used. Lineage labels are drawn as arrows from the earlier resource to the one building on it; related_to has no arrowhead. A lineage relation normally points to an earlier resource; it may point to a later one only when FAIRsharing asserts it.

| Label (`hadRole`) | FAIRsharing id | Lineage | Meaning | Allowed in FAIRsharing between |
|---|---|---|---|---|
| implements | 1 | yes | The database implements the standard. | Database to Standard |
| extends | 8 | yes | The subject builds on and extends the target. | Database to Database, Policy to Policy, Standard to Standard |
| profiles | 7 | yes | The standard is a profile of the target standard. | Standard to Standard |
| recommends | 11 | yes | The policy recommends the target. | Policy to Collection, Policy to Database, Policy to Standard |
| deprecates | 9 | yes | The subject replaces the target. | Collection to Collection, Database to Database, Policy to Policy, Standard to Standard |
| related_to | 4 | no | The resources are related without one building on the other. | Database to Database, Database to Standard, Policy to Policy, Standard to Database, Standard to Standard |

Relations FAIRsharing does not allow between the two types are kept and flagged as not enterable in FAIRsharing.

## The `fairsharing` block

Written by `fairtox fetch` from the FAIRsharing API; replaced on every refresh: `id`, `doi`, `name`, `abbreviation`, `registry`, `recordType`, `status`, `yearCreation`, `homepage`, `inCollection` (member of the Toxicology collection, record 3496), `associations` (FAIRsharing's own relations of this record: label and record id) and `retrieved` (date). FAIRsharing contact details are never stored.

## Change log

`data/changes.csv` has one row per changed field: `date`, `round` (curation round or refresh), `key`, `field`, `old`, `new`, `by` (the Reviewed by initials from the Sheet) and `source` (workbook file name or FAIRsharing).
