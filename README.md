# Cab investment analysis

Which of two US cab operators should a private investor acquire? This repository works through 359,392 trips from 2016 to 2018 and answers it.

**Short version:** buy Yellow Cab, and price the deal off 2018 rather than the three-year average. The full reasoning is in **[REPORT.md](REPORT.md)**.

![Market share](outputs/figures/01_market_share.png)

## The question

XYZ is a private firm planning to enter the US cab market by acquiring an existing operator. Two candidates: Pink Cab and Yellow Cab. They supplied four files covering three years of trips, customers and city populations, and asked which company to buy.

## What the analysis found

Yellow Cab runs 76% of the trips and keeps 89% of the profit. That gap is the whole finding, and most of the work goes into testing whether it holds up.

- **$44.0m profit against $5.31m**, on a 35.0% margin against 20.2%
- **Yellow Cab out-earns Pink Cab in all 19 cities**, and 60% of its own profit comes from New York alone
- **13.1% of Pink Cab trips lose money**, against 5.0% of Yellow Cab's
- **Rider demographics are identical** between the two, so there is no segment to buy
- **Both companies lost about a fifth of their profit in 2018** while volumes barely moved
- **Controlling for city, distance, timing and rider**, the Yellow Cab badge is still worth about $50 per trip

## Repository layout

```
.
├── README.md                    you are here
├── REPORT.md                    the written analysis and recommendation
├── run_analysis.py              regenerates every figure and table
├── requirements.txt
├── data/raw/                    the four source CSVs
├── notebooks/
│   └── cab_investment_analysis.ipynb    the working analysis, start to finish
├── src/
│   ├── data.py                  loading, cleaning, joining, join audit
│   ├── analysis.py              descriptive tables and hypothesis tests
│   ├── model.py                 profit model, time split, company effect
│   └── plots.py                 the twelve charts
└── outputs/
    ├── figures/                 PNGs used in the report
    └── tables/                  CSV and JSON behind every number quoted
```

The notebook tells the story. The modules hold the logic, so the notebook stays readable and every number in the report can be regenerated without re-running charts by hand.

## Running it

Built and tested on Python 3.11 with the versions pinned in `requirements.txt`.

```bash
pip install -r requirements.txt
python run_analysis.py
```

Takes two to three minutes, mostly the gradient boosting fit and the permutation importance. It writes to `outputs/figures/` and `outputs/tables/`.

To work through the notebook instead:

```bash
jupyter lab notebooks/cab_investment_analysis.ipynb
```

It runs from either the project root or `notebooks/`.

## Method notes

Three decisions are worth flagging because they change the answer.

**The merge drops 80,706 rows on purpose.** `Transaction_ID.csv` has more rows than `Cab_Data.csv`, and those extras have no trip attached. They cannot contribute to a profit comparison. `src.data.audit_join()` reports the count rather than letting the merge swallow it.

**The model splits by time, not at random.** Training on 2016 and 2017 and holding out 2018 is harder than a random split and more honest, because 2018 behaves differently from the two years before it. The held-out year exposes a $20.92 per trip over-prediction that a random split would have hidden.

**No leakage into the model.** Profit is fare minus cost, so fare, cost, margin and price per km are all excluded as features. Only what is knowable before the meter runs goes in.

## Data

The four files in `data/raw/` are the G2M cab investment case study dataset: trip records, transaction-to-customer links, customer demographics, and city populations. Column meanings are documented in `src/data.py`.

The customer attributes look generated rather than observed, which is noted in the report. No conclusion depends on them.

## Licence

MIT. See [LICENSE](LICENSE).
