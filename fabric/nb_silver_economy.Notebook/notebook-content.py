# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # Silver: economy
# Bronze ECB and World Bank tables → `fx_daily` (one USD/EUR rate per calendar day, weekends and
# holidays forward-filled) and `gdp_yearly` (GDP in USD with year-over-year growth) in `lh_silver`.

# CELL ********************

from pyspark.sql import Window
from pyspark.sql import functions as F

def lakehouse_paths(name):
    """(Files path, Tables path) of a lakehouse in the current workspace, found by name."""
    root = notebookutils.lakehouse.get(name)["properties"]["abfsPath"]
    # Schema-enabled lakehouses keep tables under Tables/dbo.
    tables = f"{root}/Tables/dbo" if notebookutils.fs.exists(f"{root}/Tables/dbo") else f"{root}/Tables"
    return f"{root}/Files", tables

_, bronze = lakehouse_paths("lh_bronze")
_, silver = lakehouse_paths("lh_silver")
FX, GDP = f"{silver}/fx_daily", f"{silver}/gdp_yearly"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Daily FX
# The ECB publishes rates on business days only. A full calendar is built and the last known
# rate is carried forward, so every taxi date can be converted to EUR.

# CELL ********************

rates = (
    spark.read.format("delta").load(f"{bronze}/ecb_fx_raw")
    .select(F.to_date(F.col("TIME_PERIOD").cast("string")).alias("date"), F.col("OBS_VALUE").cast("double").alias("rate"))
    .where("date IS NOT NULL AND rate > 0")
    .dropDuplicates(["date"])
)
calendar = rates.agg(F.min("date").alias("lo"), F.max("date").alias("hi")).select(
    F.explode(F.sequence("lo", "hi")).alias("date")
)
# One global window: the table has about 10,000 rows.
carry = Window.orderBy("date").rowsBetween(Window.unboundedPreceding, Window.currentRow)
fx = (
    calendar.join(rates, "date", "left")
    .withColumn("is_filled", F.col("rate").isNull())
    .withColumn("usd_per_eur", F.last("rate", ignorenulls=True).over(carry))
    .withColumn("eur_per_usd", 1 / F.col("usd_per_eur"))
    .select("date", "usd_per_eur", "eur_per_usd", "is_filled")
)
fx.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(FX)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Yearly GDP

# CELL ********************

by_year = Window.partitionBy("country_code").orderBy("year")
gdp = (
    spark.read.format("delta").load(f"{bronze}/worldbank_gdp_raw")
    .select(F.col("country_code"), F.col("year").cast("int").alias("year"), F.col("value").cast("double").alias("gdp_usd"))
    .where("gdp_usd IS NOT NULL AND country_code IS NOT NULL")
    .dropDuplicates(["country_code", "year"])
    .withColumn("yoy_growth_pct", (F.col("gdp_usd") / F.lag("gdp_usd").over(by_year) - 1) * 100)
)
gdp.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(GDP)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Checks

# CELL ********************

fx = spark.read.format("delta").load(FX)
span = fx.agg(F.datediff(F.max("date"), F.min("date")) + 1).first()[0]
assert fx.count() == span, "fx_daily must have exactly one row per calendar day"
assert fx.where("usd_per_eur IS NULL OR usd_per_eur < 0.5 OR usd_per_eur > 2.0").count() == 0, "FX rate out of range"
gdp = spark.read.format("delta").load(GDP)
assert gdp.count() > 0, "gdp_yearly is empty"
assert gdp.select("country_code", "year").distinct().count() == gdp.count(), "duplicate (country_code, year)"
print(f"fx_daily: {fx.count():,} days; gdp_yearly: {gdp.count()} years")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
