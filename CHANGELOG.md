# Changelog

## Unreleased

- Terms: every field in the graph is a schema.org term, else a DCAT term, and the FIP ontology's for FSR types and
  FIP declarations; the dataset defines no properties of its own. Controlled values are IRIs: outside concepts where
  one exists (FAIRsharing's subject terms for the scopes, MeSH and NCIT for four sub-domains, ADMS for in development),
  else 19 defined terms of the dataset (`schema:DefinedTerm` and `skos:Concept`) in `terms.ttl`. Phases and creator
  types are DCAT themes. Derived and curation fields stay out of the graph: the context has no `@vocab`.
- Dates are stored under the property of what they refer to: `datePublished`, `dateReleased` (`dct:issued`),
  `dateAdopted` (`dct:dateAccepted`), `dateCreated`, or `date` when no basis is recorded. The curation sheet keeps
  First published and Date basis.
- Each resource states its persistent identifier (`identifier`) and homepage (`url`). The curation sheet shows the
  identifier, its Type column is now FAIRsharing type, and each header note names the column's term.
- The dashboard's data dictionary shows each field's term and has an anchor for each term of the dataset; the
  published credit names the nanopublications of the two FIPs.

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
