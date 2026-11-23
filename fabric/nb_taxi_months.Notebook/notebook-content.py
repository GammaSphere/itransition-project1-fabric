# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # Taxi months to ingest
# Returns the yellow-taxi months that are published by TLC and not yet landed in `lh_bronze/Files/taxi`.
# The pipeline `pl_ingest_taxi` copies one Parquet file per month in the returned list.

# PARAMETERS CELL ********************

start_month = "2024-01"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json
import re
from datetime import date

import requests

def lakehouse_paths(name):
    """(Files path, Tables path) of a lakehouse in the current workspace, found by name."""
    root = notebookutils.lakehouse.get(name)["properties"]["abfsPath"]
    # Schema-enabled lakehouses keep tables under Tables/dbo.
    tables = f"{root}/Tables/dbo" if notebookutils.fs.exists(f"{root}/Tables/dbo") else f"{root}/Tables"
    return f"{root}/Files", tables

SOURCE = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{}.parquet"

bronze_files, _ = lakehouse_paths("lh_bronze")
taxi_dir = f"{bronze_files}/taxi"
landed = {f.name for f in notebookutils.fs.ls(taxi_dir)} if notebookutils.fs.exists(taxi_dir) else set()

year, month = map(int, start_month.split("-"))
today = date.today()
candidates = []
while (year, month) <= (today.year, today.month):
    candidates.append(f"{year}-{month:02d}")
    year, month = (year + 1, 1) if month == 12 else (year, month + 1)

# TLC publishes with a ~2 month lag; unpublished months answer 403, so only existing files are returned.
todo = [
    m for m in candidates
    if f"yellow_tripdata_{m}.parquet" not in landed
    and requests.head(SOURCE.format(m), timeout=30).status_code == 200
]
assert all(re.fullmatch(r"\d{4}-\d{2}", m) for m in todo)
print(f"{len(landed)} files already landed, {len(todo)} to copy: {todo}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

notebookutils.notebook.exit(json.dumps(todo))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
