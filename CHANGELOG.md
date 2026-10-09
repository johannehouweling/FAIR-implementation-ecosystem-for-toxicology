# Changelog

## 0.2.0 (2026-10-09)

- FAIR Implementation Profiles: the declarations of the PARC Toxicology FIP and the Reference AOP FIP are read from
  their nanopublications, through each FIP's declaration index, when the dashboard and the curation sheet are built.
  The 36 resources they declare that were not yet in the dataset are added as undecided rows for screening.
- Types: every resource has one FAIR Supporting Resource type from the FIP ontology, chosen by the kind of resource
  after the type a FIP gives it; databases are registries. A resource is a FAIR-Enabling Resource or another FAIR
  Supporting Resource, and FAIR principles come only from the FIP questions it is declared for.
- Phases: Data generation, Data integration and Regulatory assessment, defined by the data life cycle. A toxicology
  resource takes the earliest phase it acts on, and every phase it acts on is recorded as its span.
- FAIR Implementation Communities are kept only when a FIC nanopublication identifies them, and are listed but not
  drawn.
- FAIRsharing records are read when the dashboard and the sheet are built; the dataset stores only what is curated.
- The JSON-LD uses schema.org, DCTERMS, DCAT, SKOS, PAV and the FIP ontology. The 14 own terms are published as
  `terms.ttl`, `terms.jsonld` and `context.jsonld`, for `https://w3id.org/fair-tox/`.
- Dashboard: a Class filter, a FIP declarations switch and filter, toxicology lanes by phase or by creator, and links
  that open a resource or a term from the URL fragment.
- Curation sheet: FSR type, Class and span columns, and the FIP declarations as read-only rows.
- Docs: the inclusion criteria, the data dictionary and a FIP convergence table (`docs/fip-convergence.md`).

## 0.1.0 (2026-10-05)

First curated version: the resources named in the manuscript and the FAIRsharing Toxicology collection, with first
publication dates, FAIRsharing types, phases, sub-domains and relations, and the dashboard.
