"""Periodically copies enriched weather rows from the Fabric warehouse into TimescaleDB."""
import logging
import os
import time

import pandas as pd
import psycopg

from integrations.common.reader import read_table

log = logging.getLogger("weather_sync")

COLUMNS = [
    "time", "temperature_c", "precipitation_mm", "wind_speed_kmh",
    "relative_humidity_pct", "trips_day", "pm25_day", "no2_day",
]
UPSERT = (
    f"INSERT INTO weather_enriched ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))}) "
    "ON CONFLICT (time) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS[1:])
)


def sync_once(conn):
    """Upserts every row of the enriched weather view; returns the number of rows written.

    The whole view is re-read each cycle (about 9,000 hourly rows per year). Taxi figures for a
    day arrive in the warehouse months after its weather, so rows already copied must be updated,
    and a full upsert cannot miss any of them.
    """
    df = read_table("vw_weather_enriched")
    if df.empty:
        return 0
    df = df.rename(columns={"ts": "time"})
    df["time"] = pd.to_datetime(df["time"]).dt.tz_localize("UTC")  # the warehouse stores UTC without a zone
    rows = [
        tuple(None if pd.isna(v) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v) for v in row)
        for row in df[COLUMNS].astype(object).itertuples(index=False)
    ]
    with conn.cursor() as cur:
        cur.executemany(UPSERT, rows)
    conn.commit()
    return len(rows)


def connect():
    return psycopg.connect()  # host, user, password and database come from the PG* variables


def run(connect=connect, sleep=time.sleep, cycles=None):
    """Runs sync_once every SYNC_INTERVAL_MINUTES; a failed cycle is logged and the loop goes on."""
    interval = int(os.environ.get("SYNC_INTERVAL_MINUTES") or 60) * 60
    done = 0
    while cycles is None or done < cycles:
        try:
            with connect() as conn:
                log.info("synced %d rows", sync_once(conn))
        except Exception:
            log.exception("sync failed, retrying in %d s", interval)
        done += 1
        if cycles is None or done < cycles:
            sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run()
