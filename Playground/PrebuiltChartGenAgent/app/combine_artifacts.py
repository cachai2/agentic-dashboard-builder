"""Utilities for consolidating chart artifacts into a single HTML dashboard."""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Combine individual HTML artifacts into a single index page.")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("artifacts"),
        help="Directory containing chart artifacts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts") / "all_artifacts.html",
        help="Path for the combined HTML page.",
    )
    parser.add_argument(
        "--title",
        default="Chart Artifact Index",
        help="Title to display at the top of the consolidated page.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts_dir: Path = args.artifacts_dir
    output_path: Path = args.output

    if not artifacts_dir.exists():
        raise FileNotFoundError(f"Artifacts directory '{artifacts_dir}' does not exist.")

    html_files = sorted(_iter_html_files(artifacts_dir))
    if not html_files:
        raise FileNotFoundError(f"No HTML artifacts were found in '{artifacts_dir}'.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = _render_document(html_files, output_path, title=args.title)
    output_path.write_text(document, encoding="utf-8")
    print(f"Combined {len(html_files)} artifacts into {output_path}")


def _iter_html_files(artifacts_dir: Path) -> Iterable[Path]:
    for path in artifacts_dir.glob("*.html"):
        yield path


def _render_document(html_files: list[Path], output_path: Path, *, title: str) -> str:
    sections = []
    for path in html_files:
        if path.resolve() == output_path.resolve():
            continue  # don't iframe the output file itself
        rel_path = path.name
        section_title = escape(path.stem.replace("_", " ").title())
        sections.append(
            f"<section id='{escape(path.stem)}'>\n"
            f"  <header><h2>{section_title}</h2><p>{escape(rel_path)}</p></header>\n"
            f"  <iframe src='{escape(rel_path)}' loading='lazy'></iframe>\n"
            "</section>"
        )

    if not sections:
        raise ValueError("No artifacts remain after excluding the output file itself.")

    sections_html = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f3f4f6; }}
    header.page-header {{ padding: 1.5rem; background: #111827; color: #f9fafb; }}
    header.page-header h1 {{ margin: 0; font-size: 1.5rem; }}
    main {{ padding: 1rem; display: grid; gap: 1.5rem; }}
    section {{ background: #fff; border-radius: 0.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 1rem; }}
    section header {{ margin-bottom: 0.5rem; }}
    section h2 {{ margin: 0 0 0.25rem 0; font-size: 1.2rem; }}
    iframe {{ width: 100%; height: 480px; border: 1px solid #e5e7eb; border-radius: 0.25rem; background: #fff; }}
  </style>
</head>
<body>
  <header class=\"page-header\">
    <h1>{escape(title)}</h1>
    <p>Generated from {len(sections)} artifact(s)</p>
  </header>
  <main>
    {sections_html}
  </main>
</body>
</html>
"""


if __name__ == "__main__":
    main()
