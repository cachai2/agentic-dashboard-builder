"""Generate reproducible ~10k-row CSV samples for profiling tests."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from random import Random
from typing import Iterable, Iterator

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"
ROW_COUNT = 10_000
RNG = Random(42)


@dataclass(frozen=True)
class Station:
    name: str
    lat: float
    lng: float


SUPPLIER_COUNTRIES = [
    ("United States", "West", ["California", "Washington", "Colorado", "New York"]),
    ("United Kingdom", "EMEA", ["England", "Scotland", "Wales"]),
    ("Canada", "Canada", ["Ontario", "Quebec", "Alberta"]),
]
SHIP_MODES = ["Second Class", "Standard Class", "First Class", "Same Day"]
SEGMENTS = ["Consumer", "Corporate", "Home Office"]
CATEGORIES = {
    "Furniture": ["Chairs", "Bookcases", "Tables"],
    "Office Supplies": ["Binders", "Appliances", "Paper", "Storage"],
    "Technology": ["Phones", "Accessories", "Copiers", "Machines"],
}

TELCO_PAYMENT = [
    "Electronic check",
    "Mailed check",
    "Bank transfer (automatic)",
    "Credit card (automatic)",
]
TELCO_CONTRACTS = ["Month-to-month", "One year", "Two year"]
TELCO_SERVICES = ["DSL", "Fiber optic", "No"]

STATIONS = [
    Station("Pershing Square N", 40.751873, -73.977706),
    Station("Broadway & E 22 St", 40.740343, -73.989551),
    Station("W 52 St & 5 Ave", 40.758491, -73.978664),
    Station("Lafayette St & E 8 St", 40.730206, -73.99126),
    Station("Bond St & Schermerhorn St", 40.688417, -73.984764),
    Station("Metropolitan Ave & Meeker Ave", 40.714133, -73.951583),
]
BIKE_TYPES = ["classic_bike", "electric_bike"]
MEMBERSHIP = ["member", "casual"]


def write_csv(path: Path, fieldnames: Iterable[str], rows: Iterator[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_superstore_rows() -> Iterator[dict[str, object]]:
    start_date = datetime(2023, 1, 1)
    for idx in range(ROW_COUNT):
        country, region, states = RNG.choice(SUPPLIER_COUNTRIES)
        state = RNG.choice(states)
        city = f"City-{RNG.randint(1, 1200)}"
        postal_code = f"{RNG.randint(10000, 99999)}"
        order_date = start_date + timedelta(days=RNG.randint(0, 364))
        ship_delay = RNG.randint(1, 7)
        ship_date = order_date + timedelta(days=ship_delay)
        category = RNG.choice(list(CATEGORIES))
        sub_category = RNG.choice(CATEGORIES[category])
        segment = RNG.choice(SEGMENTS)
        ship_mode = RNG.choice(SHIP_MODES)
        quantity = RNG.randint(1, 10)
        unit_price = round(RNG.uniform(5.0, 500.0), 2)
        discount = RNG.choice([0, 0, 0, 0.1, 0.2, 0.3])
        sales = round(quantity * unit_price * (1 - discount), 2)
        profit = round(sales * RNG.uniform(-0.1, 0.35), 2)
        yield {
            "Order ID": f"CA-{order_date.year}-{idx:05d}",
            "Order Date": order_date.strftime("%Y-%m-%d"),
            "Ship Date": ship_date.strftime("%Y-%m-%d"),
            "Ship Mode": ship_mode,
            "Customer ID": f"CUST-{RNG.randint(1000, 9999)}",
            "Segment": segment,
            "Country": country,
            "City": city,
            "State": state,
            "Postal Code": postal_code,
            "Region": region,
            "Category": category,
            "Sub-Category": sub_category,
            "Product ID": f"PROD-{RNG.randint(10000, 99999)}",
            "Sales": f"{sales:.2f}",
            "Quantity": quantity,
            "Discount": f"{discount:.2f}",
            "Profit": f"{profit:.2f}",
        }


def generate_telco_rows() -> Iterator[dict[str, object]]:
    for idx in range(ROW_COUNT):
        tenure = RNG.randint(0, 72)
        monthly = round(RNG.uniform(18.0, 120.0), 2)
        total = round(max(1, tenure) * monthly + RNG.uniform(-20.0, 60.0), 2)
        churn = RNG.choices(["Yes", "No"], weights=[0.26, 0.74])[0]
        yield {
            "customerID": f"{idx:04d}-{RNG.randint(1000, 9999)}",
            "gender": RNG.choice(["Male", "Female"]),
            "SeniorCitizen": RNG.choice([0, 1]),
            "Partner": RNG.choice(["Yes", "No"]),
            "Dependents": RNG.choice(["Yes", "No"]),
            "tenure": tenure,
            "PhoneService": RNG.choice(["Yes", "No"]),
            "MultipleLines": RNG.choice(["Yes", "No", "No phone service"]),
            "InternetService": RNG.choice(TELCO_SERVICES),
            "OnlineSecurity": RNG.choice(["Yes", "No", "No internet service"]),
            "OnlineBackup": RNG.choice(["Yes", "No", "No internet service"]),
            "DeviceProtection": RNG.choice(["Yes", "No", "No internet service"]),
            "TechSupport": RNG.choice(["Yes", "No", "No internet service"]),
            "StreamingTV": RNG.choice(["Yes", "No", "No internet service"]),
            "StreamingMovies": RNG.choice(["Yes", "No", "No internet service"]),
            "Contract": RNG.choice(TELCO_CONTRACTS),
            "PaperlessBilling": RNG.choice(["Yes", "No"]),
            "PaymentMethod": RNG.choice(TELCO_PAYMENT),
            "MonthlyCharges": f"{monthly:.2f}",
            "TotalCharges": f"{total:.2f}",
            "Churn": churn,
        }


def generate_bike_rows() -> Iterator[dict[str, object]]:
    base = datetime(2024, 6, 1)
    for idx in range(ROW_COUNT):
        start_station = RNG.choice(STATIONS)
        end_station = RNG.choice(STATIONS)
        rideable_type = RNG.choice(BIKE_TYPES)
        member = RNG.choice(MEMBERSHIP)
        offset = timedelta(minutes=RNG.randint(0, 60 * 24 * 30))
        started_at = base + offset
        duration = RNG.randint(120, 3600)
        ended_at = started_at + timedelta(seconds=duration)
        def jitter(coord: float) -> float:
            return round(coord + RNG.uniform(-0.0007, 0.0007), 6)
        yield {
            "ride_id": f"{started_at.strftime('%Y%m%d')}-{idx:05d}",
            "rideable_type": rideable_type,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "start_station_name": start_station.name,
            "end_station_name": end_station.name,
            "member_casual": member,
            "trip_duration_sec": duration,
            "start_lat": jitter(start_station.lat),
            "start_lng": jitter(start_station.lng),
            "end_lat": jitter(end_station.lat),
            "end_lng": jitter(end_station.lng),
        }


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        SAMPLES_DIR / "retail_superstore_sample.csv",
        [
            "Order ID",
            "Order Date",
            "Ship Date",
            "Ship Mode",
            "Customer ID",
            "Segment",
            "Country",
            "City",
            "State",
            "Postal Code",
            "Region",
            "Category",
            "Sub-Category",
            "Product ID",
            "Sales",
            "Quantity",
            "Discount",
            "Profit",
        ],
        generate_superstore_rows(),
    )

    write_csv(
        SAMPLES_DIR / "telco_churn_sample.csv",
        [
            "customerID",
            "gender",
            "SeniorCitizen",
            "Partner",
            "Dependents",
            "tenure",
            "PhoneService",
            "MultipleLines",
            "InternetService",
            "OnlineSecurity",
            "OnlineBackup",
            "DeviceProtection",
            "TechSupport",
            "StreamingTV",
            "StreamingMovies",
            "Contract",
            "PaperlessBilling",
            "PaymentMethod",
            "MonthlyCharges",
            "TotalCharges",
            "Churn",
        ],
        generate_telco_rows(),
    )

    write_csv(
        SAMPLES_DIR / "citibike_trips_sample.csv",
        [
            "ride_id",
            "rideable_type",
            "started_at",
            "ended_at",
            "start_station_name",
            "end_station_name",
            "member_casual",
            "trip_duration_sec",
            "start_lat",
            "start_lng",
            "end_lat",
            "end_lng",
        ],
        generate_bike_rows(),
    )

    print("Synthetic CSVs written to", SAMPLES_DIR)


if __name__ == "__main__":
    main()
