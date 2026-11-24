"""Periodically copies enriched weather rows from the Fabric warehouse into TimescaleDB."""
import logging
import os
import time
from datetime import timedelta

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


def sync_once(conn, lookback_days=None):
    """Upserts new rows and re-reads a trailing window; returns the number of rows written.

    Taxi and air-quality figures for a day arrive in the warehouse long after its weather
    (taxi data is published about two months late), so already-copied hours inside the
    lookback window are read again and updated.
    """
    if lookback_days is None:
        lookback_days = int(os.environ.get("SYNC_LOOKBACK_DAYS", "100"))
    latest = conn.execute("SELECT max(time) FROM weather_enriched").fetchone()[0]
    since = None
    if latest is not None:
        since = pd.Timestamp(latest).tz_convert("UTC").tz_localize(None) - timedelta(days=lookback_days)
    df = read_table("vw_weather_enriched", since=since, time_col="ts")
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
    return psycopg.connect(os.environ["PG_DSN"])


def run(connect=connect, sleep=time.sleep, cycles=None):
    """Runs sync_once every SYNC_INTERVAL_MINUTES; a failed cycle is logged and the loop goes on."""
    interval = int(os.environ.get("SYNC_INTERVAL_MINUTES", "60")) * 60
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
