"""Batch profile multiple CSV datasets and persist the JSON outputs."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.profiling import profile_csv_path

DEFAULT_DATASETS = [
    "samples/retail_superstore_sample.csv",
    "samples/telco_churn_sample.csv",
    "samples/citibike_trips_sample.csv",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=DEFAULT_DATASETS,
        help="CSV paths to profile (defaults to in-repo samples)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to write output-<dataset>.json files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    for csv_path in args.inputs:
        profile = profile_csv_path(csv_path)
        payload = {
            "timestamp": timestamp,
            "dataset": csv_path,
            "profile": profile.model_dump(mode="json"),
        }
        stem = Path(csv_path).stem
        out_file = output_dir / f"output-{stem}.json"
        out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
