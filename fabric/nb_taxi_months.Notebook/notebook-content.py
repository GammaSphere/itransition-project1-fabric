# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# CELL ********************

# Setup check: resolves both lakehouses by name in the current workspace.
bronze = notebookutils.lakehouse.get("lh_bronze")["properties"]["abfsPath"]
silver = notebookutils.lakehouse.get("lh_silver")["properties"]["abfsPath"]
print(bronze)
print(silver)
print(notebookutils.fs.ls(f"{bronze}/Files"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
