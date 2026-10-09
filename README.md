# FAIR implementation ecosystem for toxicology

[![CI](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/actions/workflows/ci.yml/badge.svg)](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/actions/workflows/ci.yml)
[![Data: CC BY-SA 4.0](https://img.shields.io/badge/data-CC%20BY--SA%204.0-lightgrey)](LICENSE-DATA)
[![Code: MIT](https://img.shields.io/badge/code-MIT-lightgrey)](LICENSE)

A curated dataset of the resources used in toxicology to make data and metadata findable, accessible, interoperable
and reusable, with the code to curate it and to publish its dashboard. It underlies Figure 2 of the ELIXIR Toxicology
Community paper on ten years of the FAIR principles in toxicology (in preparation). The dataset combines the
resources named in the manuscript, the FAIRsharing Toxicology collection and the resources declared in two toxicology
FAIR Implementation Profiles (FIPs). For each resource it records when it was first published, its FAIRsharing type,
its type in the FIP ontology, its toxicology life-cycle phase and span, its sub-domains and its relations to other
resources.

Dashboard: https://johannehouweling.github.io/FAIR-implementation-ecosystem-toxicology-timeline/

## Contents

- `data/fair-tox-ecosystem.jsonld`: the dataset (JSON-LD with schema.org, DCAT and the FIP ontology; FAIRsharing DOIs
  as identifiers).
- `data/changes.csv`: every curated change, with date, curator and source.
- `data/raw/fip/fip-ontology.trig`: the pinned FIP ontology.
- `docs/inclusion-criteria.md`: how resources were selected and classified.
- `docs/data-dictionary.md`: fields, controlled vocabularies and own terms.
- `docs/fip-convergence.md`: the choices of the two FIPs per FIP question.
- `src/fairtox/`: the `fairtox` command line tool; `tests/`: its tests.

## Data flow

The dataset stores only what is curated. FAIRsharing record data are read when the dashboard, the curation sheet or
the FAIRsharing export is built, and the FIP declarations when the dashboard or the sheet is built; both are published
with their retrieval date. FAIRsharing is read with the login in `.env` (see `.env.example`), the FIPs from their
nanopublications. `--offline` reads the local caches in `build/fairsharing` and `build/fip`, left by an earlier run,
instead.

## Commands

Requires [uv](https://docs.astral.sh/uv/). Run from the repository root.

```bash
uv sync
uv run fairtox validate                                        # check the dataset; --strict fails on warnings too
uv run --env-file .env fairtox fairsharing                     # new FAIRsharing collection members; --apply stores them
uv run fairtox fip                                             # FIP match report; --apply stores links and new rows
uv run --env-file .env fairtox sheet build/curation.xlsx       # curation workbook, edited as a Google Sheet
uv run fairtox ingest curated.xlsx                             # read the edited sheet back, checked and logged
uv run --env-file .env fairtox site build/site                 # dashboard, published dataset, CSV files and vocabulary
uv run --env-file .env fairtox site --internal build/internal  # curation view with every row; local only, never publish
uv run --env-file .env fairtox export-fairsharing build/       # what could be added to FAIRsharing; nothing is posted
uv run fairtox draft-check draft.txt                           # check manuscript line references against a later draft
```

`fairsharing`, `fip`, `sheet`, `site` and `export-fairsharing` take `--offline`; `fip --report` writes
`docs/fip-convergence.md`.

## Licences

The code is licensed MIT ([LICENSE](LICENSE)). The dataset, documentation and dashboard are licensed CC BY-SA 4.0
([LICENSE-DATA](LICENSE-DATA)) because they contain information from [FAIRsharing](https://fairsharing.org), licensed
CC BY-SA 4.0. The FIP declarations come from nanopublications licensed CC0, or as stated in each.

## How to cite

Cite the dataset with the metadata in [CITATION.cff](CITATION.cff) and credit FAIRsharing. Built by the ELIXIR
Toxicology Community.
