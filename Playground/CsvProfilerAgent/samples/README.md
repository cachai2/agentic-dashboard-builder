# Sample CSV Inventory

The profiling sandbox ships with deterministic synthetic datasets so we can benchmark dtype inference and distribution stats without fetching external files.

| File | Rows | Mirrors | Notes |
| --- | --- | --- | --- |
| `retail_superstore_sample.csv` | 10,000 | Tableau Sample Superstore | Retail orders with geographic + merchandising context. |
| `telco_churn_sample.csv` | 10,000 | IBM Telco Customer Churn | Subscription billing funnel with binary churn target. |
| `citibike_trips_sample.csv` | 10,000 | NYC Citi Bike Trip Data | Micromobility telemetry with timestamps + GPS. |

Regenerate the CSVs anytime with:

```powershell
python scripts/generate_sample_datasets.py
```

The generator seeds Python's PRNG (`random.Random(42)`) so repeating the command yields byte-identical outputs.
