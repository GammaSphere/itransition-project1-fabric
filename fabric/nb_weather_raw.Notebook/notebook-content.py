# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # Weather raw landing
# Calls the Open-Meteo archive API for hourly New York City weather and lands the raw JSON
# responses in the bronze table `weather_raw_json`, one row per calendar year. The dataflow
# `df_weather` turns that JSON into the table `weather_hourly_raw`.

# PARAMETERS CELL ********************

start_month = "2024-01"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import time
from datetime import date, datetime, timedelta, timezone

import requests
from pyspark.sql import types as T

def lakehouse_paths(name):
    """(Files path, Tables path) of a lakehouse in the current workspace, found by name."""
    root = notebookutils.lakehouse.get(name)["properties"]["abfsPath"]
    # Schema-enabled lakehouses keep tables under Tables/dbo.
    tables = f"{root}/Tables/dbo" if notebookutils.fs.exists(f"{root}/Tables/dbo") else f"{root}/Tables"
    return f"{root}/Files", tables

API = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = "temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m"

_, bronze = lakehouse_paths("lh_bronze")


def fetch(start, end):
    """One request for a date range; a failure reports the HTTP status and the response body."""
    params = {
        "latitude": 40.7128, "longitude": -74.0060, "start_date": start, "end_date": end,
        "hourly": VARIABLES, "timezone": "GMT",
    }
    for attempt in range(4):
        try:
            r = requests.get(API, params=params, timeout=120)
        except requests.RequestException as error:  # timeout or dropped connection: wait and retry
            last = type(error).__name__
        else:
            if r.status_code == 200:
                return r.text
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"Open-Meteo failed for {start}..{end}: {last}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

first = date.fromisoformat(f"{start_month}-01")
last = date.today() - timedelta(days=6)  # the archive is about five days behind
fetched_at = datetime.now(timezone.utc)
rows = []  # (year, payload, fetched_at)
for year in range(first.year, last.year + 1):
    start = max(first, date(year, 1, 1))
    end = min(last, date(year, 12, 31))
    rows.append((year, fetch(start.isoformat(), end.isoformat()), fetched_at))
    print(f"{year}: {start} to {end}, {len(rows[-1][1]):,} characters")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

schema = T.StructType([
    T.StructField("year", T.IntegerType()),
    T.StructField("payload", T.StringType()),
    T.StructField("fetched_at", T.TimestampType()),
])
assert rows, "start_month is in the future"
spark.createDataFrame(rows, schema).write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{bronze}/weather_raw_json")
print(f"Landed {len(rows)} API responses")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
