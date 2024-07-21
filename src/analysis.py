"""Descriptive and comparative analysis used in the report.

Every function takes the master table from src.data.build_master() and returns
a DataFrame or dict, so the notebook stays readable and the report numbers can
be regenerated without re-running any charts.
"""

import numpy as np
import pandas as pd
from scipy import stats


def company_summary(master):
    """The headline table: volume, revenue, profit and margin per company."""
    g = master.groupby("company")
    out = pd.DataFrame(
        {
            "trips": g.size(),
            "customers": g["customer_id"].nunique(),
            "revenue": g["price_charged"].sum(),
            "cost": g["cost_of_trip"].sum(),
            "profit": g["profit"].sum(),
            "mean_km": g["km_travelled"].mean(),
            "mean_fare": g["price_charged"].mean(),
            "profit_per_trip": g["profit"].mean(),
            "median_profit_per_trip": g["profit"].median(),
            "price_per_km": g["price_charged"].sum() / g["km_travelled"].sum(),
            "cost_per_km": g["cost_of_trip"].sum() / g["km_travelled"].sum(),
        }
    )
    out["margin"] = out["profit"] / out["revenue"]
    out["trip_share"] = out["trips"] / out["trips"].sum()
    out["revenue_share"] = out["revenue"] / out["revenue"].sum()
    out["profit_share"] = out["profit"] / out["profit"].sum()
    out["loss_making_trip_rate"] = (
        master.assign(loss=master["profit"] < 0).groupby("company")["loss"].mean()
    )
    out["trips_per_customer"] = out["trips"] / out["customers"]
    return out


def yearly_summary(master):
    """Growth matters more than levels when you are buying a business."""
    g = master.groupby(["company", "year"])
    out = pd.DataFrame(
        {
            "trips": g.size(),
            "revenue": g["price_charged"].sum(),
            "profit": g["profit"].sum(),
            "customers": g["customer_id"].nunique(),
            "profit_per_trip": g["profit"].mean(),
        }
    )
    out["margin"] = out["profit"] / out["revenue"]
    out["profit_growth"] = out.groupby("company")["profit"].pct_change()
    out["trip_growth"] = out.groupby("company")["trips"].pct_change()
    return out.reset_index()


def monthly_series(master):
    """Monthly trips and profit per company, for the seasonality charts."""
    g = master.groupby(["company", "year_month"])
    out = pd.DataFrame({"trips": g.size(), "profit": g["profit"].sum()})
    return out.reset_index()


def seasonality_index(master):
    """Average trips per calendar month divided by the overall monthly average.

    Above 1.0 means that month runs busier than a typical month. Three years of
    data is thin for a seasonal estimate, so this is indicative rather than a
    forecast input.
    """
    monthly = master.groupby(["company", "year", "month"]).size().rename("trips").reset_index()
    avg = monthly.groupby(["company", "month"])["trips"].mean().rename("avg_trips").reset_index()
    avg["index"] = avg["avg_trips"] / avg.groupby("company")["avg_trips"].transform("mean")
    return avg


def city_summary(master):
    """City-level economics plus how much of each city already rides."""
    g = master.groupby(["city", "company"])
    out = pd.DataFrame(
        {
            "trips": g.size(),
            "revenue": g["price_charged"].sum(),
            "profit": g["profit"].sum(),
            "customers": g["customer_id"].nunique(),
            "profit_per_trip": g["profit"].mean(),
        }
    ).reset_index()
    out["margin"] = out["profit"] / out["revenue"]

    city_meta = master.groupby("city")[["population", "city_users", "adoption_rate"]].first()
    out = out.merge(city_meta, on="city", how="left")

    city_totals = out.groupby("city")["trips"].transform("sum")
    out["share_of_city_trips"] = out["trips"] / city_totals
    return out.sort_values(["city", "company"])


def city_pivot(master, value="profit"):
    """Wide city table, handy for ranking and for the report."""
    s = city_summary(master)
    return s.pivot(index="city", columns="company", values=value)


def demographic_summary(master):
    """Who rides each company, by age band, gender and income band."""
    df = master.copy()
    df["age_band"] = pd.cut(
        df["age"], bins=[17, 24, 34, 44, 54, 65], labels=["18-24", "25-34", "35-44", "45-54", "55-65"]
    )
    df["income_band"] = pd.qcut(
        df["monthly_income"], q=4, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"]
    )

    tables = {}
    for dim in ["gender", "age_band", "income_band", "payment_mode"]:
        g = df.groupby(["company", dim], observed=True)
        t = pd.DataFrame(
            {
                "trips": g.size(),
                "profit": g["profit"].sum(),
                "profit_per_trip": g["profit"].mean(),
                "mean_fare": g["price_charged"].mean(),
            }
        )
        t["share_of_company_trips"] = t["trips"] / t.groupby("company")["trips"].transform("sum")
        tables[dim] = t.reset_index()
    return tables


def retention(master):
    """How much of each company's volume comes from customers who come back.

    A cab business that keeps its riders is worth more than one that churns
    them, so this is the closest thing in the data to a loyalty read.
    """
    trips_per_customer = (
        master.groupby(["company", "customer_id"]).size().rename("trips").reset_index()
    )
    trips_per_customer["repeat"] = trips_per_customer["trips"] > 1

    by_company = trips_per_customer.groupby("company")
    out = pd.DataFrame(
        {
            "customers": by_company.size(),
            "repeat_customers": by_company["repeat"].sum(),
            "mean_trips_per_customer": by_company["trips"].mean(),
            "max_trips_per_customer": by_company["trips"].max(),
        }
    )
    out["repeat_rate"] = out["repeat_customers"] / out["customers"]

    repeat_volume = (
        trips_per_customer[trips_per_customer["repeat"]].groupby("company")["trips"].sum()
    )
    total_volume = trips_per_customer.groupby("company")["trips"].sum()
    out["share_of_trips_from_repeat_customers"] = repeat_volume / total_volume
    return out


def customer_overlap(master):
    """Customers who used both companies, which tells you how sticky either is."""
    sets = {c: set(d["customer_id"]) for c, d in master.groupby("company")}
    pink, yellow = sets["Pink Cab"], sets["Yellow Cab"]
    both = pink & yellow
    return {
        "pink_only": len(pink - yellow),
        "yellow_only": len(yellow - pink),
        "both": len(both),
        "share_of_pink_customers_also_yellow": len(both) / len(pink),
        "share_of_yellow_customers_also_pink": len(both) / len(yellow),
    }


# --- Hypothesis tests -------------------------------------------------------


def test_profit_per_trip(master):
    """Is Yellow Cab's profit per trip really higher, or is it noise?

    Sample sizes are large and the profit distribution is right-skewed, so
    Welch's t-test runs alongside Mann-Whitney as a distribution-free check.
    """
    pink = master.loc[master["company"] == "Pink Cab", "profit"]
    yellow = master.loc[master["company"] == "Yellow Cab", "profit"]

    t_stat, t_p = stats.ttest_ind(yellow, pink, equal_var=False)
    u_stat, u_p = stats.mannwhitneyu(yellow, pink, alternative="two-sided")

    # Cohen's d with a pooled standard deviation, for the size of the gap
    # rather than just its significance.
    n1, n2 = len(yellow), len(pink)
    pooled_sd = np.sqrt(
        ((n1 - 1) * yellow.var(ddof=1) + (n2 - 1) * pink.var(ddof=1)) / (n1 + n2 - 2)
    )
    cohens_d = (yellow.mean() - pink.mean()) / pooled_sd

    return {
        "pink_mean": pink.mean(),
        "yellow_mean": yellow.mean(),
        "difference": yellow.mean() - pink.mean(),
        "welch_t": t_stat,
        "welch_p": t_p,
        "mannwhitney_u": u_stat,
        "mannwhitney_p": u_p,
        "cohens_d": cohens_d,
        "n_pink": n2,
        "n_yellow": n1,
    }


def test_margin(master):
    """Same question on margin, which strips out the effect of trip length."""
    pink = master.loc[master["company"] == "Pink Cab", "margin"]
    yellow = master.loc[master["company"] == "Yellow Cab", "margin"]
    t_stat, t_p = stats.ttest_ind(yellow, pink, equal_var=False)
    return {
        "pink_mean_margin": pink.mean(),
        "yellow_mean_margin": yellow.mean(),
        "difference": yellow.mean() - pink.mean(),
        "welch_t": t_stat,
        "welch_p": t_p,
    }


def test_independence(master, column):
    """Chi-square on company against a categorical rider attribute."""
    table = pd.crosstab(master["company"], master[column])
    chi2, p, dof, expected = stats.chi2_contingency(table)
    n = table.to_numpy().sum()
    cramers_v = np.sqrt(chi2 / (n * (min(table.shape) - 1)))
    return {
        "table": table,
        "chi2": chi2,
        "p": p,
        "dof": dof,
        "cramers_v": cramers_v,
    }


def test_city_profit_differences(master):
    """One-way ANOVA on profit per trip across cities, within each company.

    Answers whether the city a trip happens in moves profit at all, which
    matters because the two companies do not operate at the same scale
    everywhere.
    """
    results = {}
    for company, part in master.groupby("company"):
        groups = [g["profit"].to_numpy() for _, g in part.groupby("city")]
        f_stat, p = stats.f_oneway(*groups)
        results[company] = {"f": f_stat, "p": p, "cities": len(groups)}
    return results
