"""Dataset-specific preprocessor registry."""

from .base import (
    DatasetPreprocessor,
    get_preprocessor,
    list_preprocessors,
    register_preprocessor,
)

# Import dataset modules so they self-register with the global registry.
from . import preprocessor as _preprocessor  # noqa: F401

__all__ = [
    "DatasetPreprocessor",
    "get_preprocessor",
    "list_preprocessors",
    "register_preprocessor",
]
