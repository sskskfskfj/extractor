---
name: opendart-keyword-csv
description: Download public OpenDART XBRL note archives, find companies whose VALUE rows contain both "자기주식" and "소각", rank by the closest keyword pair, and export the matching sentence per company to CSV. Use for this OpenDART keyword-to-CSV workflow; an API key is not required.
---

# OpenDART keyword proximity CSV

Use the packaged Python helper to create `opendart_dataset/` in the active workspace, download the available OpenDART bulk XBRL note ZIPs sequentially, scan each ZIP's `val.tsv`, and save a CSV containing `회사명` and `문장`.

## Workflow

1. Use the active workspace as the output root; do not write data beside the installed skill. Defaults are `opendart_dataset/` for archives and `results/keyword_proximity_bulk_2025_2026.csv` for the result.
2. Run the packaged `scripts/collect.py` with Python 3.11+ from the active workspace. It creates the data directory, reuses verified archive files, downloads any missing official ZIPs in sequence, validates each ZIP contains `val.tsv`, then starts the analysis. On a failed download it stops before producing a partial CSV; a rerun reuses completed ZIPs and retries the missing file.
3. The default report-date years are 2025 and 2026. A row matches only when its `VALUE` contains both exact Korean strings `자기주식` and `소각`.
4. Rank companies by the smallest number of characters between the nearest occurrence of the two terms in any one row. For each company, use the row establishing its smallest distance and extract the sentence in that row containing both terms.
5. Export the top 30 companies by default, with exactly two columns: `회사명`, `문장`. Set the desired company count with `--count 40`. The helper first maps CIKs through the bundled OpenDART Korean company-name snapshot, then falls back to the dataset's `EntityRegistrantName` facts. It does not call the company-code API.
6. Report the output path, number of archives and rows scanned, number of matches/exported sentences, selected years, and any missing bundle or company-name issues. Never describe the result as all OpenDART disclosures: it covers only the files scanned. A row without a sentence containing both terms is reported and omitted from the sentence CSV. If the execution environment blocks network access or cannot run the packaged script, state that clearly and provide the local command; do not simulate a completed download or substitute a generated script artifact.

## Run options

Run with Python 3.11+; the helper uses only the standard library. If using the queryEngine repository's environment, activate it first with `source .venv/bin/activate`. Resolve the helper's installed path from the active skill metadata rather than assuming a fixed home directory.

```sh
python <active-skill-path>/scripts/collect.py
```

Use already-downloaded ZIPs without network requests:

```sh
python <active-skill-path>/scripts/collect.py --no-download --data-dir opendart_dataset
```

Use a local dataset folder or a single `val.tsv`/ZIP source instead:

```sh
python /path/to/opendart-keyword-csv/scripts/collect.py --dataset /path/to/queryEngineDataset
```

Change years, top-N, paths, or keywords:

```sh
python /path/to/opendart-keyword-csv/scripts/collect.py --year 2025 --year 2026 --count 50 --output results/custom.csv
python /path/to/opendart-keyword-csv/scripts/collect.py --keyword 자기주식 --keyword 소각
```

OpenDART public XBRL bulk downloads do not require an API key. Do not request or read `.env` for this workflow. The bundled company-name snapshot is static and may become outdated; a company not in it falls back to its XBRL name or CIK. The optional OpenDART company-code API is outside this helper's required path.
