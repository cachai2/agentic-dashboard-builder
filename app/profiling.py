import pandas as pd

def generate_profile_summary(df: pd.DataFrame) -> dict:
    """Basic profiling for MVP. Returns schema + row count.
    Later: add correlations, distributions, outlier markers, role inference.
    """
    schema = []
    for col in df.columns:
        s = df[col]
        schema.append({
            "name": col,
            "dtype": str(s.dtype),
            "non_null_count": int(s.notna().sum()),
            "null_ratio": float(s.isna().mean()),
            "unique_values": int(s.nunique()),
            "example_values": [str(v) for v in s.dropna().unique()[:5]]
        })
    return {
        "row_count": len(df),
        "schema": schema
    }
