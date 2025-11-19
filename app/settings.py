from functools import lru_cache
from pydantic import BaseSettings

class Settings(BaseSettings):
    app_name: str = "ignite-autodash"
    max_profile_rows: int = 100_000
    sample_rows: int = 50_000
    enable_mock_planner: bool = True
    dashboard_plan_schema_path: str = "schemas/dashboard_plan.schema.json"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
