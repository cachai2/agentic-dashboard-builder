import json
from pathlib import Path

import pytest

from app.validator import PlanValidator

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_validator_accepts_valid_plan():
    validator = PlanValidator()
    plan_text = (SAMPLES / "mock_plan.json").read_text()
    parsed = validator.parse_and_validate(plan_text)
    assert parsed["sections"], "Expect sections to pass schema"


def test_validator_rejects_invalid_plan():
    validator = PlanValidator()
    invalid_plan = json.dumps({"title": "Missing sections"})
    with pytest.raises(Exception):
        validator.parse_and_validate(invalid_plan)
