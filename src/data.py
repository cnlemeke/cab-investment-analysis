"""Loading, cleaning and joining the four raw files.

The four CSVs are a star schema in disguise. Cab_Data is the fact table
(one row per completed trip), Transaction_ID links a trip to a customer,
Customer_ID holds demographics, and City holds population figures.
"""

from pathlib import Path

import pandas as pd

# Excel counts days from 1900-01-01 but gets 1900 wrong as a leap year, so
# pandas needs 1899-12-30 as the origin to land on the right calendar date.
EXCEL_EPOCH = "1899-12-30"

RAW_FILES = {
    "cab": "Cab_Data.csv",
    "transactions": "Transaction_ID.csv",
    "customers": "Customer_ID.csv",
    "cities": "City.csv",
}


def load_raw(data_dir="data"):
    """Read the four CSVs as they come, no cleaning yet."""
    data_dir = Path(data_dir)
    return {name: pd.read_csv(data_dir / f) for name, f in RAW_FILES.items()}


def clean_cities(cities):
    """Population and Users arrive as quoted strings with commas and padding."""
    out = cities.copy()
    out.columns = ["city", "population", "city_users"]
    for col in ["population", "city_users"]:
        out[col] = (
            out[col].astype(str).str.replace(",", "", regex=False).str.strip().astype(int)
        )
    out["city"] = out["city"].str.strip()
    # Share of the city already using either cab company. Useful as a rough
    # proxy for how much room is left to grow in each market.
    out["adoption_rate"] = out["city_users"] / out["population"]
    return out


def clean_trips(cab):
    """Rename to snake_case, convert the date, and derive profit per trip."""
    out = cab.copy()
    out.columns = [
        "transaction_id",
        "date_serial",
        "company",
        "city",
        "km_travelled",
        "price_charged",
        "cost_of_trip",
    ]
    out["date"] = pd.to_datetime(out["date_serial"], unit="D", origin=EXCEL_EPOCH)
    out = out.drop(columns="date_serial")

    out["city"] = out["city"].str.strip()
    out["profit"] = out["price_charged"] - out["cost_of_trip"]
    out["margin"] = out["profit"] / out["price_charged"]
    out["price_per_km"] = out["price_charged"] / out["km_travelled"]
    out["cost_per_km"] = out["cost_of_trip"] / out["km_travelled"]

    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    out["year_month"] = out["date"].dt.to_period("M").dt.to_timestamp()
    out["weekday"] = out["date"].dt.day_name()
    out["is_weekend"] = out["date"].dt.dayofweek >= 5
    return out


def clean_customers(customers):
    out = customers.copy()
    out.columns = ["customer_id", "gender", "age", "monthly_income"]
    return out


def clean_transactions(transactions):
    out = transactions.copy()
    out.columns = ["transaction_id", "customer_id", "payment_mode"]
    return out


def build_master(data_dir="data"):
    """One wide table: every completed trip with its customer and city attached.

    Transaction_ID has about 80k more rows than Cab_Data. Those extra rows have
    no trip attached, so an inner join on the trip table is the right call here
    and the discarded count is reported by audit_join() rather than silently
    dropped.
    """
    raw = load_raw(data_dir)

    trips = clean_trips(raw["cab"])
    transactions = clean_transactions(raw["transactions"])
    customers = clean_customers(raw["customers"])
    cities = clean_cities(raw["cities"])

    master = (
        trips.merge(transactions, on="transaction_id", how="left")
        .merge(customers, on="customer_id", how="left")
        .merge(cities, on="city", how="left")
    )
    return master


def audit_join(data_dir="data"):
    """Counts worth quoting in the report before anyone trusts the merged table."""
    raw = load_raw(data_dir)
    trips = clean_trips(raw["cab"])
    transactions = clean_transactions(raw["transactions"])
    customers = clean_customers(raw["customers"])
    cities = clean_cities(raw["cities"])

    trip_ids = set(trips["transaction_id"])
    txn_ids = set(transactions["transaction_id"])

    return {
        "trip_rows": len(trips),
        "transaction_rows": len(transactions),
        "customer_rows": len(customers),
        "city_rows": len(cities),
        "trips_without_transaction": len(trip_ids - txn_ids),
        "transactions_without_trip": len(txn_ids - trip_ids),
        "duplicate_trip_ids": int(trips["transaction_id"].duplicated().sum()),
        "customers_missing_demographics": int(
            (~transactions["customer_id"].isin(customers["customer_id"])).sum()
        ),
        "cities_in_trips": trips["city"].nunique(),
        "cities_in_city_file": cities["city"].nunique(),
        "cities_with_no_trips": sorted(set(cities["city"]) - set(trips["city"])),
        "date_min": trips["date"].min(),
        "date_max": trips["date"].max(),
        "loss_making_trips": int((trips["profit"] < 0).sum()),
        "missing_values": int(trips.isna().sum().sum()),
    }
