# Sample Datasets

Synthetic datasets curated for manual and automated testing. Everything is in CSV format so you can drop files directly into the pipeline while still exercising different business scenarios and schema shapes.

| File | Format | Primary fields | Intended checks |
| ---- | ------ | -------------- | --------------- |
| `Climate-dataset.csv` | CSV | `Date`, `City`, `AverageTempC`, `PrecipitationMm`, `WindSpeedKph`, `AirQualityIndex` | Verifies multi-city climate metrics, numeric aggregation, and date parsing. |
| `Retail-sales.csv` | CSV | Transaction-level fields plus exploded `item_skus`, `item_categories`, and `total_items` counts | Exercises nested data flattening, currency totals, and segment analysis. |
| `business-insights-sample.csv` | CSV | `quarter`, `net_revenue`, `support_tickets`, `customer_count` | Guaranteed to trigger the inline dashboard charts (revenue, support backlog, retention) during demos. |
| `Healthcare-admissions.csv` | CSV | Department-level wait times, occupancy, readmission percentages | Tests healthcare metrics, percentage handling, and multi-hospital comparisons. |
| `Transportation-routes.csv` | CSV | Route metadata (`mode`, `origin`, `avg_ridership`, etc.) | Validates transportation KPI profiling and categorical dimensions. |

Feel free to copy these into storage or run them through the MCP shell-based wrangling pipeline to sanity check format support.

## Dashboard compatibility checklist

To light up the in-app charts, your dataset should include:

- A time period column containing quarter, month, date, timestamp, or year information (e.g. `quarter`, `month`, `timestamp`, `start_year`).
- At least one numeric revenue-like column (`revenue`, `sales`, `total_amount`, `allocated_budget`, etc.).
- Optional extras for richer visuals:
  - A backlog/volume column for support (`support_tickets`, `open_cases`, `case_backlog`).
  - A retention/customer count column (`customer_count`, `active_customers`, `households_impacted`).

Run `business-insights-sample.csv` through the workflow to confirm everything is wired correctly, then align your own dataset column names to the same conventions for inline dashboards.
