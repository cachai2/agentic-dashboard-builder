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
