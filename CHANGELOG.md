# Changelog

## Unreleased

- Terms: every field in the graph is a schema.org term (written `http://schema.org/`), else a DCAT term, and a FIP
  ontology term for FSR types and FIP declarations; the dataset defines no properties of its own. Controlled values
  are IRIs of established concepts where one exists (FAIRsharing's subject terms, the IUPAC Gold Book, MeSH, NCIT, EFO,
  SIO, Wikidata, and the ADMS and EU status lists). The 11 values without one are defined terms of the dataset in `terms.ttl`,
  each linked to its closest outside concepts. Derived and curation fields stay out of the graph.
- CDIF: the published dataset conforms to CODATA's CDIF Discovery profile 1.1, checked in CI with CODATA's SHACL
  rules, and its term lists to the CDIF Concept Scheme profile 1.1. The dataset states its identifier, landing page,
  release date, temporal coverage, sources, fields with their terms, and downloads with checksums; its creator, and the
  maintainer of its catalog record, is the ELIXIR Toxicology Community within ELIXIR (ROR), its licence a labelled link
  and its keywords defined terms.
- Resources: each states its persistent identifier, written in full (the context sets no `@base`), and homepage and
  has a schema.org type. The creator types (`creatorType`, formerly `stakeholders`) are qualified attributions
  (`prov:qualifiedAttribution` with `dcat:hadRole`); the FAIRsharing type is `fairsharingType` (formerly `type`); the
  IRIs under which the FIPs declare a resource are `schema:sameAs`. Dates are stored under the
  property of what they refer to, after DataCite's date types; the date source is `schema:citation`. An unknown
  maintenance status is not published.
- Curation sheet: the Type column is now FAIRsharing type, a computed Identifier column is added, each header note
  names the column's term, and Lane, Warnings and Row version are folded.
- The FIP convergence table (`fip --report`) is written to `build/` and no longer kept in the repository.
- Dashboard: the data dictionary shows each field's term and has an anchor for each term of the dataset. The published
  credit names the nanopublications of the two FIPs.

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
- FAIRsharing records and the FIP ontology are read when the dashboard and the sheet are built; the dataset stores
  only what is curated.
- The JSON-LD uses schema.org, DCTERMS, DCAT, SKOS, PAV and the FIP ontology. The 14 own terms are published as
  `terms.ttl`, `terms.jsonld` and `context.jsonld`, for `https://w3id.org/fair-tox/`.
- Dashboard: a Class filter, a FIP declarations switch and filter, toxicology lanes by phase or by creator, and links
  that open a resource or a term from the URL fragment.
- Curation sheet: FSR type, Class and span columns, and the FIP declarations as read-only rows.
- Docs: the inclusion criteria, the data dictionary and a FIP convergence table (`docs/fip-convergence.md`).
- Robustness: reads from FAIRsharing, the nanopublication services and the FIP ontology retry busy servers and failed
  connections, and CI runs `fairtox validate --strict`, so a release has no warnings.
- The FAIRsharing export proposes only what FAIRsharing would accept and the curators have checked, in the shapes of
  its API, and lists everything else with the reason it is held back.
- Removed: the dashboard's internal curation view, as curation is done in the sheet, and the `draft-check` command.

## 0.1.0 (2026-10-05)

First curated version: the resources named in the manuscript and the FAIRsharing Toxicology collection, with first
publication dates, FAIRsharing types, phases, sub-domains and relations, and the dashboard.
