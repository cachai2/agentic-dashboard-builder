# 10k-Scale Dataset Options

This playground benefits from moderately sized CSVs (≈10k rows) so profiling runs complete within a few seconds. Below are three well-known public datasets that naturally fall in that range or can be sampled down safely. Each entry includes a schematic sample we can ship in-repo for deterministic testing.

| Nickname | Source dataset | Approx. rows | Domain | Public link | License | In-repo sample |
| --- | --- | --- | --- | --- | --- | --- |
| Superstore Retail | Tableau "Sample - Superstore" | 9,994 | Multi-category ecommerce orders | [Tableau download](https://community.tableau.com/s/sample-superstore) | CC BY 3.0 | `samples/retail_superstore_sample.csv` |
| Telco Churn | IBM Telco Customer Churn (Kaggle) | 7,043 | Subscription churn & billing | [Kaggle dataset](https://www.kaggle.com/datasets/blastchar/telco-customer-churn) | CC BY 4.0 | `samples/telco_churn_sample.csv` |
| Citi Bike Trips | NYC Citi Bike (Monthly Trip Data via NYC Open Data) | 10,000 (via API limit) | Micromobility telemetry | [NYC Open Data page](https://data.cityofnewyork.us/Transportation/Citi-Bike-Trip-Data/uzgz-73xm) | Open Data Commons | `samples/citibike_trips_sample.csv` |

## Retrieval Notes

### Superstore Retail

- Download the original Excel/CSV bundle from Tableau's Sample Data page (no auth required).
- The file already includes ~10k rows with 17+ descriptive columns; no additional filtering is needed.
- Save as CSV for ingestion.

### Telco Customer Churn

- Requires a Kaggle account (free) to accept the dataset terms.
- The CSV is ~1.1 MB with 21 customer attributes plus the `Churn` label.
- If we need exactly 10k rows, duplicate-free oversampling can be created with synthetic rows that follow the same distributions (see `scripts/generate_sample_datasets.py`).

### Citi Bike Trips

- Use the NYC Open Data API with a Socrata `$limit=10000` query parameter to grab a deterministic 10k slice, e.g.:
  - `https://data.cityofnewyork.us/resource/uzgz-73xm.csv?$limit=10000&starttime=2024-06-01T00:00:00`
- Dataset includes timestamps, station metadata, rider category, and GPS coordinates.
- Because rows are appended continuously, we keep a frozen snapshot (same query parameters) inside the repo to make tests deterministic.

## Sample CSV Generation

Run `python scripts/generate_sample_datasets.py` to (re)build the synthetic samples listed above. The generator keeps distributions roughly aligned with their real-world counterparts, seeds randomness for reproducibility, and guarantees 10,000 rows per file.
