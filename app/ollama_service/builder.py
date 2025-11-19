"""Prompt construction helpers for the Ollama planner."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from .config import get_settings


def compute_prompt_hash(system_prompt: str, user_prompt: str, prompt_version: str) -> str:
    """Create a deterministic hash to identify the prompt bundle."""
    return hashlib.sha256((system_prompt + user_prompt + prompt_version).encode("utf-8")).hexdigest()


def _load_prompt_assets() -> Dict[str, str]:
    settings = get_settings()
    system_path = settings.prompt_dir / "system_v1.md"
    user_template_path = settings.prompt_dir / "user_template.md"

    with system_path.open("r", encoding="utf-8") as system_file:
        system = system_file.read().strip()
    with user_template_path.open("r", encoding="utf-8") as user_file:
        user_template = user_file.read().strip()

    return {"system": system, "user_template": user_template}


def render_prompt(profile_summary: Dict[str, Any], prompt_version: str = "v1") -> Dict[str, str]:
    assets = _load_prompt_assets()
    profile_json = json.dumps(profile_summary, separators=(",", ":"))
    user = assets["user_template"].replace("{profile_summary}", profile_json)
    prompt_hash = compute_prompt_hash(assets["system"], user, prompt_version)
    return {
        "system": assets["system"],
        "user": user,
        "prompt_version": prompt_version,
        "prompt_hash": prompt_hash,
    }
