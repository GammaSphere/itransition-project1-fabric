# External integrations

Two integrations run outside Fabric, in Docker, and read the gold layer of the warehouse.

1. **Weather → time-series database → Grafana.** Weather is ingested in Fabric and enriched with
   taxi and air-quality data. A job copies it periodically into TimescaleDB, and a Grafana
   dashboard analyses it.
2. **Data-quality bot.** A Telegram bot runs Great Expectations checks on the gold tables on
   request and replies with a report.

```mermaid
flowchart LR
    OM[Open-Meteo API] -- df_weather --> B[(lh_bronze)]
    B -- nb_silver_weather --> S[(lh_silver)]
    S -- nb_gold_load --> G[(wh_gold<br/>vw_weather_enriched)]
    G -- "weather_sync<br/>every 60 min" --> T[(TimescaleDB)]
    T --> GR[Grafana dashboard]
    G -- "Great Expectations" --> BOT[dq_bot]
    U[You, in Telegram] -- "/quality" --> BOT
    BOT -- "summary + HTML report" --> U
```

## Weather in Fabric

| Item | Role |
|---|---|
| `df_weather` (Dataflow Gen2) | Hourly temperature, precipitation, wind speed and humidity for New York City from the Open-Meteo archive (free, no key), into `lh_bronze.weather_hourly_raw` |
| `nb_silver_weather` | Types and deduplicates into `lh_silver.weather_hourly`; adds the New York calendar day |
| `FactWeatherHourly` | Gold table, one row per hour (UTC) |
| `vw_weather_enriched` | Each weather hour with that day's taxi trips, PM2.5 and NO2 |

Both run as part of `pl_master`. After syncing, open `df_weather` once and confirm the anonymous
web connection, as for the other dataflows.

Taxi data is published about two months late, so `trips_day` is empty for recent hours and is
filled in on a later run.

## Run the stack

Requirements: Docker Desktop.

```bash
cp .env.example .env      # then set POSTGRES_PASSWORD and GRAFANA_ADMIN_PASSWORD
docker compose up -d --build
```

| Service | What it does |
|---|---|
| `timescaledb` | Time-series database with the hypertable `weather_enriched` |
| `weather_sync` | Copies `vw_weather_enriched` into TimescaleDB every `SYNC_INTERVAL_MINUTES` |
| `grafana` | Dashboard at <http://localhost:3000> (user `admin`, password from `.env`) |
| `dq_bot` | Telegram bot; stays off while `TELEGRAM_BOT_TOKEN` is empty |

### Sample mode and Fabric mode

`DATA_SOURCE` in `.env` chooses where the data comes from.

- `sample` (default) reads the small files in `integrations/sample/`. Everything works without
  any Fabric access, which is useful for a demonstration.
- `fabric` reads `wh_gold` with a service principal. Fill in the `FABRIC_*` variables first.

### Connect to Fabric with a service principal

1. In Microsoft Entra ID, register an application and create a client secret. Note the tenant ID,
   client ID and secret.
2. In the Fabric admin portal, enable **Service principals can use Fabric APIs** for that
   application (or a security group containing it).
3. In the workspace, **Manage access** → add the application with the **Viewer** role.
4. Open `wh_gold` → **Settings** → **SQL endpoint** and copy the SQL connection string
   (it ends in `.datawarehouse.fabric.microsoft.com`).
5. In `.env` set `DATA_SOURCE=fabric`, `FABRIC_SQL_ENDPOINT`, `FABRIC_TENANT_ID`,
   `FABRIC_CLIENT_ID` and `FABRIC_CLIENT_SECRET`, then run `docker compose up -d`.

## How the sync works

Every cycle the job reads the rows newer than the latest hour already copied, **minus a lookback
window** (`SYNC_LOOKBACK_DAYS`, default 100), and upserts them by timestamp. The lookback exists
because enrichment arrives late: a weather hour is copied first without taxi trips, and the trip
count for that day appears in the warehouse weeks later. Re-reading the window updates those rows.

If the warehouse or the database is unreachable, the cycle is logged as failed and the job tries
again at the next interval.

## Grafana dashboard

*NYC weather, mobility and air quality* opens as the home dashboard.

| Panel | Shows |
|---|---|
| Latest weather hour loaded, Hours loaded | Whether the sync is keeping up |
| Temperature | Hourly temperature |
| Precipitation per day | Daily rainfall |
| Air quality and temperature | Daily PM2.5 and NO2 against temperature |
| Taxi trips and precipitation | Do people take more taxis when it rains? |
| Wind speed and humidity | Hourly wind and humidity |

Use the time picker to zoom in. The data source and the dashboard are provisioned from
`grafana/provisioning/`, so nothing is configured by hand.

## Data-quality bot

### Set up

1. In Telegram, talk to **@BotFather**, send `/newbot`, and copy the token into
   `TELEGRAM_BOT_TOKEN` in `.env`.
2. Run `docker compose up -d dq_bot`, open your bot and send `/start`. It replies with your chat ID.
3. Put that ID in `TELEGRAM_ALLOWED_CHAT_IDS` (comma-separated for several people) and run
   `docker compose up -d dq_bot` again.

Only chats on the list can run checks; everyone else gets "Not authorised".

### Use

| Command | Result |
|---|---|
| `/quality` | Checks every gold table |
| `/quality FactTaxiDaily` | Checks one table |

The bot replies with a summary — one line per table, then each failed check with what was
observed — and attaches `quality_report.html` with every check of every table.

```
Data quality: 1 of 7 tables have failures ❌

✅ DimDate: 5/5 checks, 1,055 rows
❌ FactTaxiDaily: 9/10 checks, 240,118 rows
…

Failures:
• FactTaxiDaily.date_key — expect_column_values_to_not_be_null — 3 bad rows (0.00%)
```

### What is checked

| Kind | Checks |
|---|---|
| Completeness | Tables are not empty; key columns have no nulls |
| Uniqueness | Keys are unique (`date_key` + `zone_key`, `date_key` + `location_id` + `pollutant`, …) |
| Validity | Trips ≥ 1; amounts ≥ 0; pollutant is one of PM2.5, NO2, O3; values between 0 and 500 µg/m³; FX rate between 0.8 and 1.6; humidity 0–100 % |
| Distribution | Mean revenue per trip between 5 and 150 USD; median trips per zone-day in range; mean PM2.5 between 2 and 35 µg/m³ and its 95th percentile under 100; FX rate actually varies; mean temperature in range |
| Freshness (Fabric mode only) | Newest taxi day within 120 days; newest air-quality day within 14 days |

The checks are defined with Great Expectations in `integrations/dq_bot/suites.py`.

## Tests

```bash
docker compose run --rm -e PG_DSN=postgresql://weather:$POSTGRES_PASSWORD@timescaledb:5432/weather weather_sync python -m pytest integrations/tests -q
```

The tests cover the incremental sync and its lookback window, updates of changed rows, survival of
a failed cycle, every suite on good data and on deliberately broken data, the message length limit,
and the chat allow-list.
