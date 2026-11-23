# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # Silver: air quality
# Bronze OpenAQ tables → `air_quality_daily` in `lh_silver`: one row per day, monitoring station
# and pollutant (PM2.5, NO2, O3), all values in µg/m³, each station assigned to a borough.

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
OUT = f"{silver}/air_quality_daily"

# Gas conversion to µg/m³ at 25 °C and 1 atm: ppb × molecular weight / 24.45.
MOLECULAR_WEIGHT = {"no2": 46.01, "o3": 48.00}
BOROUGH_CENTRES = {
    "Manhattan": (40.7831, -73.9712),
    "Brooklyn": (40.6782, -73.9442),
    "Queens": (40.7282, -73.7949),
    "Bronx": (40.8448, -73.8648),
    "Staten Island": (40.5795, -74.1502),
}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

locations = (
    spark.read.format("delta").load(f"{bronze}/openaq_locations_raw")
    .select("sensor_id", "location_id", "location_name", "latitude", "longitude")
    .dropDuplicates(["sensor_id"])
)
daily = spark.read.format("delta").load(f"{bronze}/openaq_daily_raw")

unit = F.lower(F.col("units"))
weight = F.coalesce(*[F.when(F.col("pollutant") == p, F.lit(w)) for p, w in MOLECULAR_WEIGHT.items()])
factor = (
    F.when(unit == "ppm", 1000 * weight / 24.45)
    .when(unit == "ppb", weight / 24.45)
    .otherwise(F.lit(1.0))
)

measurements = (
    daily
    .withColumn("pollutant", F.lower(F.col("parameter_name")))
    .where(F.col("pollutant").isin("pm25", "no2", "o3") & F.col("value").isNotNull() & (F.col("value") >= 0))
    .withColumn("date", F.to_date("day"))
    .withColumn("value", F.col("value") * factor)
    .withColumn("min_value", F.col("min_value") * factor)
    .withColumn("max_value", F.col("max_value") * factor)
    .join(locations, "sensor_id")
)

# shortcut: nearest borough centre, upgrade to a taxi-zone shapefile join for zone-level analysis.
# The second filter drops New Jersey stations that fall inside the bounding box.
def km_to(lat, lon):
    dy = (F.col("latitude") - lat) * 111.0
    dx = (F.col("longitude") - lon) * 84.0  # km per degree of longitude at 40.7° N
    return F.sqrt(dx * dx + dy * dy)

distances = {b: km_to(*c) for b, c in BOROUGH_CENTRES.items()}
nearest = F.least(*distances.values())
borough = F.coalesce(*[F.when(d == nearest, F.lit(b)) for b, d in distances.items()])

air = (
    measurements
    .where(F.col("latitude").isNotNull() & F.col("longitude").isNotNull())
    .where(~((F.col("longitude") < -74.05) & (F.col("latitude") > 40.65)))
    .withColumn("borough", borough)
    .groupBy("date", "location_id", "location_name", "latitude", "longitude", "borough", "pollutant")
    .agg(
        F.avg("value").alias("avg_value"),
        F.min("min_value").alias("min_value"),
        F.max("max_value").alias("max_value"),
        F.sum("measurements").cast("int").alias("measurements"),
    )
)
air.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(OUT)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Checks

# CELL ********************

air = spark.read.format("delta").load(OUT)
n = air.count()
assert n > 0, "air_quality_daily is empty"
assert air.select("date", "location_id", "pollutant").distinct().count() == n, "duplicate (date, location_id, pollutant)"
assert air.where("date IS NULL OR location_id IS NULL OR avg_value < 0").count() == 0, "null keys or negative values"
air.groupBy("pollutant").agg(
    F.count("*").alias("rows"), F.countDistinct("location_id").alias("stations"),
    F.round(F.avg("avg_value"), 2).alias("mean_ugm3"), F.min("date").alias("from"), F.max("date").alias("to"),
).show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
