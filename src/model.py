"""Predicting profit on a single trip.

The business reason for this section: the descriptive work says Yellow Cab
earns more per trip, but it does not say how much of that gap is the company
itself and how much is the mix of cities and trip lengths it happens to serve.
A model that holds the other factors constant answers that.

Two rules are followed throughout.

1. No leakage. Profit is price_charged minus cost_of_trip, so neither of those
   columns, nor anything derived from them (margin, price_per_km, cost_per_km),
   can be a feature. Only what is knowable before the meter runs goes in.
2. Time-based split. Trips are not independent across time and 2018 looks
   different from the two years before it, so the test set is 2018 and the
   training set is 2016 to 2017. A random split would quietly leak the later
   regime into training and flatter the model.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = ["km_travelled", "age", "monthly_income", "month", "population", "adoption_rate"]
CATEGORICAL = ["company", "city", "weekday", "payment_mode", "gender"]
TARGET = "profit"

TEST_YEAR = 2018


def split_by_year(master, test_year=TEST_YEAR):
    """Everything before test_year trains, test_year itself is held out."""
    features = NUMERIC + CATEGORICAL
    train = master[master["year"] < test_year]
    test = master[master["year"] == test_year]
    return (
        train[features],
        train[TARGET],
        test[features],
        test[TARGET],
    )


def make_preprocessor():
    return ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC),
            # sparse_output=False because HistGradientBoostingRegressor will not
            # take a sparse matrix, and the widened frame is small enough here.
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", drop="first", sparse_output=False),
                CATEGORICAL,
            ),
        ]
    )


def build_models():
    """Two baselines and two real models, so the gains are easy to read.

    The km-only baseline matters more than the mean baseline: trip length is
    the obvious driver, and any model that cannot beat it is not earning its
    complexity.
    """
    return {
        "Mean baseline": Pipeline(
            [("model", DummyRegressor(strategy="mean"))]
        ),
        "Distance only (linear)": Pipeline(
            [
                ("pre", ColumnTransformer([("km", StandardScaler(), ["km_travelled"])])),
                ("model", Ridge(alpha=1.0)),
            ]
        ),
        "Ridge, all features": Pipeline(
            [("pre", make_preprocessor()), ("model", Ridge(alpha=1.0))]
        ),
        "Gradient boosting": Pipeline(
            [
                ("pre", make_preprocessor()),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        max_iter=400,
                        learning_rate=0.08,
                        max_depth=6,
                        min_samples_leaf=50,
                        l2_regularization=1.0,
                        random_state=42,
                    ),
                ),
            ]
        ),
    }


def evaluate(master, test_year=TEST_YEAR):
    """Fit each model on the earlier years and score it on the held-out year."""
    X_train, y_train, X_test, y_test = split_by_year(master, test_year)

    rows = []
    fitted = {}
    for name, pipe in build_models().items():
        pipe.fit(X_train, y_train)
        pred_train = pipe.predict(X_train)
        pred_test = pipe.predict(X_test)
        rows.append(
            {
                "model": name,
                "train_mae": mean_absolute_error(y_train, pred_train),
                "test_mae": mean_absolute_error(y_test, pred_test),
                "train_rmse": root_mean_squared_error(y_train, pred_train),
                "test_rmse": root_mean_squared_error(y_test, pred_test),
                "train_r2": r2_score(y_train, pred_train),
                "test_r2": r2_score(y_test, pred_test),
                # Average signed error on the test year. Tells you whether the
                # model runs hot or cold once the regime changes, which the
                # error metrics above hide.
                "test_bias": float(np.mean(pred_test - y_test)),
            }
        )
        fitted[name] = pipe

    results = pd.DataFrame(rows).set_index("model")
    return results, fitted, (X_train, y_train, X_test, y_test)


def feature_importance(pipe, X_test, y_test, n_repeats=5, sample=40000, random_state=42):
    """Permutation importance on the held-out year.

    Permutation rather than a tree's internal gain, because gain is biased
    toward high-cardinality columns and city has nineteen levels. Scored on a
    sample because permuting nineteen columns over ninety thousand rows is slow
    and the ranking is stable well before that.
    """
    rng = np.random.default_rng(random_state)
    if sample and len(X_test) > sample:
        idx = rng.choice(len(X_test), size=sample, replace=False)
        X_test = X_test.iloc[idx]
        y_test = y_test.iloc[idx]

    result = permutation_importance(
        pipe,
        X_test,
        y_test,
        n_repeats=n_repeats,
        random_state=random_state,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
    )
    return (
        pd.DataFrame(
            {
                "feature": X_test.columns,
                "mae_increase": result.importances_mean,
                "std": result.importances_std,
            }
        )
        .sort_values("mae_increase", ascending=False)
        .reset_index(drop=True)
    )


def company_effect(pipe, X_test):
    """What the model says the company badge alone is worth per trip.

    Take the held-out trips, score them as they are, then score the same trips
    with the company flipped. The average difference is the company effect with
    city, distance, date and rider held constant.
    """
    as_is = pipe.predict(X_test)

    flipped = X_test.copy()
    flipped["company"] = np.where(
        flipped["company"] == "Yellow Cab", "Pink Cab", "Yellow Cab"
    )
    counterfactual = pipe.predict(flipped)

    out = pd.DataFrame(
        {
            "company": X_test["company"].to_numpy(),
            "predicted_as_is": as_is,
            "predicted_if_other_company": counterfactual,
        }
    )
    out["uplift_from_being_yellow"] = np.where(
        out["company"] == "Yellow Cab",
        out["predicted_as_is"] - out["predicted_if_other_company"],
        out["predicted_if_other_company"] - out["predicted_as_is"],
    )
    return out.groupby("company")["uplift_from_being_yellow"].agg(["mean", "median", "count"])
