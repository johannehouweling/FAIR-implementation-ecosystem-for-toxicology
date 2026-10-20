# Inclusion and exclusion criteria

This document explains which resources the dataset contains and how that was decided. The rules are applied per
row in the dataset: every screened candidate keeps its row, with its decision and, when excluded, the reason.

## 1. Terminology

The terms follow the typology of FAIR Supporting Resources of Magagna et al. 2024 (*Ontological Analysis of FAIR
Supporting Resources*, CEUR-WS Vol-3882) and the FIP ontology (`https://w3id.org/fair/fip/terms/FIP-Ontology`, read
from `https://w3id.org/fair/fip/terms/`), whose FSR typology gives the FSR types (data dictionary, FSR type). The
types were checked against version 20260227 (`https://w3id.org/fair/fip/terms/FIP-Ontology_20260227`), and
validation warns when the ontology moves on.

- A **FAIR Supporting Resource (FSR)** is any resource that supports FAIR implementation.
- A **FAIR-Enabling Resource (FER)** is an FSR that is essential to the operationalisation of the FAIR principles: a
  service, a specification or a data policy, such as an identifier service, a registry, a metadata schema or a
  structured vocabulary.

The dataset lists standards, databases, policies and guidance, collections, and tools or services that make data or
metadata findable, accessible, interoperable or reusable, each typed as an FER or another FSR (section
6). Their FAIRsharing types follow the FAIRsharing registries (standards, databases, policies, collections)
and their record types; software and services, which FAIRsharing does not register, are recorded as Tool. Initiatives,
projects and communities are not resources: they appear only through the resources they produced, except FAIR
Implementation Communities (E1).

## 2. Sources screened

| Source | Version | What it contributes |
|---|---|---|
| Manuscript draft | ELIXIR Toxicology Community paper, Google Docs export (8) of 2 Oct 2026, frozen by SHA-256 checksum in the dataset header | Every named entity in the text, Table 1, figure captions, to-do notes and comments |
| FAIRsharing Toxicology collection | Record 3496; membership as read on the retrieval date published with the dataset | All collection members |
| FAIRsharing neighbours | Records linked to collection members ("two hops") | Reported only; not screened |
| PARC Toxicology FIP | Nanopublication `https://w3id.org/np/RAKa7vUwc8qVbktDqDSpuq7lRrrKcjPKvkB4Tn7WHvr7E` (7 Sep 2026), read through its declaration index on the retrieval date published with the dataset | Every resource it declares, and the community that declares it |
| Reference AOP FIP | Nanopublication `https://w3id.org/np/RAQMnw2u-ZG_zVkVIzEdtYn3o4tYqyhsnOhiWaMLG01Bc` (14 Jul 2025), read the same way | Every resource it declares, and the community that declares it |
| Co-author additions | Rows added in the curation Sheet | New candidates; the addition documents toxicology use (I4) |
| ELIXIR Toxicology Community documents | Martens et al. 2023, "ELIXIR and Toxicology: a community in development", F1000Research, doi 10.12688/f1000research.74502.2; FAIRsharing's report on the collection, 3 Jul 2025, doi 10.5281/zenodo.15799783; the reports of INTOXICOM workshops 1 to 5, preprints on BioHackrXiv: Martens et al. 2024, doi 10.37044/osf.io/un2rw; Bonatto Minella et al. 2026, doi 10.37044/osf.io/64dfv_v1; Bünger et al. 2026, doi 10.37044/osf.io/u3fnh_v1; for workshop 4 a draft, github.com/TGX-UM/INTOXICOM_Workshop_4; Evelo et al. 2026, doi 10.37044/osf.io/zf2qj_v1 | Mentions of a row, ticked by curators in the sheet; a mention documents toxicology use (I4) |

The PARC TOXRIC FIP (2024), an earlier FIP of the PARC toxicology community, is known but not imported.

The list of data repositories compiled for the impact section of the paper (repository list, version 2) was
considered and not used: it lists places to deposit or explore data for measuring reuse, not the resources the paper
discusses. The previous inventory of this work (FAIR_tox, audit of 2 Oct 2026) was not used for selection; its
first-release years, DOIs, FAIRsharing records and relations were used as evidence to be verified.

## 3. Inclusion criteria

A candidate is included when all of these hold:

- **I1** It is a resource, not an organisation, project, community, event or publication, except a FAIR
  Implementation Community (E1).
- **I2** It is named and identifiable: it has a homepage or a DOI.
- **I3** It is or was publicly available. Discontinued resources are kept and marked as discontinued.
- **I4** Its use in toxicology is documented: it is named in the manuscript in a toxicology context, it is a member
  of the FAIRsharing Toxicology collection, it is declared in a toxicology FIP, it is mentioned in an ELIXIR
  Toxicology Community document (section 2), or a co-author added it.
- **I5** It makes data or metadata findable, accessible, interoperable or reusable.

## 4. Exclusion reasons

Each excluded row carries exactly one code.

| Code | Reason | Examples from the manuscript |
|---|---|---|
| E1 | Organisation, project, initiative, consortium, community or event, unless a registered FAIR Implementation Community (FIC) nanopublication identifies it (section 5). Its named product is listed as its own row. | EU-ToxRisk, eNanoMapper (the project), NanoCommons (the project), OpenRiskNet, eTRANSAFE, FAIRplus |
| E2 | Principle, framework, method or approach, or a publication only, rather than a resource that can be used directly; a standard, database, policy or tool that puts it into practice is listed instead. | The FAIR principles (shown as the 2016 line in the figure), the AOP framework, IATA |
| E3 | Unnamed or not identifiable. | Services or pipelines mentioned in passing without a name |
| E4 | Never publicly available. | A resource that cannot be found online and has no archived release |
| E5 | No documented use in toxicology. | A generic resource named only outside a toxicology context |
| E6 | Duplicate, version or component of another row; that row is named in Covered by. | An alternative name or a version without its own identity |
| E7 | Outside chemical toxicology. | Toxinology or clinical adverse-event grading resources |
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

- **Scope** says what a resource was made for: Generic (infrastructure not specific to a research domain, including
  FAIR resources such as FAIRsharing and the FIP), Life Sciences (life-science infrastructure) or Toxicology.
- **FSR type.** Each resource gets one type of the FSR typology of the FIP ontology. When a toxicology FIP declares
  the resource, the type comes from the FIP's own description of it (if that gives several, the one that fits the
  question it is declared for). Otherwise the kind of resource decides: a database, including a portal or a report
  repository, is a Domain-specific or Generalist registry, as databases are in FIPs; an identifier scheme is an
  Identifier service; a terminology or ontology a Structured vocabulary or Semantic model; a reporting guideline, model
  or format a Metadata schema or Knowledge representation language; a licence a Data usage license; guidance,
  including regulatory guidance, training material and statements on the FAIR principles, a FAIR practice; a tool or
  service, including software, its service type, such as Editor, FAIR Analysis Service or Validation service. The
  class (FAIR-Enabling Resource or other FAIR Supporting Resource) follows from the type. FAIR principles are assigned
  only through the FIP questions a resource is declared for, so a resource that no FIP declares has none.
- **Phase.** A toxicology resource's phase is the data life-cycle phase it acts on, whoever made it: Data generation
  (planning, producing and depositing primary records: datasets, protocols, method descriptions and the publications
  reporting them), Data integration (integrating and synthesising those records into secondary resources and evidence:
  curated databases, knowledge bases, ontologies, pathway networks and models) or Regulatory assessment (assessing
  records and secondary resources for reliability and relevance in a regulatory context and integrating them into
  weight of evidence and decisions). When it acts on several, its phase is the earliest at which it must be applied,
  and every phase it acts on is recorded as its span.
- **Creator types.** Who created a toxicology resource is recorded separately as one or more creator types: wet-lab
  research, in silico research and regulator. A resource made by a consortium gets all types that apply; the
  organisations are named in Creator.
- **Building on FAIR** is derived, not chosen: a toxicology resource builds on FAIR when it was first published in
  2016 or later and implements, extends, profiles or recommends a generic resource, such as a toxicology FAIR Implementation Profile building on the FIP.
- **Lanes.** The dashboard places Generic resources in Generic infrastructure, Life Sciences resources in Life sciences
  infrastructure, and toxicology resources in the lane of their phase (Data generation, Data integration, Regulatory
  assessment), which together form the toxicology infrastructure. The toxicology lanes can also be arranged by creator
  type, with one lane for resources made jointly. FAIR Implementation Communities are listed but not drawn.
- **Sub-domains** are those of the manuscript: in vitro toxicology, nanotoxicology, exposome, eco-toxicology,
  toxicogenomics, AOP-based mechanistic knowledge, computational and predictive toxicology, regulatory toxicology.
  They are proposed from the section that discusses a resource and from its FAIRsharing subjects, and a resource
  may have several.
- **Type** is the FAIRsharing registry and record type, or Tool.
- **First published** is the earliest date the resource was publicly available or formally described: its release or
  launch, the online publication of the paper that first describes it, or the official adoption of guidance. Sources
  are, in order: the DOI metadata of the describing paper, the first software release, the first ontology release,
  the publisher's or agency's page, the earliest web archive capture (as a lower bound only), and, as a last resort,
  FAIRsharing's year of creation. The basis and source of each date are recorded.
- **Relations** use six FAIRsharing labels: implements, extends, profiles, recommends, deprecates (lineage) and
  related_to. Each relation records its evidence: the manuscript, FAIRsharing, the literature, or a curator. FIP
  declarations are not relations: they are read from the FIPs whenever the dashboard or the curation sheet is built.

## 7. Process

1. **Extraction.** Two independent passes listed every named entity in the manuscript draft, including entities that
   were then excluded, so that the counts are complete. The passes were reconciled, every row's line references,
   manuscript status and classification were checked against the text, and a final sweep looked for missed names.
2. **FAIRsharing and FIPs.** The collection members were added as undecided rows; `fairtox fairsharing --apply` adds
   new members the same way. A member is matched to a manuscript row only through a recorded FAIRsharing record;
   homepage and name matches are proposed for a curator to confirm. `fairtox fip` reads both FIPs through their
   declaration indexes, skips invalidated declarations and reports how each declared resource matches a row (by
   FAIRsharing record, homepage or name); after review, `fairtox fip --apply` links the matched rows and adds the other
   declared resources as undecided rows. FAIRsharing record data, collection membership and associations, and the FIP
   declarations, are read whenever the dashboard or the curation sheet is built, published with their retrieval date
   and never stored.
3. **Evidence.** Dates, homepages, descriptions and FAIRsharing records were researched for every included or
   undecided row, each with its source, and checked by a second pass. This research, the screening and classification
   proposals and the relation checks were drafted with an AI-assisted workflow (Claude Opus 5.5, Anthropic) and remain
   proposals until a curator confirms them (step 4). `data/changes.csv` records each change with its process
   (research, verification, classification, relation check, phase proposal, review, migration) and source.
4. **Curation.** Co-authors review every row in the curation Sheet. Disagreements are discussed and settled by the
   corresponding authors; the outcome and the reviewer's initials are recorded in the row and in `data/changes.csv`.
   Curators also tick, for each row, the ELIXIR Toxicology Community documents that mention it. A curator confirms a
   row by putting their initials in Reviewed by once every value up to Note is checked, and a relation likewise on the
   Relations tab; its values are then curator decisions. The folded context is not covered. A process that later
   changes a confirmed value empties Reviewed by, so the row is confirmed again. The data refresh reads the Sheet back
   with `fairtox ingest` three times a day, row by row, and keeps the changes in one pull request for review; each
   change is logged under the Reviewed by of its row or relation. A row or relation with a problem, or one that would
   add an error or a warning, waits in the Sheet (a row with its relations) and is listed in the pull request until
   it is fixed; two lines with the same key or the same relation both wait. So does a row or relation that changed in
   the dataset after the Sheet was made, other than by an earlier read-back, until the Sheet is updated. A relation
   line whose resource, relation or target is edited replaces its relation; a relation whose line is deleted is left
   unchanged and listed in the pull request, and Keep set to remove drops it.
5. **Release.** A version is released by merging the release pull request that release-please keeps open: it sets the
   version and writes the `CHANGELOG.md` entry from the Conventional Commits since the last release. CI makes the
   release only after the tests and `fairtox validate --strict` pass.

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