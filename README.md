# NYC Mobility, Air Quality and Economy on Microsoft Fabric

A unified analytics platform on Microsoft Fabric. It combines NYC taxi trips, OpenAQ air-quality
measurements, World Bank GDP and ECB exchange rates in a medallion architecture
(Bronze → Silver → Gold) with a Warehouse star schema and notebook dashboards.

Two external integrations build on the gold layer: weather data copied into a time-series
database with a Grafana dashboard, and a Telegram bot that runs Great Expectations data-quality
checks on request.

## Questions it answers

1. How does traffic intensity (trips per day) relate to air quality (PM2.5, NO2) in New York City?
2. Which boroughs or times of day show the strongest link between taxi demand and pollution?
3. What is the average revenue per trip in USD and in EUR, and how does the exchange rate affect it?
4. Over several years, does mobility and economic growth come at the expense of air quality?

## What is in the repository

| Folder | Content |
|---|---|
| [`fabric/`](fabric) | Every Fabric item, in Git-integration format: 2 lakehouses, 1 warehouse, 2 pipelines, 4 dataflows, 9 notebooks |
| [`integrations/`](integrations) | Weather sync job, data-quality bot, sample data and tests (Python) |
| [`grafana/`](grafana), [`db/`](db), `docker-compose.yml` | Grafana dashboard, TimescaleDB schema and the Docker stack |
| [`docs/`](docs) | Setup guide, architecture, data dictionary, lineage, governance, integrations |

| Layer | Item | Content |
|---|---|---|
| Bronze | `lh_bronze` | Monthly taxi Parquet files; raw OpenAQ, ECB and World Bank tables |
| Silver | `lh_silver` | Cleaned trips, daily aggregates, air quality per station, FX per day, GDP per year |
| Gold | `wh_gold` | `FactTaxiDaily`, `FactAirQualityDaily`, `DimDate`, `DimZone`, `DimFX`, `DimGDP`, two reporting views |
| Analytics | `nb_dashboards` | Mobility, air quality, mobility vs air quality, economic impact |

`pl_master` runs the whole chain every day at 06:00.

## Quick start

1. Connect a Fabric workspace to this repository, Git folder `fabric`, and sync.
2. Upload your OpenAQ API key to `lh_bronze/Files/config/openaq_api_key.txt`.
3. Run `pl_master`, then open `nb_dashboards` and run all cells.

Full instructions: [docs/setup.md](docs/setup.md).

To try the external integrations without Fabric access:

```bash
cp .env.example .env      # set the two passwords
docker compose up -d --build
```

Then open Grafana at <http://localhost:3000>. Details: [docs/integrations.md](docs/integrations.md).

## Documentation

- [Setup](docs/setup.md)
- [Architecture and design decisions](docs/architecture.md)
- [Data dictionary](docs/data-dictionary.md)
- [Data lineage](docs/lineage.md)
- [Governance policies](docs/governance.md)
- [External integrations: weather, Grafana, data-quality bot](docs/integrations.md)

## Data sources

- [NYC TLC trip record data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [OpenAQ](https://docs.openaq.org/)
- [World Bank Open Data](https://api.worldbank.org/v2/country/USA/indicator/NY.GDP.MKTP.CD?format=json)
- [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api)
- [European Central Bank data portal](https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata)
