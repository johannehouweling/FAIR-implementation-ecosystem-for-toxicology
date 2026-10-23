# Inclusion and exclusion criteria

This document explains which resources the dataset contains and how that was decided. The rules are applied per
row in the dataset: every screened candidate keeps its row, with its decision and, when excluded, the reason.

## 1. Terminology

The terms follow the typology of FAIR Supporting Resources of Magagna et al. 2024 (*Ontological Analysis of FAIR
Supporting Resources*, CEUR-WS Vol-3882) and the FIP ontology, whose FSR typology gives the FSR types (data
dictionary, FSR type, with the ontology version they were checked against); validation warns when the ontology moves
on.

- A **FAIR Supporting Resource (FSR)** is any resource that supports FAIR implementation.
- A **FAIR-Enabling Resource (FER)** is an FSR that is essential to the operationalisation of the FAIR principles: a
  service, a specification or a data policy, such as an identifier service, a registry, a metadata schema or a
  structured vocabulary.

The dataset lists standards, databases, policies and guidance, collections, and tools or services that make data or
metadata findable, accessible, interoperable or reusable, each typed as an FER or another FSR (section 6).

## 2. Sources screened

| Source | Version | What it contributes |
|---|---|---|
| Manuscript draft | ELIXIR Toxicology Community paper, Google Docs export (8) of 2 Oct 2026, frozen by SHA-256 checksum in the dataset header | Every named entity in the text, Table 1, figure captions, to-do notes and comments |
| FAIRsharing Toxicology collection | Record 3496; membership as read on the retrieval date published with the dataset | All collection members |
| FAIRsharing neighbours | Records linked to collection members ("two hops") | Reported only; not screened |
| PARC Toxicology FIP | Nanopublication `https://w3id.org/np/RAKa7vUwc8qVbktDqDSpuq7lRrrKcjPKvkB4Tn7WHvr7E` (7 Sep 2026), read through its declaration index on the retrieval date published with the dataset | Every resource it declares, and the community that declares it |
| Reference AOP FIP | Nanopublication `https://w3id.org/np/RAQMnw2u-ZG_zVkVIzEdtYn3o4tYqyhsnOhiWaMLG01Bc` (14 Jul 2025), read the same way | Every resource it declares, and the community that declares it |
| Co-author additions | Rows added in the curation Sheet | New candidates |
| Co-author repository inventory | A co-author's list of repositories for toxicology data (a Google Sheet, read 21 Oct 2026; its name and the keys taken from it in the dataset header) | New candidates, added as rows |
| ELIXIR Toxicology Community documents | The documents listed in the data dictionary (Community documents) | Mentions of a row, ticked by curators in the sheet |

The PARC TOXRIC FIP (2024), an earlier FIP of the PARC toxicology community, is known but not imported.

The list of data repositories compiled for the impact section of the paper (repository list, version 2) was
considered and not used: it lists places to deposit or explore data for measuring reuse, not the resources the paper
discusses. The previous inventory of this work (FAIR_tox, audit of 2 Oct 2026) was not used for selection; its
first-release years, DOIs, FAIRsharing records and relations were used as evidence to be verified.

## 3. Inclusion criteria

A candidate is included when all of these hold:

- **I1** It is a resource, not an organisation, project, community, event or publication, except a FAIR
  Implementation Community (section 5).
- **I2** It is named and identifiable: it has a homepage or a DOI.
- **I3** It is or was publicly available. Discontinued resources are kept and marked as discontinued.
- **I4** Its use in toxicology is documented: it is named in the manuscript in a toxicology context, it is a member
  of the FAIRsharing Toxicology collection, it is declared in a toxicology FIP, it is mentioned in an ELIXIR
  Toxicology Community document, or a co-author added it or listed it in a repository inventory (section 2).
- **I5** It makes data or metadata findable, accessible, interoperable or reusable.

## 4. Exclusion reasons

Each excluded row carries exactly one code.

| Code | Reason | Examples from the manuscript |
|---|---|---|
| E1 | Organisation, project, initiative, consortium, community or event; its named product is listed instead. For a FAIR Implementation Community (FIC), see section 5. | EU-ToxRisk, eNanoMapper (the project), NanoCommons (the project), OpenRiskNet, eTRANSAFE, FAIRplus |
| E2 | Principle, framework, method or approach, or a publication only, rather than a resource that can be used directly; a standard, database, policy or tool that puts it into practice is listed instead. | The FAIR principles (shown as the 2016 line in the figure), the AOP framework, IATA |
| E3 | Unnamed or not identifiable (no homepage or DOI). | Services or pipelines mentioned in passing without a name |
| E4 | Never publicly available. | A resource that cannot be found online and has no archived release |
| E5 | No documented toxicology use. | A generic resource named only outside a toxicology context |
| E6 | Duplicate, version or component of another row (see Covered by). | An alternative name or a version without its own identity |
| E7 | Outside chemical toxicology, such as toxinology or clinical adverse-event grading. | Toxinology or clinical adverse-event grading resources |
| E8 | Test method or guideline that standardises an experiment rather than data or metadata. | An OECD test guideline that describes how to run an assay |

## 5. Rules for borderline cases

- **Project and product.** The project is excluded (E1); each named product is judged on its own (for example the
  eNanoMapper ontology and database, the NanoCommons Knowledge Base, AOPLink from OpenRiskNet).
- **FAIR Implementation Communities.** A community is kept only when a valid (not invalidated) FIC nanopublication
  identifies it. The row is typed FAIR Implementation Community, takes that nanopublication as its identifier, and is
  listed but not drawn in the figure. `fairtox fip` lists the FIC nanopublications whose name or homepage matches an
  E1 row, and `--apply` adds the communities that declare a FIP; curators check only that a nanopublication is the
  same community and never judge whether a community is a FIC. Every other community stays E1.
- **Availability.** A resource the manuscript names but that cannot be found (for example the eTRANSAFE knowledge
  hub, ToxDataExplorer) stays undecided until the co-authors confirm it exists or existed (I3).
- **Guidance, test guidelines and quality systems.** Guidance on how to report, share or describe data is included as
  a policy; guidelines that only standardise how an experiment is run are excluded (E8).
- **Generic resource and toxicology instance.** Both are rows when each has its own identity, such as RDMkit and its
  toxicology page, or FAIRsharing and the Toxicology collection. The toxicology instance has scope Toxicology and a
  relation to the generic resource it builds on.
- **Versions and successors.** A successor is its own row when it has its own name, identifier or paper (for example
  ISA-JSON after ISA-Tab); otherwise it is covered by the original (E6).
- **RDF conversions.** A conversion is its own row only with its own identifier, endpoint or paper (AOP-Wiki RDF,
  AOP-DB RDF).
- **Programmes and their data.** A screening programme counts only through a named data resource (for example the
  ToxCast and Tox21 data rather than the programmes).
- **Generic web and semantic-web standards** (RDF, OWL, SPARQL, JSON-LD, nanopublications) and FAIR assessment tools
  (F-UJI) are resources with scope Generic when the manuscript uses them for toxicology.

## 6. Classification

- **Scope** says what a resource was made for (data dictionary, Scope).
- **FSR types.** Each resource gets every type of the FSR typology of the FIP ontology that applies. When a
  toxicology FIP declares the resource, its types are those of the typology that the FIP's own description gives it.
  Otherwise the kind of resource decides: a database, including a portal or a report
  repository, is a Domain-specific or Generalist registry, as databases are in FIPs; an identifier scheme is an
  Identifier service; a terminology or ontology a Structured vocabulary or Semantic model; a reporting guideline, model
  or format a Metadata schema or Knowledge representation language; a licence a Data usage license; guidance,
  including regulatory guidance, training material and statements on the FAIR principles, a FAIR practice; a tool or
  service, including software, its service type, such as Editor, FAIR Analysis Service or Validation service. A FAIR
  Implementation Community has no other type. The class (FAIR-Enabling Resource or other FAIR Supporting Resource)
  follows from the types: a resource is a FAIR-Enabling Resource when one of its types is. FAIR principles are assigned
  only through the FIP questions a resource is declared for, so a resource that no FIP declares has none.
- **Phase.** A toxicology resource's phase is the data life-cycle phase it acts on, whoever made it (data dictionary,
  Phase). When it acts on several, its phase is the earliest at which it must be applied, and every phase it acts on
  is recorded as its span.
- **Creator types.** Who created a toxicology resource is recorded separately as one or more creator types (data
  dictionary, Creator types). A resource made by a consortium gets all types that apply; the organisations are named
  in Creator.
- **Building on FAIR** is derived, not chosen: a toxicology resource builds on FAIR when it was first published in
  2016 or later and implements, extends, profiles or recommends a generic resource, such as a toxicology FAIR Implementation Profile building on the FIP.
- **Lanes.** The dashboard places Generic resources in Generic infrastructure, Life Sciences resources in Life sciences
  infrastructure, and toxicology resources in the lane of their phase (data dictionary, Lanes). The toxicology lanes,
  which together form the toxicology infrastructure, can also be arranged by creator type, with one lane for resources
  made jointly. FAIR Implementation Communities are listed but not drawn.
- **Sub-domains** are those of the manuscript (data dictionary, Sub-domains). They are proposed from the section that
  discusses a resource and from its FAIRsharing subjects, and a resource may have several.
- **FAIRsharing type** is the FAIRsharing registry and record type, or Tool (data dictionary, FAIRsharing type).
- **First published** is the earliest date the resource was publicly available or formally described, recorded with
  its basis (data dictionary, Date basis) and its source. Sources are, in order: the DOI metadata of the describing
  paper, the first software release, the first ontology release, the publisher's or agency's page, the earliest web
  archive capture (as a lower bound only), and, as a last resort, FAIRsharing's year of creation.
- **Relations** use the labels of the data dictionary (Relations), which also lists the registry pairs FAIRsharing
  allows for each label. A relation must be possible: FAIRsharing allows its label between the FAIRsharing registries
  of its two resources; a Tool, which FAIRsharing does not register, or a Collection also counts as the registry of
  each of its FSR typology columns (FAIR Data Policy as a Policy, FAIR specification as a Standard, FAIR Supporting
  Technology as a Database); and implements is also possible from a FAIR-Enabling Resource to a FAIR specification,
  the domain and range of `fip:implements`. The label uses is always possible, and so is any relation while an end has
  no FAIRsharing type or is a Tool without an FSR type. A relation that is not possible is a warning (section 7); one
  that is possible but that FAIRsharing cannot hold is kept and flagged as not enterable in FAIRsharing. A lineage
  relation to a resource first published in a later year is a warning unless FAIRsharing asserts it. Each relation
  records its evidence (data dictionary, Relation evidence). FIP declarations are not relations.

## 7. Process

1. **Extraction.** Two independent passes listed every named entity in the manuscript draft, including entities that
   were then excluded, so that the counts are complete. The passes were reconciled, every row's line references,
   manuscript status and classification were checked against the text, and a final sweep looked for missed names.
2. **FAIRsharing and FIPs.** The collection members were added as undecided rows; `fairtox fairsharing --apply` adds
   new members the same way, their curated fields filled from their records. A member is matched to a manuscript row
   only through a recorded FAIRsharing record; homepage and name matches are proposed for a curator to confirm.
   `fairtox fip` reads both FIPs through their declaration indexes, skips invalidated declarations and reports how each
   declared resource matches a row (by FAIRsharing record, homepage or name); after review, `fairtox fip --apply` links
   the matched rows and adds the other declared resources as undecided rows. FAIRsharing record data and the FIP
   declarations are never stored: they are read when the outputs are built (data dictionary, Fields added at build
   time).
3. **Evidence.** Dates, homepages, descriptions and FAIRsharing records were researched for every included or
   undecided row, each with its source, and checked by a second pass. This research, the screening and classification
   proposals and the relation checks were drafted with an AI-assisted workflow (Claude Opus 5.5, Anthropic) and remain
   proposals until a curator confirms them (step 4). `data/changes.csv` records each change with its process and
   source (data dictionary, Change log).
4. **Curation.** Co-authors review every row in the curation Sheet. Disagreements are discussed and settled by the
   corresponding authors; the outcome and the reviewer's initials are recorded in the row and in `data/changes.csv`.
   Curators also tick, for each row, the ELIXIR Toxicology Community documents that mention it. A curator confirms a
   row by putting their initials in Reviewed by once every value up to Note is checked, and a relation likewise on the
   Relations tab; its values are then curator decisions. The folded context is not covered. A process that later
   changes a confirmed value empties Reviewed by, so the row is confirmed again. The data refresh reads the Sheet back
   with `fairtox ingest` three times a day, row by row, and keeps the changes in one pull request for review. A row or
   relation with a problem, or one that would add an error or a warning, waits in the Sheet (a row with its relations)
   and is listed in the pull request until it is fixed; two lines with the same key both wait, and so do two lines with
   the same relation unless exactly one of them is signed: that line decides, and the unsigned copies are ignored and
   listed in the pull request. So does a row or relation that changed in the dataset after the Sheet was made, other
   than by an earlier read-back, until the Sheet is updated. A relation line whose resource, relation or target is
   edited replaces its relation; a relation whose line is deleted is left unchanged and listed in the pull request, and
   Keep set to remove drops it.
5. **Release.** A version is released by merging the release pull request (README, Data flow); CI makes the release
   only after the tests pass and `fairtox validate --strict` finds no error or warning.

## 8. Decision record

| Date | Decision | By |
|---|---|---|
| 2 Oct 2026 | A resource's lane follows where it comes from; guidance made by regulators belongs to Application. | Jente Houweling |
| 3 Oct 2026 | Relations use FAIRsharing's relation labels only, so that every relation can be entered in FAIRsharing. | Jente Houweling |
| 5 Oct 2026 | FERs only, not initiatives. The phase of a toxicology resource follows the stakeholder who created it. Sub-domains are those of the manuscript; a resource can have several. Toxicology building on FAIR is a scope of its own. | Jente Houweling |
| 5 Oct 2026 | Alignment with the PARC Toxicology and Reference AOP FAIR Implementation Profiles follows after the first curated version. | Jente Houweling |
| 5 Oct 2026 | The phase of a toxicology resource is its main intended use, chosen directly; who made it is recorded separately as one or more creator types (wet-lab research, in silico research, regulator), so both can be plotted. "Toxicology building on FAIR" is no longer a scope: it is derived from a builds-on relation to a FAIR resource, and those resources sit in the toxicology lanes. This replaces the earlier rule that the creator sets the phase. | Jente Houweling |
| 5 Oct 2026 | Scope and lane FAIR are renamed Generic (generic infrastructure): several of these resources (RDF, OWL, SPARQL, nanopublications, FAIRsharing as BioSharing) predate the FAIR principles, so calling them FAIR was anachronistic. For the same reason a toxicology resource counts as building on FAIR only when first published in 2016 or later. | Jente Houweling |
| 8 Oct 2026 | The declarations of the PARC Toxicology FIP and the Reference AOP FIP are imported through each FIP's declaration index, never by community, which also returns earlier and invalidated profiles. Only these two FIPs are imported. A declaration in a toxicology FIP counts as documented toxicology use (I4). | Jente Houweling |
| 8 Oct 2026 | Resources are typed in the FIP ontology after Magagna et al. 2024: the type a FIP gives a resource comes first; otherwise the role that makes it FAIR-relevant decides, and content is a digital object. At most two types, under one direct FSR subclass. Principles come only from the FIP questions a resource is declared for. | Jente Houweling |
| 8 Oct 2026 | The phases become Data generation, Data integration and Regulatory assessment, defined by the data life cycle. A toxicology resource takes the earliest phase it acts on, and every phase it acts on is recorded as its span; the lanes follow. This replaces the phase by main intended use. | Jente Houweling |
| 8 Oct 2026 | FAIR Implementation Communities are recognised mechanically: a community is kept, typed FAIR Implementation Community, only when a valid FIC nanopublication identifies it, and is listed but not drawn. Curators check only that a nanopublication is the same community, never whether a community is a FIC; every other community stays E1. | Jente Houweling |
| 8 Oct 2026 | The JSON-LD context maps the fields to schema.org, DCTERMS, DCAT, SKOS, PAV and the FIP ontology; only 14 core terms and the class Digital object are the dataset's own (`https://w3id.org/fair-tox/terms#`). | Jente Houweling |
| 9 Oct 2026 | FAIRsharing record data, the FIP declarations and the FIP ontology are read when the dashboard and the curation sheet are built, and published with their retrieval date. The dataset stores only what is curated. | Jente Houweling |
| 9 Oct 2026 | Typing is simplified: every resource is an FSR with one type from the FIP ontology, chosen by the kind of resource, the type a FIP gives coming first. A database that indexes and serves records under stable identifiers is a registry, as in FIPs; the own class Digital object and second types are dropped, and the curation sheet offers only the 27 types the rule uses. | Jente Houweling |
| 9 Oct 2026 | Curation is done in the curation sheet only; the dashboard has no separate curation view. A release has no validation warnings: relations that FAIRsharing cannot hold are shown in the sheet rather than warned about, and a pending FAIRsharing match is a warning only for an included resource. | Jente Houweling |
| 9 Oct 2026 | Every field takes a term of schema.org, else of DCAT, and of the FIP ontology for FSR types and FIP declarations; the dataset defines no properties of its own. Controlled values are concepts of established vocabularies wherever one fits, preferring resources in the dataset, such as the IUPAC toxicology glossary; the other values are terms of the dataset, each linked to its closest concepts. Derived and curation fields stay out of the graph, and field and column names stay readable. This replaces the own terms of 8 Oct. | Jente Houweling |
| 9 Oct 2026 | A date is stored under the property of what it refers to, after DataCite's date types: publication `schema:datePublished`, release `dct:issued`, adoption `dct:dateAccepted`, FAIRsharing year `schema:dateCreated`, and no recorded basis `dct:date`. | Jente Houweling |
| 9 Oct 2026 | A resource with a confirmed FAIRsharing record keeps the record DOI as its identifier, as the FIP Wizard and the two toxicology FIPs do, although FAIRsharing describes the DOI as identifying its record; each resource states its identifier and homepage. | Jente Houweling |
| 9 Oct 2026 | The published dataset follows CODATA's CDIF Discovery profile 1.1, and its term lists the CDIF Concept Scheme profile 1.1; CI checks the dataset with CODATA's SHACL rules. An unknown maintenance status is not published. | Jente Houweling |
| 10 Oct 2026 | The creator types are stored as `creatorType` (formerly `stakeholders`) and published as qualified attributions (`prov:qualifiedAttribution`) whose role (`dcat:hadRole`) is the EFO or SIO concept: they say who made a resource, not what it is about (`dcat:theme`), and they are kinds of creator, not creators (`schema:creator`). | Jente Houweling |
| 10 Oct 2026 | Identifiers are written in full and the context sets no `@base`, which a context loaded by URL may not set. The FAIRsharing type is stored as `fairsharingType`, since `type` is schema.org's alias of `@type`. The IRIs under which the FIPs declare a resource are `schema:sameAs`, since SKOS mappings relate concepts. The catalog record names its maintainer, as in the CDIF examples. | Jente Houweling |
| 10 Oct 2026 | FAIRsharing's subjects and domains of a confirmed record are published on the FAIRsharing record that the resource links to (`schema:sameAs`): its subjects (subject areas) as `schema:about`, the property of the curated scope, and its domains (the kinds of data, entities and activities a record covers, some of them life-cycle activities such as study design) as `dcat:theme`, the property of the curated phases. They are FAIRsharing's statements: read when the dataset and the sheet are built, shown in grey columns of the sheet next to Scope and Span, and neither stored in the dataset nor read back. | Jente Houweling |
| 10 Oct 2026 | Versions and the changelog follow the Conventional Commits: release-please proposes each release as a pull request, and a release is made only from a commit that passed CI. | Jente Houweling |
| 10 Oct 2026 | Edits made in the curation sheet are read back daily and reach the dataset only through a reviewed pull request. | Jente Houweling |
| 10 Oct 2026 | The curation sheet puts what curators check first, in the order of the curation steps and ending with Reviewed by and Note; the context (identifiers, FAIRsharing and FIP data, derived fields, the manuscript columns) follows, folded. | Jente Houweling |
| 17 Oct 2026 | A mention in an ELIXIR Toxicology Community document documents toxicology use (I4). Curators tick the documents in the sheet (`mentionedIn`): the white paper (Martens et al. 2023), FAIRsharing's report on the collection of 3 Jul 2025 and the INTOXICOM workshop reports 1, 2, 3 and 5. The sheet also shows, computed, where each resource is found now (manuscript draft, FAIRsharing Toxicology collection, a toxicology FIP, co-author addition) in a Source column after URL, an exception to the layout of 10 Oct 2026, which replaces In FAIRsharing collection. | Jente Houweling |
| 18 Oct 2026 | A value is a proposal until a curator confirms its row, or relation, by putting initials in Reviewed by after checking every value up to Note; a process that changes a confirmed value empties Reviewed by. Nothing else is stored: `data/changes.csv` records each proposal under its process, each change made in the Sheet under the Reviewed by of its row or relation, and each confirmation as a change of Reviewed by. The data refresh reads the Sheet back three times a day, row by row: a row or relation with a problem, or one that would add an error or a warning, waits and is listed in the pull request. A new row gets a key typed by its curator; a key left empty is made from the name on import. | Jente Houweling |
| 18 Oct 2026 | The FSR types are the FSR typology of the FIP ontology as the ontology draws it, read from the ontology: the classes under FAIR Data Policy, FAIR specification and FAIR Supporting Technology, and one level below, that are not deprecated (31), with FAIR Implementation Community for communities. FAIR-Enabling Resource still follows from the type. Guidance, training material and statements on the FAIR principles are FAIR practices, and software takes its service type; the six resources typed FAIR training material, FAIR interpretation or the deprecated FAIR Supporting Software were retyped accordingly. This replaces the 27 types of 9 Oct 2026. | Jente Houweling |
| 18 Oct 2026 | A co-author's addition documents toxicology use (I4), like a mention in the manuscript or a community document. `data/changes.csv` is published with the code and cites the manuscript drafts by section and line; the drafts never enter the repository. | Jente Houweling |
| 18 Oct 2026 | Each line on the Relations tab carries a line version, as each row carries its row version. A relation changed in the dataset after the Sheet was made waits instead of being put back; a line whose resource, relation or target is edited replaces its relation; a deleted line leaves its relation unchanged and is listed in the pull request, since it cannot be told apart from a relation added after the Sheet was made. | Jente Houweling |
| 19 Oct 2026 | The curation sheet shows FAIRsharing's subjects and domains of a record beside the fields they help check, the subjects after Scope and the domains after the Span columns, an exception to the layout of 10 Oct 2026. | Jente Houweling |
| 19 Oct 2026 | The report of INTOXICOM workshop 4 counts as an ELIXIR Toxicology Community document too; its tick boxes in the sheet are read back like the others. | Jente Houweling |
| 20 Oct 2026 | The curation sheet records a toxicology resource's phases in one multi-select Phase column instead of Phase and three Span columns: the earliest chosen is its phase and sets the lane, and all chosen are its span. Its sub-domains are chosen in one multi-select Sub-domains column instead of one tick column each. Reviewed by and Sub-domains come right after Name and URL, so that curators find the rows they signed and the resources of their sub-domain. The dataset is unchanged. | Jente Houweling |
| 21 Oct 2026 | A relation must be possible: FAIRsharing allows its label between the registries of its two resources, a Tool or a Collection also counting as the registry of its FSR typology column, and implements also from a FAIR-Enabling Resource to a FAIR specification. A relation that is not possible is a warning, so it waits in the sheet and blocks a release; one that is possible but that FAIRsharing cannot hold is still only shown. This replaces the 9 Oct 2026 rule for relations FAIRsharing cannot hold. | Jente Houweling |
| 21 Oct 2026 | A seventh relation label, uses, is the dataset's own: "The subject uses the target." It is lineage, FAIRsharing cannot hold it, the possibility rule does not constrain it, and it does not count for Builds on FAIR. This amends the 3 Oct 2026 rule that relations use FAIRsharing's labels only. | Jente Houweling |
| 23 Oct 2026 | A resource takes every FSR type that applies, chosen in one multi-select FSR type column of the curation sheet: the types of the typology that the FIP's own description gives it when a toxicology FIP declares it, otherwise those its kind gives. It is a FAIR-Enabling Resource when one of its types is one. For a relation, a Tool or a Collection counts as the registry of each of its FSR typology columns. A FAIR Implementation Community has no other type. Rows declared in a toxicology FIP and not yet confirmed were given, as proposals, the other types of their FIP's description. This replaces the one type per resource of 9 Oct 2026 and amends the relation rule of 21 Oct 2026 to match. | Jente Houweling |
| 23 Oct 2026 | Each resource records who to contact about it, as the ORCID of a person or the ROR of an organisation (`contactPoint`, DCAT's `dcat:contactPoint`, as schema.org has none for a creative work), in a Contact column of the curation sheet after Creator. Creator still names the organisations that made the resource. | Jente Houweling |
| 23 Oct 2026 | When a relation appears on several lines of the Relations tab and exactly one of them is signed, the signed line decides; the unsigned copies are ignored and listed in the pull request, so a copy never has to be deleted. With no signed line, or more than one, all copies wait as before. | Jente Houweling |

## 9. Limitations

- The manuscript is a draft; line references refer to the frozen version, and later drafts may name other resources.
- The FAIRsharing collection is curated by its maintainers and changes over time; the retrieval date is published
  with the dashboard and the dataset.
- First-publication dates depend on what is documented; some can only be bounded.
- Mentions in the community documents are ticked by curators, not extracted systematically; FAIRsharing's report
  lists its records only in figures.
- Who typed a value in the Sheet is taken from Reviewed by; the Sheet's version history is the full record.
- A release's dashboard and figure cannot be rebuilt identically later: FAIRsharing, the FIP declarations and the FIP
  ontology are read when they are built, and published with their retrieval dates. Each published build is kept in
  the history of the dashboard's repository.
- A read-back can be replayed from its exported sheet, which the data refresh keeps for 90 days; dates are checked
  against the day of the run.
- FSR types, phases and spans are proposals until the co-authors confirm them, and a judgement for resources with
  several roles or uses; creator types depend on what is documented about the makers. All are recorded per resource
  so they can be checked and revised.
- Principles are known only for resources that the two FIPs declare, as read on the retrieval date.