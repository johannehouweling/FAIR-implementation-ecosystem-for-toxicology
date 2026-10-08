# Inclusion and exclusion criteria

This document explains which resources the dataset contains and how that was decided. The rules are applied per
row in the dataset: every screened candidate keeps its row, with its decision and, when excluded, the reason.

## 1. What counts as a FAIR-enabling resource

A FAIR-enabling resource (FER) is a standard, database, policy or guidance document, collection, or tool or service
that makes data or metadata findable, accessible, interoperable or reusable. The types follow the FAIRsharing
registries (standards, databases, policies, collections) and their record types; software and services, which
FAIRsharing does not register, are recorded as Tool. Initiatives, projects and communities are not resources: they
appear only through the resources they produced.

## 2. Sources screened

| Source | Version | What it contributes |
|---|---|---|
| Manuscript draft | ELIXIR Toxicology Community paper, Google Docs export (8) of 2 Oct 2026, frozen by SHA-256 checksum in the dataset header | Every named entity in the text, Table 1, figure captions, to-do notes and comments |
| FAIRsharing Toxicology collection | Record 3496; membership as read on the retrieval date recorded in the dataset header | All collection members |
| FAIRsharing neighbours | Records linked to collection members ("two hops") | Reported only; not screened |
| Co-author additions | Rows added in the curation Sheet | New candidates |

The list of data repositories compiled for the impact section of the paper (repository list, version 2) was
considered and not used: it lists places to deposit or explore data for measuring reuse, not the resources the paper
discusses. The previous inventory of this work (FAIR_tox, audit of 2 Oct 2026) was not used for selection; its
first-release years, DOIs, FAIRsharing records and relations were used as evidence to be verified.

## 3. Inclusion criteria

A candidate is included when all of these hold:

- **I1** It is a resource, not an organisation, project, community, event or publication.
- **I2** It is named and identifiable: it has a homepage or a DOI.
- **I3** It is or was publicly available. Discontinued resources are kept and marked as discontinued.
- **I4** Its use in toxicology is documented: it is named in the manuscript in a toxicology context, or it is a
  member of the FAIRsharing Toxicology collection.
- **I5** It makes data or metadata findable, accessible, interoperable or reusable.

## 4. Exclusion reasons

Each excluded row carries exactly one code.

| Code | Reason | Examples from the manuscript |
|---|---|---|
| E1 | Organisation, project, initiative, consortium, community or event. Its named product is listed as its own row. | PARC, EU-ToxRisk, eNanoMapper (the project), NanoCommons (the project), OpenRiskNet, eTRANSAFE, FAIRplus, the FAIR AOP Cluster |
| E2 | Principle, framework or concept without a reusable artefact, or a publication only. | The FAIR principles (shown as the 2016 line in the figure), the AOP framework, IATA |
| E3 | Unnamed or not identifiable. | Services or pipelines mentioned in passing without a name |
| E4 | Never publicly available. | A resource that cannot be found online and has no archived release |
| E5 | No documented use in toxicology. | A generic resource named only outside a toxicology context |
| E6 | Duplicate, version or component of another row; that row is named in Covered by. | An alternative name or a version without its own identity |
| E7 | Outside chemical toxicology. | Toxinology or clinical adverse-event grading resources |
| E8 | Test method or guideline that standardises an experiment rather than data or metadata. | An OECD test guideline that describes how to run an assay |

## 5. Rules for borderline cases

- **Project and product.** The project is excluded (E1); each named product is judged on its own (for example the
  eNanoMapper ontology and database, the NanoCommons Knowledge Base, AOPLink from OpenRiskNet).
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
- **Phase.** A toxicology resource's lifecycle phase is its main intended use in toxicology, whatever its type and
  whoever made it: Data Generation (generating, recording or describing experimental data), Data Integration
  (combining, curating, linking, modelling or analysing data and knowledge) or Application (Regulatory Use)
  (preparing, submitting, assessing or publishing data for regulatory decisions).
- **Creator types.** Who created a toxicology resource is recorded separately as one or more creator types: wet-lab
  research, in silico research and regulator. A resource made by a consortium gets all types that apply; the
  organisations are named in Creator.
- **Building on FAIR** is derived, not chosen: a toxicology resource builds on FAIR when it was first published in
  2016 or later and implements, extends, profiles or recommends a generic resource, such as a toxicology FAIR Implementation Profile building on the FIP.
- **Lanes.** The dashboard places Generic resources in Generic infrastructure, Life Sciences resources in Life Sciences
  infrastructure, and toxicology resources in the lane of their phase (Data Generation, Tools & Integration,
  Application (regulatory)), which together form the toxicology infrastructure. The toxicology lanes can also be
  arranged by creator type, with one lane for resources made jointly.
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
  related_to. Each relation records its evidence: the manuscript, FAIRsharing, the literature, or a curator.

## 7. Process

1. **Extraction.** Two independent passes listed every named entity in the manuscript draft, including entities that
   were then excluded, so that the counts are complete. The passes were reconciled, every row's line references,
   manuscript status and classification were checked against the text, and a final sweep looked for missed names.
2. **FAIRsharing.** The collection members were added. A member is matched to a manuscript row only through a
   recorded FAIRsharing record; homepage and name matches are proposed for a curator to confirm.
3. **Evidence.** Dates, homepages, descriptions and FAIRsharing records were researched for every included or
   undecided row, each with its source, and checked by a second pass. This research, the screening and classification
   proposals and the relation checks were drafted with an AI-assisted workflow (Claude Opus 5.5, Anthropic) and remain
   proposals until a curator confirms them. `data/changes.csv` records each change with its process (research,
   verification, relation check, phase proposal, review, migration) and source.
4. **Curation.** Co-authors review every row in the curation Sheet. Disagreements are discussed and settled by the
   corresponding authors; the outcome and the reviewer's initials are recorded in the row and in `data/changes.csv`.
5. **Release.** A version is released when `fairtox validate --strict` passes. The dashboard shows the selection
   flow (candidates per source, excluded per reason, undecided, included), computed from the dataset.

## 8. Decision record

| Date | Decision | By |
|---|---|---|
| 2 Oct 2026 | A resource's lane follows where it comes from; guidance made by regulators belongs to Application. | Jente Houweling |
| 3 Oct 2026 | Relations use FAIRsharing's relation labels only, so that every relation can be entered in FAIRsharing. | Jente Houweling |
| 5 Oct 2026 | FERs only, not initiatives. The phase of a toxicology resource follows the stakeholder who created it. Sub-domains are those of the manuscript; a resource can have several. Toxicology building on FAIR is a scope of its own. | Jente Houweling |
| 5 Oct 2026 | Alignment with the PARC Toxicology and Reference AOP FAIR Implementation Profiles follows after the first curated version. | Jente Houweling |
| 5 Oct 2026 | The phase of a toxicology resource is its main intended use, chosen directly; who made it is recorded separately as one or more creator types (wet-lab research, in silico research, regulator), so both can be plotted. "Toxicology building on FAIR" is no longer a scope: it is derived from a builds-on relation to a FAIR resource, and those resources sit in the toxicology lanes. This replaces the earlier rule that the creator sets the phase. | Jente Houweling |
| 5 Oct 2026 | Scope and lane FAIR are renamed Generic (generic infrastructure): several of these resources (RDF, OWL, SPARQL, nanopublications, FAIRsharing as BioSharing) predate the FAIR principles, so calling them FAIR was anachronistic. For the same reason a toxicology resource counts as building on FAIR only when first published in 2016 or later. | Jente Houweling |

## 9. Limitations

- The manuscript is a draft; line references refer to the frozen version, and later drafts may name other resources
  (`fairtox draft-check` reports the differences).
- The FAIRsharing collection is curated by its maintainers and changes over time; the retrieval date is recorded.
- First-publication dates depend on what is documented; some can only be bounded.
- Choosing a phase by main use is a judgement for resources with several uses, and creator types depend on what
  is documented about the makers; both are recorded per resource so they can be checked and revised.