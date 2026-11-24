"""Reads gold tables either from the Fabric warehouse or from the committed sample files."""
import os
from decimal import Decimal
from pathlib import Path

import pandas as pd

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample"

# Names are interpolated into SQL, so only these are accepted.
TABLES = {
    "DimDate", "DimZone", "DimFX", "DimGDP",
    "FactTaxiDaily", "FactAirQualityDaily", "vw_weather_enriched",
}


def read_table(name, since=None, time_col=None):
    """Returns a table as a DataFrame; with `since` and `time_col`, only rows newer than `since`."""
    if name not in TABLES:
        raise ValueError(f"Unknown table '{name}'. Known tables: {', '.join(sorted(TABLES))}")
    if os.environ.get("DATA_SOURCE", "sample") == "sample":
        df = pd.read_csv(SAMPLE_DIR / f"{name}.csv", parse_dates=[time_col] if time_col else None)
        return df[df[time_col] > since].reset_index(drop=True) if since is not None else df
    return _read_fabric(name, since, time_col)


def _read_fabric(name, since, time_col):
    import mssql_python  # imported here so sample mode needs no SQL driver

    env = os.environ
    conn = mssql_python.connect(
        f"Server={env['FABRIC_SQL_ENDPOINT']};Database={env['FABRIC_WAREHOUSE']};"
        "Authentication=ActiveDirectoryServicePrincipal;"
        f"UID={env['FABRIC_CLIENT_ID']}@{env['FABRIC_TENANT_ID']};PWD={env['FABRIC_CLIENT_SECRET']};Encrypt=yes;"
    )
    try:
        cursor = conn.cursor()
        if since is not None:
            cursor.execute(f"SELECT * FROM dbo.[{name}] WHERE [{time_col}] > ?", since)
        else:
            cursor.execute(f"SELECT * FROM dbo.[{name}]")
        columns = [c[0] for c in cursor.description]
        df = pd.DataFrame.from_records([tuple(r) for r in cursor.fetchall()], columns=columns)
    finally:
        conn.close()
    for column in df.columns:  # SQL decimals arrive as Decimal objects; the checks need floats
        if df[column].map(lambda v: isinstance(v, Decimal)).any():
            df[column] = df[column].astype(float)
    return df
