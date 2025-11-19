"""Agent-friendly CLI for running dataset preprocessors."""

from __future__ import annotations

from pathlib import Path

import typer

from app.preprocessors import get_preprocessor, list_preprocessors

app = typer.Typer(help="Run registered dataset preprocessors.")


def _choices() -> list[str]:
    return [proc.name for proc in list_preprocessors()]


def _validate_dataset(dataset: str) -> str:
    choices = _choices()
    if dataset not in choices:
        raise typer.BadParameter(f"Dataset must be one of: {', '.join(choices)}")
    return dataset


@app.command()
def run(
    dataset: str = typer.Option(..., callback=_validate_dataset, help="Dataset key to preprocess."),
    input: Path | None = typer.Option(None, exists=False, help="Raw dataset path (defaults per dataset)."),
    output: Path | None = typer.Option(None, help="Destination for cleaned dataset."),
) -> None:
    preprocessor = get_preprocessor(dataset)
    destination = preprocessor.run(input_path=input, output_path=output)
    typer.echo(f"[{dataset}] wrote cleaned dataset to {destination}")


if __name__ == "__main__":  # pragma: no cover
    app()
