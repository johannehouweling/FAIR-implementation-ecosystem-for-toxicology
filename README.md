# FAIR implementation ecosystem for toxicology

[![CI](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/actions/workflows/ci.yml/badge.svg)](https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology/actions/workflows/ci.yml)
[![Data: CC BY-SA 4.0](https://img.shields.io/badge/data-CC%20BY--SA%204.0-lightgrey)](LICENSE-DATA)
[![Code: MIT](https://img.shields.io/badge/code-MIT-lightgrey)](LICENSE)

A curated dataset of FAIR-enabling resources used in toxicology, with the code to curate it and to publish its
dashboard. It underlies Figure 2 of the ELIXIR Toxicology Community paper on ten years of the FAIR principles in
toxicology (in preparation). The dataset combines the resources named in the manuscript with the FAIRsharing
Toxicology collection. For each resource it records when it was first published, its FAIRsharing type, its toxicology
lifecycle phase, its sub-domains and its relations to other resources.

Dashboard: https://johannehouweling.github.io/FAIR-implementation-ecosystem-for-toxicology/

## Contents

- `data/fair-tox-ecosystem.jsonld`: the dataset (JSON-LD with schema.org and DCAT; FAIRsharing DOIs as identifiers).
- `data/changes.csv`: every curated change, with date, curator and source.
- `docs/inclusion-criteria.md`: how resources were selected.
- `docs/data-dictionary.md`: fields and controlled vocabularies.
- `src/fairtox/`: the `fairtox` command line tool; `tests/`: its tests.

## Reproduce

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run fairtox validate
uv run fairtox site build/site                 # the dashboard
uv run --env-file .env fairtox fetch           # refresh from FAIRsharing; login in .env (see .env.example)
```

## Curation

`uv run fairtox sheet build/curation.xlsx` writes a workbook with drop-down lists that co-authors edit as a Google
Sheet. The edited sheet, downloaded as .xlsx, is read back with `uv run fairtox ingest <file>.xlsx`, which checks
every cell and logs each change. `uv run fairtox export-fairsharing build/` lists what could be registered in
FAIRsharing; nothing is submitted automatically.

## Citation and licences

Cite this work with the metadata in [CITATION.cff](CITATION.cff). The dataset, documentation and dashboard are
licensed CC BY-SA 4.0 because they contain FAIRsharing data; the code is licensed MIT.

## Acknowledgements

Contains information from [FAIRsharing](https://fairsharing.org), licensed CC BY-SA 4.0. Built by the
ELIXIR Toxicology Community.
