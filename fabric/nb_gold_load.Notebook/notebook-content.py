# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # Gold: load the star schema
# Reads the silver Delta tables and loads the dimension and fact tables of the warehouse
# `wh_gold` with the Spark connector for Fabric Data Warehouse. Every table is fully reloaded,
# so the notebook can be re-run safely.

# CELL ********************

import com.microsoft.spark.fabric  # noqa: F401  (adds synapsesql to Spark readers and writers)
from pyspark.sql import functions as F

def lakehouse_paths(name):
    """(Files path, Tables path) of a lakehouse in the current workspace, found by name."""
    root = notebookutils.lakehouse.get(name)["properties"]["abfsPath"]
    # Schema-enabled lakehouses keep tables under Tables/dbo.
    tables = f"{root}/Tables/dbo" if notebookutils.fs.exists(f"{root}/Tables/dbo") else f"{root}/Tables"
    return f"{root}/Files", tables

_, silver = lakehouse_paths("lh_silver")
WAREHOUSE = "wh_gold"


def silver_table(name):
    return spark.read.format("delta").load(f"{silver}/{name}")


def date_key(column):
    return F.date_format(column, "yyyyMMdd").cast("int")


def load(df, table):
    """Replaces the warehouse table with df and returns the number of rows written."""
    df.write.mode("overwrite").synapsesql(f"{WAREHOUSE}.dbo.{table}")
    return df.count()


def gold_table(name):
    return spark.read.synapsesql(f"{WAREHOUSE}.dbo.{name}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Facts

# CELL ********************

taxi = silver_table("taxi_daily_zone")
fact_taxi = taxi.select(
    date_key("trip_date").alias("date_key"),
    F.col("zone_id").alias("zone_key"),
    F.col("trips").cast("bigint").alias("trips"),
    F.col("fare_amount").cast("decimal(18,2)").alias("fare_amount"),
    F.col("total_amount").cast("decimal(18,2)").alias("total_amount"),
    F.col("trip_distance").cast("decimal(18,2)").alias("trip_distance"),
    F.col("avg_duration_min").cast("decimal(9,2)").alias("avg_duration_min"),
    F.col("passengers").cast("bigint").alias("passengers"),
    *[F.col(c).cast("bigint").alias(c) for c in taxi.columns if c.startswith("trips_")],
)

air = silver_table("air_quality_daily")
fact_air = air.select(
    date_key("date").alias("date_key"),
    F.col("location_id").cast("int").alias("location_id"),
    "location_name",
    "borough",
    "pollutant",
    F.col("avg_value").cast("decimal(12,4)").alias("avg_value"),
    F.col("min_value").cast("decimal(12,4)").alias("min_value"),
    F.col("max_value").cast("decimal(12,4)").alias("max_value"),
    F.col("measurements").cast("int").alias("measurements"),
)

weather = silver_table("weather_hourly")
fact_weather = weather.select(
    "ts",
    date_key("local_date").alias("date_key"),
    F.col("temperature_c").cast("decimal(6,2)").alias("temperature_c"),
    F.col("precipitation_mm").cast("decimal(8,2)").alias("precipitation_mm"),
    F.col("wind_speed_kmh").cast("decimal(6,2)").alias("wind_speed_kmh"),
    F.col("relative_humidity_pct").cast("decimal(5,2)").alias("relative_humidity_pct"),
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Dimensions
# `DimDate` covers every day between the first and last fact date.

# CELL ********************

bounds = (
    taxi.select(F.col("trip_date").alias("d")).union(air.select(F.col("date").alias("d")))
    .agg(F.min("d").alias("lo"), F.max("d").alias("hi"))
)
weekday = ((F.dayofweek("date") + 5) % 7) + 1  # 1 = Monday … 7 = Sunday
dim_date = bounds.select(F.explode(F.sequence("lo", "hi")).alias("date")).select(
    date_key("date").alias("date_key"),
    "date",
    F.year("date").alias("year"),
    F.quarter("date").alias("quarter"),
    F.month("date").alias("month"),
    F.dayofmonth("date").alias("day"),
    weekday.alias("weekday"),
    F.date_format("date", "EEEE").alias("weekday_name"),
    (weekday >= 6).alias("is_weekend"),
)

dim_zone = silver_table("taxi_zones").select(
    F.col("zone_id").alias("zone_key"), "zone", "borough", "service_zone"
)

dim_fx = silver_table("fx_daily").join(F.broadcast(bounds), F.col("date").between(F.col("lo"), F.col("hi"))).select(
    date_key("date").alias("date_key"),
    F.col("usd_per_eur").cast("decimal(18,6)").alias("usd_per_eur"),
    F.col("eur_per_usd").cast("decimal(18,6)").alias("eur_per_usd"),
    "is_filled",
)

dim_gdp = silver_table("gdp_yearly").select(
    "country_code",
    "year",
    F.col("gdp_usd").cast("decimal(24,2)").alias("gdp_usd"),
    F.col("yoy_growth_pct").cast("decimal(9,4)").alias("yoy_growth_pct"),
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Load

# CELL ********************

written = {
    "DimDate": load(dim_date, "DimDate"),
    "DimZone": load(dim_zone, "DimZone"),
    "DimFX": load(dim_fx, "DimFX"),
    "DimGDP": load(dim_gdp, "DimGDP"),
    "FactTaxiDaily": load(fact_taxi, "FactTaxiDaily"),
    "FactAirQualityDaily": load(fact_air, "FactAirQualityDaily"),
    "FactWeatherHourly": load(fact_weather, "FactWeatherHourly"),
}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Checks
# Row counts are read back from the warehouse, and every fact key must exist in its dimension.

# CELL ********************

for table, rows in written.items():
    in_warehouse = gold_table(table).count()
    assert in_warehouse == rows and rows > 0, f"{table}: wrote {rows}, warehouse has {in_warehouse}"
    print(f"{table}: {rows:,} rows")

dates = gold_table("DimDate").select("date_key")
zones = gold_table("DimZone").select("zone_key")
for fact in ("FactTaxiDaily", "FactAirQualityDaily"):
    assert gold_table(fact).join(dates, "date_key", "left_anti").count() == 0, f"{fact}: date_key missing from DimDate"
assert gold_table("FactTaxiDaily").join(zones, "zone_key", "left_anti").count() == 0, "zone_key missing from DimZone"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
