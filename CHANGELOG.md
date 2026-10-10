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
  IRIs under which the FIPs declare a resource are `schema:sameAs`. The FAIRsharing record of a resource carries
  FAIRsharing's subjects (`schema:about`, beside scope) and domains (`dcat:theme`, beside span), read at build time.
  The FAIRsharing Toxicology collection lists its included members (`dcat:resource`).
  Dates are stored under the
  property of what they refer to, after DataCite's date types; the date source is `schema:citation`. An unknown
  maintenance status is not published.
- Curation sheet: the Type column is now FAIRsharing type, a computed Identifier column is added, each header note
  names the column's term, Lane, Warnings and Row version are folded, and grey FAIRsharing subjects and domains
  columns sit next to Scope and Span.
- The FIP convergence table (`fip --report`) is written to `build/` and no longer kept in the repository.
- A FIP description that cites a FAIRsharing record by its legacy id (`bsg-…`) is resolved to the record, whose
  FAIRsharing entry lists its legacy ids.
- Dashboard: the data dictionary shows each field's term and has an anchor for each term of the dataset. The published
  credit names the nanopublications of the two FIPs.

## [0.3.0](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/compare/v0.2.0...v0.3.0) (2026-10-10)


### Features

* **fairsharing:** inherit FAIRsharing's subjects, domains and collection members ([ab8b97e](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/ab8b97ed803ab63d56e991caf2080bfd91704908)), closes [#5](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/issues/5)
* **terms:** bind every field to a published term and conform to CDIF Discovery 1.1 ([3f359c7](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/3f359c773c5e3536b375fa218548cdcfa24d6d5b))
* **terms:** conform to the CDIF Discovery profile 1.1 and reuse more concepts ([fab2e61](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/fab2e6169d043002d71f6330d5788d7b411a538a)), closes [#5](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/issues/5)
* **terms:** define in vitro and regulatory toxicology from published sources ([b9447f3](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/b9447f3036c38a154a38df7ec19f9404a1a99f89)), closes [#5](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/issues/5)
* **terms:** describe each published field and reuse Wikidata for in vitro toxicology ([4ee5b1a](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/4ee5b1ac4db55b782c14d610ae9d0bce17cf1198)), closes [#5](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/issues/5)
* **terms:** map every field to schema.org, DCAT or FIP ontology terms ([d253626](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/d2536263eda2f245d59c40a703d28862b0d56b80)), closes [#5](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/issues/5)
* **terms:** publish creator types as schema:creator and fold technical sheet columns ([6cfa3c5](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/6cfa3c520cbef5642e0dbc6b914a6f0d7043373e)), closes [#5](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/issues/5)


### Fixes

* **fip:** resolve FAIRsharing legacy ids and confirm the FIP-linked records ([d91b492](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/d91b492b951314a93e85d92b9d1872fd557fdae0)), closes [#5](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/issues/5)
* **sheet:** let a row read back from the sheet be edited there again ([6de9528](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/6de952869a16eb41f3fb7c6a98bdfdc72f928812))
* **terms:** absolute identifiers, qualified attributions and FAIRsharing types ([f484505](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/f48450583907cf235d7a6e266ddd0d6c80f00ba3))
* **terms:** absolute identifiers, qualified attributions and sameAs links ([be9c166](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/be9c1665b36cd03fc5d2f5b25ad71ddc00d8a1e0)), closes [#5](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/issues/5)


### Documentation

* **readme:** describe CI, the weekly refresh and the curation sheet ([e760e13](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/e760e13fd05db177ce83d6283f52ea33d63361ce))
* **readme:** describe CI, the weekly refresh and the curation sheet ([0f81840](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/commit/0f81840cb19f65da3793c075cc54b745af86d976))

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
