"""Regenerate every figure and table quoted in REPORT.md.

Run from the project root:

    python run_analysis.py

Takes a couple of minutes, mostly the gradient boosting fit and the
permutation importance.
"""

import json
from pathlib import Path

import pandas as pd

from src import analysis as an
from src import model as md
from src import plots
from src.data import audit_join, build_master

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
FIG_DIR = PROJECT_ROOT / "outputs" / "figures"


def save_table(df, name):
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLE_DIR / f"{name}.csv"
    df.to_csv(path)
    print(f"  wrote {path}")
    return path


def main():
    plots.setup_style()
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    print("Checking the joins before trusting anything downstream")
    audit = audit_join(DATA_DIR)
    for key, value in audit.items():
        print(f"  {key}: {value}")
    with open(TABLE_DIR / "join_audit.json", "w") as f:
        json.dump({k: str(v) for k, v in audit.items()}, f, indent=2)

    print("\nBuilding the master table")
    master = build_master(DATA_DIR)
    print(f"  {len(master):,} trips, {master['customer_id'].nunique():,} customers")

    print("\nDescriptive tables")
    save_table(an.company_summary(master), "company_summary")
    save_table(an.yearly_summary(master), "yearly_summary")
    save_table(an.city_summary(master), "city_summary")
    save_table(an.retention(master), "retention")
    save_table(an.seasonality_index(master), "seasonality_index")
    for dim, table in an.demographic_summary(master).items():
        save_table(table, f"demographics_{dim}")

    print("\nHypothesis tests")
    tests = {
        "profit_per_trip": an.test_profit_per_trip(master),
        "margin": an.test_margin(master),
        "city_anova": an.test_city_profit_differences(master),
        "customer_overlap": an.customer_overlap(master),
    }
    for column in ["gender", "payment_mode"]:
        result = an.test_independence(master, column)
        tests[f"independence_{column}"] = {
            k: v for k, v in result.items() if k != "table"
        }
        save_table(result["table"], f"crosstab_{column}")
    with open(TABLE_DIR / "hypothesis_tests.json", "w") as f:
        json.dump(tests, f, indent=2, default=str)
    print(f"  wrote {TABLE_DIR / 'hypothesis_tests.json'}")

    print("\nFitting models on 2016-2017 and scoring on 2018")
    results, fitted, (X_train, y_train, X_test, y_test) = md.evaluate(master)
    print(results.round(3).to_string())
    save_table(results, "model_performance")

    best = fitted["Gradient boosting"]
    importance = md.feature_importance(best, X_test, y_test)
    save_table(importance, "feature_importance")
    effect = md.company_effect(best, X_test)
    save_table(effect, "company_effect")
    print("\nCompany effect on held-out trips (USD per trip)")
    print(effect.round(2).to_string())

    print("\nCharts")
    paths = [
        plots.plot_market_share(master),
        plots.plot_profit_distribution(master),
        plots.plot_monthly_profit(master),
        plots.plot_seasonality(master),
        plots.plot_city_profit(master),
        plots.plot_city_share(master),
        plots.plot_margin_by_city(master),
        plots.plot_retention(master),
        plots.plot_demographics(master),
        plots.plot_model_performance(results),
        plots.plot_feature_importance(importance),
        plots.plot_predicted_vs_actual(best, X_test, y_test),
    ]
    for path in paths:
        print(f"  wrote {path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
