# User Prompt Template

Profile summary JSON:

```json
{profile_summary}
```

Return only the JSON body of a DashboardPlan captured under a root object:

```json
{
  "title": string,
  "description": string,
  "sections": [
    {
      "title": string,
      "charts": [
        {
          "id": string,
          "type": string,
          "query": {...},
          "insight": string
        }
      ]
    }
  ]
}
```

If `llm_annotations` is present inside `profile_summary`, fold it directly into the plan:

- Promote the strongest `kpis` into a KPI grid or headline cards (carry over labels/units).
- Mirror the `retention_funnel.stages` order for any funnel chart and reference the underlying dataset columns mentioned in each stage definition (PhoneService, InternetService, add-on counts, target label, etc.).
- Use `loyalty_hint.columns` for scatter plots (MonthlyCharges vs TotalCharges sized by tenure, colored by the detected target) and cite the churn lift metrics in the `insight` text.
- Turn `segments`/`driver_candidates` into grouped comparisons or heatmaps that emphasize the largest churn deltas across features like Contract, InternetService, TechSupport, and tenure_band.
