# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # Silver: weather
# Bronze Open-Meteo table → `weather_hourly` in `lh_silver`: one row per hour for New York City.
# Timestamps are UTC; `local_date` is the New York calendar day, used to join daily taxi and
# air-quality figures.

# CELL ********************

from pyspark.sql import functions as F

def lakehouse_paths(name):
    """(Files path, Tables path) of a lakehouse in the current workspace, found by name."""
    root = notebookutils.lakehouse.get(name)["properties"]["abfsPath"]
    # Schema-enabled lakehouses keep tables under Tables/dbo.
    tables = f"{root}/Tables/dbo" if notebookutils.fs.exists(f"{root}/Tables/dbo") else f"{root}/Tables"
    return f"{root}/Files", tables

_, bronze = lakehouse_paths("lh_bronze")
_, silver = lakehouse_paths("lh_silver")
OUT = f"{silver}/weather_hourly"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

weather = (
    spark.read.format("delta").load(f"{bronze}/weather_hourly_raw")
    .select(
        F.to_timestamp("ts").alias("ts"),
        F.col("temperature_c").cast("double").alias("temperature_c"),
        F.col("precipitation_mm").cast("double").alias("precipitation_mm"),
        F.col("wind_speed_kmh").cast("double").alias("wind_speed_kmh"),
        F.col("relative_humidity_pct").cast("double").alias("relative_humidity_pct"),
    )
    .where("ts IS NOT NULL AND temperature_c IS NOT NULL")
    .dropDuplicates(["ts"])
    .withColumn("local_date", F.to_date(F.from_utc_timestamp("ts", "America/New_York")))
)
weather.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(OUT)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Checks

# CELL ********************

weather = spark.read.format("delta").load(OUT)
n = weather.count()
assert n > 0, "weather_hourly is empty"
assert weather.select("ts").distinct().count() == n, "duplicate ts"
assert weather.where("temperature_c < -40 OR temperature_c > 50 OR precipitation_mm < 0").count() == 0, "implausible weather values"
first, last = weather.agg(F.min("ts"), F.max("ts")).first()
print(f"weather_hourly: {n:,} hours from {first} to {last}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
