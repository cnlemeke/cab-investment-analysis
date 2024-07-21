"""Charts for the report.

Each function saves one PNG and returns the path. Colours match the company
names on purpose, which saves the reader a trip to the legend, and the palette
stays readable in greyscale if anyone prints the report.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

from . import analysis as an

COLOURS = {"Pink Cab": "#d94f8a", "Yellow Cab": "#e8a300"}
ORDER = ["Pink Cab", "Yellow Cab"]

# Anchored to the project root rather than the current directory, so figures
# land in the same place whether this is called from run_analysis.py at the
# root or from a notebook sitting in notebooks/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = PROJECT_ROOT / "outputs" / "figures"


def setup_style():
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "axes.edgecolor": "#444444",
            "grid.color": "#dddddd",
            "legend.frameon": False,
        }
    )


def _save(fig, name, fig_dir=FIG_DIR):
    fig_dir = Path(fig_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / name
    fig.savefig(path)
    plt.close(fig)
    return path


def _money(ax, axis="y", millions=False):
    if millions:
        fmt = mticker.FuncFormatter(lambda v, _: f"${v / 1e6:,.0f}M")
    else:
        fmt = mticker.FuncFormatter(lambda v, _: f"${v:,.0f}")
    getattr(ax, f"{axis}axis").set_major_formatter(fmt)


def plot_market_share(master, fig_dir=FIG_DIR):
    """Trips, revenue and profit side by side, because the three disagree."""
    summary = an.company_summary(master)
    shares = summary[["trip_share", "revenue_share", "profit_share"]].T
    shares.index = ["Trips", "Revenue", "Profit"]

    fig, ax = plt.subplots(figsize=(7, 4))
    bottom = np.zeros(len(shares))
    for company in ORDER:
        ax.bar(
            shares.index,
            shares[company],
            bottom=bottom,
            color=COLOURS[company],
            label=company,
            width=0.6,
        )
        for i, (base, value) in enumerate(zip(bottom, shares[company])):
            ax.text(
                i,
                base + value / 2,
                f"{value:.1%}",
                ha="center",
                va="center",
                color="white",
                fontweight="bold",
            )
        bottom = bottom + shares[company].to_numpy()

    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_title("Yellow Cab's lead widens as you move from trips to profit")
    ax.set_ylabel("Share of market")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncols=2)
    return _save(fig, "01_market_share.png", fig_dir)


def plot_profit_distribution(master, fig_dir=FIG_DIR):
    """Trip-level profit, trimmed at the 1st and 99th percentile for readability."""
    lo, hi = master["profit"].quantile([0.01, 0.99])
    trimmed = master[master["profit"].between(lo, hi)]

    fig, ax = plt.subplots(figsize=(7.5, 4))
    for company in ORDER:
        part = trimmed.loc[trimmed["company"] == company, "profit"]
        ax.hist(
            part, bins=70, alpha=0.6, label=company, color=COLOURS[company], density=True
        )
        ax.axvline(part.median(), color=COLOURS[company], linestyle="--", linewidth=1.5)

    ax.axvline(0, color="#333333", linewidth=1)
    ax.set_title("Profit per trip, with the break-even line and each median")
    ax.set_xlabel("Profit per trip (USD)")
    ax.set_ylabel("Density")
    _money(ax, axis="x")
    ax.legend()
    return _save(fig, "02_profit_distribution.png", fig_dir)


def plot_monthly_profit(master, fig_dir=FIG_DIR):
    monthly = an.monthly_series(master)

    fig, axes = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True)
    for company in ORDER:
        part = monthly[monthly["company"] == company]
        axes[0].plot(part["year_month"], part["trips"], color=COLOURS[company], label=company)
        axes[1].plot(part["year_month"], part["profit"], color=COLOURS[company], label=company)

    axes[0].set_title("Monthly trips")
    axes[0].set_ylabel("Trips")
    axes[1].set_title("Monthly profit")
    axes[1].set_ylabel("Profit")
    _money(axes[1])
    axes[1].set_xlabel("")
    axes[0].legend()
    fig.suptitle(
        "Trips peak every December, and 2018 profit came in below 2017 for both",
        fontweight="bold",
        y=0.98,
    )
    fig.tight_layout()
    return _save(fig, "03_monthly_trend.png", fig_dir)


def plot_seasonality(master, fig_dir=FIG_DIR):
    si = an.seasonality_index(master)
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    fig, ax = plt.subplots(figsize=(7.5, 4))
    width = 0.4
    x = np.arange(12)
    for i, company in enumerate(ORDER):
        part = si[si["company"] == company].sort_values("month")
        ax.bar(x + (i - 0.5) * width, part["index"], width, color=COLOURS[company], label=company)

    ax.axhline(1.0, color="#333333", linewidth=1, linestyle="--")
    ax.set_xticks(x, month_names)
    ax.set_title("Seasonality index, where 1.0 is an average month")
    ax.set_ylabel("Index")
    ax.legend()
    return _save(fig, "04_seasonality.png", fig_dir)


def plot_city_profit(master, fig_dir=FIG_DIR):
    pivot = an.city_pivot(master, "profit")
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total").drop(columns="total")

    fig, ax = plt.subplots(figsize=(8, 7))
    y = np.arange(len(pivot))
    height = 0.4
    for i, company in enumerate(ORDER):
        ax.barh(y + (i - 0.5) * height, pivot[company], height, color=COLOURS[company], label=company)

    ax.set_yticks(y, pivot.index)
    ax.set_xscale("log")
    ax.set_title("Total profit by city, 2016 to 2018 (log scale)")
    ax.set_xlabel("Profit")
    _money(ax, axis="x")
    ax.legend(loc="lower right")
    return _save(fig, "05_city_profit.png", fig_dir)


def plot_city_share(master, fig_dir=FIG_DIR):
    """Where Pink Cab actually holds its own, plotted against market adoption."""
    city = an.city_summary(master)
    pink = city[city["company"] == "Pink Cab"].copy()

    fig, ax = plt.subplots(figsize=(8, 5))
    sizes = pink["trips"] / pink["trips"].max() * 600 + 30
    ax.scatter(
        pink["adoption_rate"],
        pink["share_of_city_trips"],
        s=sizes,
        color=COLOURS["Pink Cab"],
        alpha=0.65,
        edgecolor="white",
    )
    ax.axhline(0.5, color="#333333", linestyle="--", linewidth=1)

    # Several small cities sit almost on top of each other at the left edge, so
    # labels alternate above and below the point to stop them colliding.
    pink = pink.sort_values("adoption_rate").reset_index(drop=True)
    for i, row in pink.iterrows():
        offset = (8, 5) if i % 2 == 0 else (8, -11)
        ax.annotate(
            row["city"].title(),
            (row["adoption_rate"], row["share_of_city_trips"]),
            textcoords="offset points",
            xytext=offset,
            fontsize=7.5,
            color="#444444",
        )

    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlabel("Share of the city's population already using a cab service")
    ax.set_ylabel("Pink Cab's share of city trips")
    ax.set_title(
        "Pink Cab only leads in small, lightly served markets\n(bubble size is trip volume)"
    )
    return _save(fig, "06_pink_city_position.png", fig_dir)


def plot_margin_by_city(master, fig_dir=FIG_DIR):
    city = an.city_summary(master)
    order = (
        city[city["company"] == "Yellow Cab"].sort_values("margin", ascending=False)["city"].tolist()
    )

    fig, ax = plt.subplots(figsize=(9, 4.5))
    sns.barplot(
        data=city,
        x="city",
        y="margin",
        hue="company",
        order=order,
        hue_order=ORDER,
        palette=COLOURS,
        ax=ax,
    )
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_title("Profit margin by city, sorted by Yellow Cab's margin")
    ax.set_xlabel("")
    ax.set_ylabel("Margin")
    ax.tick_params(axis="x", rotation=75)
    ax.legend(title="")
    return _save(fig, "07_margin_by_city.png", fig_dir)


def plot_retention(master, fig_dir=FIG_DIR):
    ret = an.retention(master)
    trips_per_customer = master.groupby(["company", "customer_id"]).size().rename("trips").reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    bars = axes[0].bar(
        ORDER, [ret.loc[c, "repeat_rate"] for c in ORDER], color=[COLOURS[c] for c in ORDER], width=0.5
    )
    axes[0].bar_label(bars, fmt="%.1f%%", labels=[f"{ret.loc[c, 'repeat_rate']:.1%}" for c in ORDER])
    axes[0].yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    axes[0].set_ylim(0, 0.85)
    axes[0].set_title("Customers who took more than one trip")
    axes[0].set_ylabel("Share of customers")

    for company in ORDER:
        part = trips_per_customer.loc[trips_per_customer["company"] == company, "trips"]
        axes[1].hist(
            part, bins=range(1, 22), alpha=0.6, density=True, color=COLOURS[company], label=company
        )
    axes[1].set_title("Trips per customer")
    axes[1].set_xlabel("Trips over the three years")
    axes[1].set_ylabel("Density")
    axes[1].legend()

    fig.tight_layout()
    return _save(fig, "08_retention.png", fig_dir)


def plot_demographics(master, fig_dir=FIG_DIR):
    """Four rider attributes, none of which separate the two companies."""
    tables = an.demographic_summary(master)
    dims = [("age_band", "Age band"), ("income_band", "Income quartile"), ("gender", "Gender"), ("payment_mode", "Payment mode")]

    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, (dim, label) in zip(axes.ravel(), dims):
        sns.barplot(
            data=tables[dim],
            x=dim,
            y="share_of_company_trips",
            hue="company",
            hue_order=ORDER,
            palette=COLOURS,
            ax=ax,
        )
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
        ax.set_title(label)
        ax.set_xlabel("")
        ax.set_ylabel("Share of company trips")
        # One shared legend under the figure beats four identical ones.
        if ax.get_legend() is not None:
            ax.get_legend().remove()

    handles = [plt.Rectangle((0, 0), 1, 1, color=COLOURS[c]) for c in ORDER]
    fig.legend(handles, ORDER, loc="lower center", ncols=2, frameon=False)
    fig.suptitle(
        "Rider mix is almost identical, so demographics do not separate the two",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    return _save(fig, "09_demographics.png", fig_dir)


def plot_model_performance(results, fig_dir=FIG_DIR):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    labels = results.index.tolist()
    y = np.arange(len(labels))

    axes[0].barh(y, results["test_mae"], color="#4a6fa5", height=0.55)
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    axes[0].set_title("Mean absolute error on 2018")
    axes[0].set_xlabel("MAE")
    _money(axes[0], axis="x")
    axes[0].bar_label(axes[0].containers[0], fmt="$%.0f", padding=3)

    axes[1].barh(y, results["test_r2"], color="#4a6fa5", height=0.55)
    axes[1].set_yticks(y, [])
    axes[1].invert_yaxis()
    axes[1].set_title("R-squared on 2018")
    axes[1].set_xlabel("R-squared")
    axes[1].bar_label(axes[1].containers[0], fmt="%.3f", padding=3)

    fig.suptitle("Model performance on the held-out year", fontweight="bold")
    fig.tight_layout()
    return _save(fig, "10_model_performance.png", fig_dir)


def plot_feature_importance(importance, fig_dir=FIG_DIR):
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    data = importance.sort_values("mae_increase")
    ax.barh(data["feature"], data["mae_increase"], xerr=data["std"], color="#4a6fa5", height=0.6)
    ax.set_title("What the model actually uses, measured by permutation")
    ax.set_xlabel("Increase in MAE when the column is shuffled (USD)")
    _money(ax, axis="x")
    return _save(fig, "11_feature_importance.png", fig_dir)


def plot_predicted_vs_actual(pipe, X_test, y_test, sample=8000, fig_dir=FIG_DIR, random_state=42):
    rng = np.random.default_rng(random_state)
    idx = rng.choice(len(X_test), size=min(sample, len(X_test)), replace=False)
    Xs, ys = X_test.iloc[idx], y_test.iloc[idx]
    pred = pipe.predict(Xs)

    fig, ax = plt.subplots(figsize=(6, 6))
    for company in ORDER:
        mask = (Xs["company"] == company).to_numpy()
        ax.scatter(ys[mask], pred[mask], s=6, alpha=0.25, color=COLOURS[company], label=company)

    lims = [min(ys.min(), pred.min()), max(ys.max(), pred.max())]
    ax.plot(lims, lims, color="#333333", linewidth=1, linestyle="--")
    ax.set_xlabel("Actual profit")
    ax.set_ylabel("Predicted profit")
    ax.set_title("Predicted against actual on 2018\n(8,000 sampled trips)")
    _money(ax, axis="x")
    _money(ax, axis="y")
    ax.legend(markerscale=3)
    return _save(fig, "12_predicted_vs_actual.png", fig_dir)
