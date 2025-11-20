"""Generic CLI for running dataset-specific preprocessing pipelines."""

from __future__ import annotations

import argparse
from pathlib import Path

from .preprocessors import DatasetPreprocessor, get_preprocessor, list_preprocessors


def _parse_args() -> argparse.Namespace:
    processors = list_preprocessors()
    choices = [processor.name for processor in processors]
    parser = argparse.ArgumentParser(description="Run data preprocessing for supported datasets.")
    parser.add_argument(
        "--dataset",
        required=True,
        choices=choices,
        help="Dataset key to preprocess (choices: %(choices)s)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to the raw dataset (default depends on dataset)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination for the cleaned dataset (default depends on dataset)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    preprocessor = get_preprocessor(args.dataset)
    output_path = preprocessor.run(input_path=args.input, output_path=args.output)
    print(f"[{preprocessor.name}] wrote cleaned dataset to {output_path}")


if __name__ == "__main__":
    main()
