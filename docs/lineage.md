# Data lineage

How data moves from each source to the dashboards, and which Fabric item performs each step.

```mermaid
flowchart LR
    subgraph Sources
        TLC[NYC TLC<br/>monthly Parquet + zone CSV]
        OAQ[OpenAQ API v3]
        ECB[ECB FX API<br/>CSV]
        WB[World Bank API<br/>JSON]
    end

    subgraph Bronze["Bronze — lh_bronze"]
        B1[Files/taxi/*.parquet<br/>taxi_zone_lookup.csv]
        B2[openaq_raw_json]
        B3[openaq_locations_raw<br/>openaq_daily_raw]
        B4[ecb_fx_raw]
        B5[worldbank_gdp_raw]
    end

    subgraph Silver["Silver — lh_silver"]
        S1[taxi_trips]
        S2[taxi_daily_zone]
        S3[taxi_zones]
        S4[air_quality_daily]
        S5[fx_daily]
        S6[gdp_yearly]
    end

    subgraph Gold["Gold — wh_gold"]
        G1[FactTaxiDaily]
        G2[FactAirQualityDaily]
        G3[DimDate]
        G4[DimZone]
        G5[DimFX]
        G6[DimGDP]
        V1[vw_city_daily]
        V2[vw_revenue_usd_eur]
    end

    TLC -- "pl_ingest_taxi<br/>(Copy)" --> B1
    OAQ -- "nb_openaq_raw" --> B2
    B2 -- "df_openaq" --> B3
    ECB -- "df_ecb_fx" --> B4
    WB -- "df_worldbank_gdp" --> B5

    B1 -- "nb_silver_taxi" --> S1 --> S2
    B1 -- "nb_silver_taxi" --> S3
    B3 -- "nb_silver_air_quality" --> S4
    B4 -- "nb_silver_economy" --> S5
    B5 -- "nb_silver_economy" --> S6

    S2 -- "nb_gold_load" --> G1
    S4 -- "nb_gold_load" --> G2
    S2 & S4 -- "nb_gold_load" --> G3
    S3 -- "nb_gold_load" --> G4
    S5 -- "nb_gold_load" --> G5
    S6 -- "nb_gold_load" --> G6

    G1 & G2 & G3 --> V1
    G1 & G3 & G5 --> V2
    V1 & V2 & G1 & G2 & G4 & G6 --> D[nb_dashboards]
```

## Orchestration

`pl_master` runs the whole chain once a day at 06:00.

```mermaid
flowchart LR
    A[Ingest taxi<br/>pl_ingest_taxi] --> B[Land OpenAQ raw<br/>nb_openaq_raw]
    B --> W[Land weather raw<br/>nb_weather_raw]
    W --> C1[Refresh df_openaq]
    W --> C2[Refresh df_ecb_fx]
    W --> C3[Refresh df_worldbank_gdp]
    W --> C4[Refresh df_weather]
    C1 & C2 & C3 & C4 --> D[Silver taxi]
    D --> E[Silver air quality]
    E --> F[Silver economy]
    F --> H[Silver weather]
    H --> G[Gold load]
```

Each step starts only when the previous one succeeded, so a failure stops the run and leaves the
gold layer as it was after the last good run.

## Column-level lineage of the key measures

| Gold column | Derived from |
|---|---|
| `FactTaxiDaily.trips` | Count of rows in `taxi_trips` per `trip_date` and `pickup_zone_id` |
| `FactTaxiDaily.total_amount` | Sum of TLC `total_amount` |
| `FactTaxiDaily.trips_<band>` | Count of trips whose `tpep_pickup_datetime` hour falls in the band |
| `FactAirQualityDaily.avg_value` | OpenAQ daily `value` per sensor, converted to µg/m³, averaged over the station's sensors of that pollutant |
| `FactAirQualityDaily.borough` | Station `coordinates`, nearest borough centre |
| `DimFX.usd_per_eur` | ECB `OBS_VALUE`, carried forward over non-business days |
| `DimGDP.yoy_growth_pct` | World Bank `value` against the previous year |
| `vw_revenue_usd_eur.revenue_eur` | `FactTaxiDaily.total_amount` × `DimFX.eur_per_usd` of the same day |

The weather flow and the external integrations that read the gold layer are shown in
[integrations.md](integrations.md).

Microsoft Purview lineage is optional in the assignment and is not enabled. The workspace
**Lineage view** in Fabric shows the same item-level graph automatically.
