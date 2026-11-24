# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # NYC mobility, air quality and economy — dashboards
# Reads the gold star schema in `wh_gold` and answers the four analytical questions of the project.
# Every finding below the charts is computed from the data at run time.

# CELL ********************

import com.microsoft.spark.fabric  # noqa: F401
import matplotlib.pyplot as plt
import pandas as pd
from pyspark.sql import functions as F

plt.rcParams.update({"figure.figsize": (12, 4), "axes.grid": True, "grid.alpha": 0.3})
BANDS = ["night", "am_rush", "midday", "pm_rush", "evening"]


def gold(name):
    """A gold table or view as a pandas DataFrame (decimals as floats)."""
    df = spark.read.synapsesql(f"wh_gold.dbo.{name}")
    df = df.select([F.col(c).cast("double").alias(c) if t.startswith("decimal") else F.col(c) for c, t in df.dtypes])
    return df.toPandas()


city = gold("vw_city_daily")
city["date"] = pd.to_datetime(city["date"])
city = city.sort_values("date").set_index("date")
taxi_days = city.dropna(subset=["trips"])

revenue = gold("vw_revenue_usd_eur")
revenue["date"] = pd.to_datetime(revenue["date"])
revenue = revenue.sort_values("date").set_index("date")

fact_taxi = gold("FactTaxiDaily")
fact_air = gold("FactAirQualityDaily")
dim_zone = gold("DimZone")
dim_date = gold("DimDate")
dim_gdp = gold("DimGDP")
dim_date["date"] = pd.to_datetime(dim_date["date"])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 1. Mobility

# CELL ********************

fig, ax = plt.subplots(1, 2, figsize=(16, 4))
taxi_days["trips"].plot(ax=ax[0], alpha=0.3, label="daily")
taxi_days["trips"].rolling(7).mean().plot(ax=ax[0], label="7-day average")
ax[0].set_title("Taxi trips per day")
ax[0].legend()
monthly = taxi_days.resample("MS").agg({"total_amount": "sum", "trips": "sum"})
(monthly["total_amount"] / monthly["trips"]).plot(ax=ax[1], marker="o")
ax[1].set_title("Average revenue per trip by month (USD)")
plt.show()

by_zone = fact_taxi.groupby("zone_key")["trips"].sum().reset_index().merge(dim_zone, on="zone_key")
top = by_zone.nlargest(15, "trips").sort_values("trips")
fig, ax = plt.subplots(1, 2, figsize=(16, 5))
ax[0].barh(top["zone"] + " (" + top["borough"] + ")", top["trips"])
ax[0].set_title("15 busiest pickup zones")
band_share = taxi_days[[f"trips_{b}" for b in BANDS]].sum() / taxi_days["trips"].sum() * 100
ax[1].bar(BANDS, band_share.values)
ax[1].set_title("Share of trips by time of day (%)")
plt.tight_layout()
plt.show()

weekday = taxi_days["trips"].groupby(taxi_days.index.dayofweek).mean()
busiest_zone = by_zone.nlargest(1, "trips").iloc[0]
print(
    f"Finding: {taxi_days['trips'].mean():,.0f} trips on an average day between "
    f"{taxi_days.index.min():%Y-%m-%d} and {taxi_days.index.max():%Y-%m-%d}. "
    f"The busiest weekday is {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][weekday.idxmax()]} and the quietest is "
    f"{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][weekday.idxmin()]}. "
    f"The busiest pickup zone is {busiest_zone['zone']} ({busiest_zone['trips'] / by_zone['trips'].sum():.1%} of all trips), "
    f"and the {band_share.idxmax().replace('trips_', '')} band carries the largest share of trips ({band_share.max():.0f}%)."
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Air quality

# CELL ********************

air = fact_air.merge(dim_date[["date_key", "date"]], on="date_key")
by_day = air.pivot_table(index="date", columns="pollutant", values="avg_value", aggfunc="mean").sort_index()

fig, ax = plt.subplots(1, 2, figsize=(16, 4))
for pollutant in [p for p in ("pm25", "no2") if p in by_day]:
    by_day[pollutant].rolling(7).mean().plot(ax=ax[0], label=f"{pollutant} (7-day average)")
ax[0].set_title("City-wide PM2.5 and NO2 (µg/m³)")
ax[0].legend()
seasonal = by_day.groupby(by_day.index.month).mean()
seasonal[[p for p in ("pm25", "no2", "o3") if p in seasonal]].plot(ax=ax[1], marker="o")
ax[1].set_title("Average by calendar month (µg/m³)")
plt.show()

by_borough = air.pivot_table(index="borough", columns="pollutant", values="avg_value", aggfunc="mean").round(2)
by_borough.plot(kind="bar", figsize=(12, 4), title="Average pollutant level by borough (µg/m³)", rot=0)
plt.show()

if "pm25" in by_day:
    worst = by_day["pm25"].idxmax()
    print(
        f"Finding: city-wide PM2.5 averages {by_day['pm25'].mean():.1f} µg/m³; the worst day was {worst:%Y-%m-%d} "
        f"at {by_day['pm25'].max():.1f} µg/m³. PM2.5 is highest in month {seasonal['pm25'].idxmax()} and lowest in "
        f"month {seasonal['pm25'].idxmin()}."
        + (f" The borough with the highest PM2.5 is {by_borough['pm25'].idxmax()}." if "pm25" in by_borough else "")
    )

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Mobility vs air quality
# How does traffic intensity relate to air quality, and which boroughs or times of day show the
# strongest link?

# CELL ********************

both = city.dropna(subset=["trips", "pm25"])

fig, ax = plt.subplots(1, 2, figsize=(16, 4))
both["trips"].rolling(7).mean().plot(ax=ax[0], color="tab:blue")
ax[0].set_ylabel("trips (7-day average)")
twin = ax[0].twinx()
both["pm25"].rolling(7).mean().plot(ax=twin, color="tab:red")
twin.set_ylabel("PM2.5 µg/m³ (7-day average)")
twin.grid(False)
ax[0].set_title("Taxi trips and PM2.5")
ax[1].scatter(both["trips"], both["pm25"], s=6, alpha=0.4)
ax[1].set_xlabel("trips per day")
ax[1].set_ylabel("PM2.5 µg/m³")
ax[1].set_title("Daily trips vs PM2.5")
plt.show()

pollutants = [p for p in ("pm25", "no2", "o3") if p in city and city[p].notna().sum() > 30]
overall = pd.Series({p: city["trips"].corr(city[p]) for p in pollutants}, name="Pearson r with daily trips")
print(overall.round(3).to_string())

# Time of day: which band's demand moves most closely with each pollutant.
by_band = pd.DataFrame({p: [city[f"trips_{b}"].corr(city[p]) for b in BANDS] for p in pollutants}, index=BANDS).round(3)

# Borough: trips picked up in the borough against pollution measured in the same borough.
taxi_borough = (
    fact_taxi.merge(dim_zone[["zone_key", "borough"]], on="zone_key")
    .groupby(["date_key", "borough"])["trips"].sum().reset_index()
)
air_borough = air.pivot_table(index=["date_key", "borough"], columns="pollutant", values="avg_value", aggfunc="mean").reset_index()
joined = taxi_borough.merge(air_borough, on=["date_key", "borough"])
by_boro = pd.DataFrame({
    p: joined.dropna(subset=[p]).groupby("borough").apply(lambda g: g["trips"].corr(g[p]) if len(g) > 30 else float("nan"))
    for p in pollutants if p in joined
}).round(3)

fig, ax = plt.subplots(1, 2, figsize=(16, 4))
by_band.plot(kind="bar", ax=ax[0], rot=0, title="Correlation of trips with pollution, by time of day")
if not by_boro.empty:
    by_boro.plot(kind="bar", ax=ax[1], rot=0, title="Correlation of trips with pollution, by borough")
plt.show()

if pollutants:
    strongest = overall.abs().idxmax()
    band = by_band[strongest].abs().idxmax()
    text = (
        f"Finding: across {len(both):,} days, daily trips correlate most with {strongest} (r = {overall[strongest]:.2f}). "
        f"By time of day, the strongest link is in the {band} band (r = {by_band.loc[band, strongest]:.2f})."
    )
    if not by_boro.empty and strongest in by_boro and by_boro[strongest].notna().any():
        boro = by_boro[strongest].abs().idxmax()
        text += f" By borough, it is strongest in {boro} (r = {by_boro.loc[boro, strongest]:.2f})."
    print(text + " Correlation is not causation: weather and season drive both series.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4. Economic impact
# Revenue per trip in USD and EUR, the effect of the exchange rate, and long-term growth next to GDP
# and air quality.

# CELL ********************

monthly = revenue.resample("MS").agg({"revenue_usd": "sum", "revenue_eur": "sum", "trips": "sum", "usd_per_eur": "mean"})
monthly["per_trip_usd"] = monthly["revenue_usd"] / monthly["trips"]
monthly["per_trip_eur"] = monthly["revenue_eur"] / monthly["trips"]

fig, ax = plt.subplots(1, 2, figsize=(16, 4))
monthly[["per_trip_usd", "per_trip_eur"]].plot(ax=ax[0], marker="o")
ax[0].set_title("Average revenue per trip: USD vs EUR")
monthly["usd_per_eur"].plot(ax=ax[1], color="tab:green", marker="o")
ax[1].set_title("USD per EUR (monthly average)")
plt.show()

yearly = revenue.groupby(revenue.index.year).agg(revenue_usd=("revenue_usd", "sum"), revenue_eur=("revenue_eur", "sum"), days=("trips", "count"))
yearly = yearly[yearly["days"] >= 330]  # full years only, so partial years do not distort growth
gdp = dim_gdp[dim_gdp["country_code"] == "USA"].set_index("year")["gdp_usd"]
pm25_yearly = by_day["pm25"].groupby(by_day.index.year).mean() if "pm25" in by_day else pd.Series(dtype=float)
trend = pd.DataFrame({
    "Taxi revenue (USD)": yearly["revenue_usd"],
    "Taxi revenue (EUR)": yearly["revenue_eur"],
    "US GDP": gdp,
    "PM2.5": pm25_yearly,
}).loc[yearly.index].dropna(axis=1, how="all")
if len(trend) >= 2:
    indexed = trend / trend.iloc[0] * 100
    indexed.plot(marker="o", figsize=(12, 4), title=f"Indexed growth ({trend.index[0]} = 100)")
    plt.xticks(indexed.index)
    plt.show()
    print(indexed.round(1).to_string())

usd, eur = revenue["avg_revenue_per_trip_usd"].mean(), revenue["avg_revenue_per_trip_eur"].mean()
fx_range = revenue["usd_per_eur"].agg(["min", "max"])
swing = (fx_range["max"] / fx_range["min"] - 1) * 100
print(
    f"Finding: the average trip earns {usd:.2f} USD, or {eur:.2f} EUR. Over the period the rate moved between "
    f"{fx_range['min']:.3f} and {fx_range['max']:.3f} USD per EUR, so the same USD revenue is worth up to {swing:.1f}% "
    f"more or less in EUR depending on the day."
)
if len(trend) >= 2:
    change = (trend.iloc[-1] / trend.iloc[0] - 1) * 100
    pm25_change = change.get("PM2.5", float("nan"))
    if pd.isna(pm25_change):
        verdict = "No PM2.5 readings cover these years, so the effect on air quality cannot be judged."
    elif pm25_change > 1:  # within 1% counts as flat
        verdict = "PM2.5 rose alongside mobility and GDP, so the data does not rule out a cost to air quality."
    else:
        verdict = "PM2.5 was flat or fell while mobility and GDP grew, so growth has not come at the expense of air quality."
    print(
        f"From {trend.index[0]} to {trend.index[-1]}: "
        + ", ".join(f"{name} {value:+.1f}%" for name, value in change.dropna().items())
        + f". {verdict} This compares {len(trend)} full years, which shows a direction, not a cause."
    )
else:
    print("Fewer than two full years of taxi data are loaded, so the multi-year trend is not shown. Lower start_month to add history.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
