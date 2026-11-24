# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # OpenAQ raw landing
# Calls the OpenAQ v3 API for reference monitors in New York City and lands the raw JSON
# responses in the bronze table `openaq_raw_json`. The dataflow `df_openaq` turns that JSON into
# tables. The API key is read from `lh_bronze/Files/config/openaq_api_key.txt`, which is never in Git.

# PARAMETERS CELL ********************

start_month = "2024-01"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import time
from datetime import date, datetime, timezone

import requests
from pyspark.sql import types as T

def lakehouse_paths(name):
    """(Files path, Tables path) of a lakehouse in the current workspace, found by name."""
    root = notebookutils.lakehouse.get(name)["properties"]["abfsPath"]
    # Schema-enabled lakehouses keep tables under Tables/dbo.
    tables = f"{root}/Tables/dbo" if notebookutils.fs.exists(f"{root}/Tables/dbo") else f"{root}/Tables"
    return f"{root}/Files", tables

API = "https://api.openaq.org/v3"
NYC_BBOX = "-74.26,40.49,-73.70,40.92"  # min lon, min lat, max lon, max lat
POLLUTANTS = {"pm25", "no2", "o3"}
PAGE = 1000

bronze_files, bronze = lakehouse_paths("lh_bronze")
api_key = notebookutils.fs.head(f"{bronze_files}/config/openaq_api_key.txt", 200).strip()
assert api_key, "Upload your OpenAQ key to lh_bronze/Files/config/openaq_api_key.txt"


def call(path, **params):
    """GET with the key header; waits and retries when the rate limit (60/min) is hit."""
    for attempt in range(6):
        try:
            r = requests.get(f"{API}{path}", params=params, headers={"X-API-Key": api_key}, timeout=60)
        except requests.RequestException as error:  # timeout or dropped connection: wait and retry
            last = type(error).__name__
            time.sleep(10 * (attempt + 1))
            continue
        last = f"HTTP {r.status_code}"
        if r.status_code == 429:
            time.sleep(int(r.headers.get("x-ratelimit-reset", 30)) + 1)
        elif r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
        else:
            r.raise_for_status()
            time.sleep(1.1)
            return r
    raise RuntimeError(f"OpenAQ kept failing for {path}: {last}")


def pages(path, **params):
    """Yields (page number, response text, results) until a short page is returned."""
    page = 1
    while True:
        r = call(path, limit=PAGE, page=page, **params)
        results = r.json()["results"]
        yield page, r.text, results
        if len(results) < PAGE:
            return
        page += 1

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

date_from = f"{start_month}-01"
date_to = date.today().isoformat()
fetched_at = datetime.now(timezone.utc)
rows = []  # (kind, sensor_id, page, payload, fetched_at)
sensors = set()

for page, text, results in pages("/locations", bbox=NYC_BBOX, monitor="true"):
    rows.append(("locations", None, page, text, fetched_at))
    for loc in results:
        last = ((loc.get("datetimeLast") or {}).get("utc") or "")[:10]
        if last >= date_from:  # skip stations that stopped reporting before the period
            sensors |= {s["id"] for s in loc["sensors"] if s["parameter"]["name"] in POLLUTANTS}

print(f"{len(sensors)} sensors to fetch from {date_from} to {date_to}")
for sensor_id in sorted(sensors):
    for page, text, _ in pages(f"/sensors/{sensor_id}/days", date_from=date_from, date_to=date_to):
        rows.append(("days", sensor_id, page, text, fetched_at))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

schema = T.StructType([
    T.StructField("kind", T.StringType()),
    T.StructField("sensor_id", T.IntegerType()),
    T.StructField("page", T.IntegerType()),
    T.StructField("payload", T.StringType()),
    T.StructField("fetched_at", T.TimestampType()),
])
assert len(sensors) > 0, "No active NYC sensors found"  # checked before bronze is overwritten
df = spark.createDataFrame(rows, schema)
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{bronze}/openaq_raw_json")

assert df.where("kind = 'days'").count() >= len(sensors)
print(f"Landed {len(rows)} API responses")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
