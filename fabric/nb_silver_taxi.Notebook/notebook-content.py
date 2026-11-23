# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # Silver: NYC yellow taxi
# Bronze Parquet files → `taxi_trips` (cleaned trips), `taxi_daily_zone` (daily aggregates per
# pickup zone) and `taxi_zones` (zone lookup) in `lh_silver`.
#
# Only months that are not yet in `taxi_trips` are processed, unless `full_refresh` is set.

# PARAMETERS CELL ********************

full_refresh = False

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import re

from pyspark.sql import functions as F

def lakehouse_paths(name):
    """(Files path, Tables path) of a lakehouse in the current workspace, found by name."""
    root = notebookutils.lakehouse.get(name)["properties"]["abfsPath"]
    # Schema-enabled lakehouses keep tables under Tables/dbo.
    tables = f"{root}/Tables/dbo" if notebookutils.fs.exists(f"{root}/Tables/dbo") else f"{root}/Tables"
    return f"{root}/Files", tables

bronze_files, _ = lakehouse_paths("lh_bronze")
_, silver = lakehouse_paths("lh_silver")
TRIPS, DAILY, ZONES = f"{silver}/taxi_trips", f"{silver}/taxi_daily_zone", f"{silver}/taxi_zones"
TAXI_DIR = f"{bronze_files}/taxi"

# Time-of-day bands by pickup hour (start hour inclusive, end hour exclusive).
BANDS = {"night": (0, 6), "am_rush": (6, 10), "midday": (10, 16), "pm_rush": (16, 20), "evening": (20, 24)}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Zone lookup

# CELL ********************

zones = (
    spark.read.option("header", True).csv(f"{TAXI_DIR}/taxi_zone_lookup.csv")
    .select(
        F.col("LocationID").cast("int").alias("zone_id"),
        F.col("Zone").alias("zone"),
        F.col("Borough").alias("borough"),
        F.col("service_zone").alias("service_zone"),
    )
    .dropDuplicates(["zone_id"])
)
zones.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(ZONES)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Trips
# Each month file is read on its own and cast to one schema, because TLC column types drift
# between years. Rows are kept when the pickup falls inside the file's month, the drop-off is
# after the pickup, distance and fare are positive, and the trip lasts at most 12 hours.

# CELL ********************

def clean_month(month):
    raw = spark.read.parquet(f"{TAXI_DIR}/yellow_tripdata_{month}.parquet")
    trips = raw.select(
        F.col("tpep_pickup_datetime").cast("timestamp").alias("pickup_ts"),
        F.col("tpep_dropoff_datetime").cast("timestamp").alias("dropoff_ts"),
        F.col("PULocationID").cast("int").alias("pickup_zone_id"),
        F.col("DOLocationID").cast("int").alias("dropoff_zone_id"),
        F.col("passenger_count").cast("int").alias("passenger_count"),
        F.col("trip_distance").cast("double").alias("trip_distance"),
        F.col("fare_amount").cast("double").alias("fare_amount"),
        F.col("total_amount").cast("double").alias("total_amount"),
    )
    return (
        trips
        .withColumn("duration_min", (F.col("dropoff_ts").cast("long") - F.col("pickup_ts").cast("long")) / 60)
        .where(
            (F.date_format("pickup_ts", "yyyy-MM") == month)
            & (F.col("dropoff_ts") > F.col("pickup_ts"))
            & (F.col("trip_distance") > 0)
            & (F.col("fare_amount") > 0)
            & (F.col("duration_min") <= 720)
            & F.col("pickup_zone_id").isNotNull()
        )
        .dropDuplicates(["pickup_ts", "dropoff_ts", "pickup_zone_id", "dropoff_zone_id", "total_amount"])
        .withColumn("trip_date", F.to_date("pickup_ts"))
        .withColumn("pickup_hour", F.hour("pickup_ts"))
        .withColumn("trip_month", F.lit(month))
    )


landed = sorted(
    m.group(1) for f in notebookutils.fs.ls(TAXI_DIR)
    if (m := re.fullmatch(r"yellow_tripdata_(\d{4}-\d{2})\.parquet", f.name))
)
have_trips = notebookutils.fs.exists(f"{TRIPS}/_delta_log")
done = set() if full_refresh or not have_trips else {
    r.trip_month for r in spark.read.format("delta").load(TRIPS).select("trip_month").distinct().collect()
}
todo = [m for m in landed if m not in done]
print(f"{len(landed)} months landed, {len(todo)} to process: {todo}")

for month in todo:
    (
        clean_month(month).write.format("delta").mode("overwrite")
        .partitionBy("trip_month").option("replaceWhere", f"trip_month = '{month}'").save(TRIPS)
    )

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Daily aggregates per pickup zone

# CELL ********************

trips = spark.read.format("delta").load(TRIPS)
band_counts = [
    F.sum(F.when((F.col("pickup_hour") >= lo) & (F.col("pickup_hour") < hi), 1).otherwise(0)).alias(f"trips_{name}")
    for name, (lo, hi) in BANDS.items()
]
daily = trips.groupBy("trip_date", F.col("pickup_zone_id").alias("zone_id")).agg(
    F.count("*").alias("trips"),
    F.sum("fare_amount").alias("fare_amount"),
    F.sum("total_amount").alias("total_amount"),
    F.sum("trip_distance").alias("trip_distance"),
    F.avg("duration_min").alias("avg_duration_min"),
    F.sum("passenger_count").alias("passengers"),
    *band_counts,
)
daily.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(DAILY)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Checks

# CELL ********************

daily = spark.read.format("delta").load(DAILY)
n = daily.count()
assert n > 0, "taxi_daily_zone is empty"
assert daily.select("trip_date", "zone_id").distinct().count() == n, "duplicate (trip_date, zone_id)"
assert daily.where("zone_id IS NULL OR trip_date IS NULL").count() == 0, "null keys"
band_sum = " + ".join(f"trips_{b}" for b in BANDS)
assert daily.where(f"{band_sum} <> trips").count() == 0, "time bands do not add up to trips"
n_zones = spark.read.format("delta").load(ZONES).count()
assert n_zones == 265, f"expected 265 taxi zones, got {n_zones}"
print(f"taxi_trips: {trips.count():,} rows; taxi_daily_zone: {n:,} rows; taxi_zones: {n_zones}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
