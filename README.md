# FAIR implementation ecosystem for toxicology

[![CI](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/actions/workflows/ci.yml/badge.svg)](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/actions/workflows/ci.yml)
[![Data: CC BY-SA 4.0](https://img.shields.io/badge/data-CC%20BY--SA%204.0-lightgrey)](LICENSE-DATA)
[![Code: MIT](https://img.shields.io/badge/code-MIT-lightgrey)](LICENSE)

A curated dataset of the resources used in toxicology to make data and metadata findable, accessible, interoperable
and reusable, with the code to curate it and to publish its dashboard. It underlies Figure 2 of the ELIXIR Toxicology
Community paper on ten years of the FAIR principles in toxicology (in preparation). The dataset combines the
resources named in the paper, the FAIRsharing Toxicology collection and the resources declared in two toxicology
FAIR Implementation Profiles (FIPs). For each resource it records when it was first published, its FAIRsharing type,
its types in the FIP ontology, its toxicology life-cycle phase and span, its sub-domains and its relations to other
resources.

Dashboard: https://johannehouweling.github.io/FAIR-implementation-ecosystem-toxicology-timeline/

## Contents

- `data/fair-tox-ecosystem.jsonld`: the dataset (JSON-LD with schema.org, DCAT and the FIP ontology; FAIRsharing DOIs
  as identifiers).
- `data/changes.csv`: every change to a curated field or relation since the first version, with its date, process or
  curator, and source; it is published with the code.
- `docs/inclusion-criteria.md`: the rules (how resources are selected, classified, related and curated).
- `docs/data-dictionary.md`: the format (fields with their terms, and the controlled vocabularies).
- `queries/`: the SPARQL queries behind the counts of relations, hubs and resources without relations, run with
  `fairtox query` over the resources in the figure.
- `CHANGELOG.md`: what changed in each version; versions are tagged (`v0.2.0`).
- `src/fairtox/`: the `fairtox` command line tool; `tests/`: its tests.

## Data flow

The dataset stores only what is curated; FAIRsharing record data and the FIP declarations are read when the outputs are
built ([data dictionary](docs/data-dictionary.md#fields-added-at-build-time)). FAIRsharing is read with the login in
`.env` (see `.env.example`). A pull request's build, which publishes nothing, uses the last cache of any day (`FAIRSHARING_CACHE_ANY_DAY`). The FIPs are read from their nanopublications, and the FIP ontology from its IRI
(`https://w3id.org/fair/fip/terms/`), once, into `build/fip`. `--offline` reads the local caches in `build/fairsharing`
and `build/fip`, left by an earlier run, instead.

CI tests every change, runs `fairtox validate --strict`, checks the published dataset against CODATA's CDIF
Discovery profile 1.1 (its SHACL rules, with pyshacl), checks that the links in the dataset and the
documentation resolve (lychee; FAIRsharing, the Wayback Machine and the dataset's own w3id.org identifiers are left out) and, on `main`,
publishes the dashboard. Then release-please
keeps a release pull request open with the next version and its `CHANGELOG.md` entry, made from the Conventional
Commits (`feat`, `fix`, `docs`) since the last release; merging it tags the version and publishes a GitHub release.
Co-authors curate in a Google Sheet made with `fairtox sheet`; `fairtox ingest` reads it back row by row, as the
[criteria](docs/inclusion-criteria.md#7-process) describe. A freshly built sheet, once uploaded, needs "Allow multiple
selections" switched on for Sub-domains, FSR type and Phase by hand, because an .xlsx cannot carry it. A workflow
reads the sheet back three times a day, then FAIRsharing, checking each new row against it, and the FIPs, and keeps
one pull request open with what changed; it keeps the exported sheet with the run for 90 days.

## Commands

Requires [uv](https://docs.astral.sh/uv/). Run from the repository root.

```bash
uv sync
uv run fairtox validate                                        # check; --strict, used by CI, also fails on warnings
uv run --env-file .env fairtox fairsharing                     # new collection members, unchecked rows searched; --apply stores them
uv run fairtox fip                                             # FIP match report; --apply stores links and new rows
uv run --env-file .env fairtox sheet build/curation.xlsx       # curation workbook, edited as a Google Sheet
uv run fairtox ingest build/curation-sheet.xlsx                # read the sheet back row by row; --report adds a summary
uv run --env-file .env fairtox site build/site                 # dashboard, published dataset, CSV files and vocabulary
uv run --env-file .env fairtox export-fairsharing build/       # what FAIRsharing would accept; nothing is posted
uv run fairtox query queries/hubs.rq                           # a SPARQL query over the resources in the figure; CSV
```

`fairsharing`, `fip`, `sheet`, `site` and `export-fairsharing` take `--offline`; `fip --report` writes the
choices of the two FIPs per FIP question to `build/fip-convergence.md`.

## Licences

The code is licensed MIT ([LICENSE](LICENSE)). The dataset, documentation and dashboard are licensed CC BY-SA 4.0
([LICENSE-DATA](LICENSE-DATA)) because they contain information from [FAIRsharing](https://fairsharing.org), licensed
CC BY-SA 4.0. The FIP declarations come from the nanopublications of the
[PARC Toxicology FIP](https://w3id.org/np/RAKa7vUwc8qVbktDqDSpuq7lRrrKcjPKvkB4Tn7WHvr7E) and the
[Reference AOP FIP](https://w3id.org/np/RAQMnw2u-ZG_zVkVIzEdtYn3o4tYqyhsnOhiWaMLG01Bc), licensed CC0, or as stated in
each.

## How to cite

Cite the dataset with the metadata in [CITATION.cff](CITATION.cff) and credit FAIRsharing. Built by the ELIXIR
Toxicology Community.
