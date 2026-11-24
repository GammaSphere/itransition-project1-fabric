# Data dictionary

Every table in the three layers, with the item that produces it.

## Bronze — `lh_bronze`

Raw data as delivered by the source. Nothing is cleaned here.

### Files

| Path | Source | Produced by |
|---|---|---|
| `Files/taxi/yellow_tripdata_YYYY-MM.parquet` | NYC TLC trip records, one file per month | `pl_ingest_taxi` |
| `Files/taxi/taxi_zone_lookup.csv` | NYC TLC taxi zone lookup | `pl_ingest_taxi` |
| `Files/config/openaq_api_key.txt` | OpenAQ API key, uploaded by hand, never in Git | — |

### `ecb_fx_raw` — `df_ecb_fx`

| Column | Type | Meaning |
|---|---|---|
| `TIME_PERIOD` | string | Business day, `YYYY-MM-DD` |
| `OBS_VALUE` | string | ECB reference rate: US dollars per 1 euro |

### `worldbank_gdp_raw` — `df_worldbank_gdp`

| Column | Type | Meaning |
|---|---|---|
| `country_code` | string | ISO 3166-1 alpha-3 code (`USA`) |
| `year` | long | Calendar year |
| `value` | double | GDP in current US dollars (indicator `NY.GDP.MKTP.CD`); null when not yet published |

### `openaq_raw_json` — `nb_openaq_raw`

One row per OpenAQ API response page.

| Column | Type | Meaning |
|---|---|---|
| `kind` | string | `locations` or `days` |
| `sensor_id` | int | Sensor the page belongs to (`days` only) |
| `page` | int | Page number of the paginated call |
| `payload` | string | The JSON response body, unchanged |
| `fetched_at` | timestamp | When the call was made (UTC) |

### `openaq_locations_raw` — `df_openaq`

One row per sensor of each reference monitoring station inside the New York City bounding box.

| Column | Type | Meaning |
|---|---|---|
| `location_id` | long | OpenAQ location (station) ID |
| `location_name` | string | Station name |
| `latitude`, `longitude` | double | Station coordinates |
| `sensor_id` | long | OpenAQ sensor ID |
| `parameter_name` | string | Pollutant measured (`pm25`, `no2`, `o3`, others) |
| `units` | string | Unit reported by the sensor (`µg/m³`, `ppm`, `ppb`) |

### `openaq_daily_raw` — `df_openaq`

| Column | Type | Meaning |
|---|---|---|
| `sensor_id` | long | OpenAQ sensor ID |
| `day` | string | Local day of the measurement period, `YYYY-MM-DD` |
| `value` | double | Daily average in the sensor's unit |
| `min_value`, `max_value` | double | Lowest and highest reading of the day |
| `measurements` | long | Number of readings observed that day |
| `parameter_name` | string | Pollutant |
| `units` | string | Unit of the values |

### `weather_hourly_raw` — `df_weather`

| Column | Type | Meaning |
|---|---|---|
| `ts` | string | Hour, UTC, `YYYY-MM-DDTHH:MM` |
| `temperature_c` | double | Air temperature at 2 m, °C |
| `precipitation_mm` | double | Rain and snow in the hour, mm |
| `wind_speed_kmh` | double | Wind speed at 10 m, km/h |
| `relative_humidity_pct` | double | Relative humidity at 2 m, % |

## Silver — `lh_silver`

Cleaned, typed, deduplicated and conformed.

### `taxi_trips` — `nb_silver_taxi`

One row per valid trip, partitioned by `trip_month`. A trip is kept when the pickup falls in the
file's month, the drop-off is after the pickup, distance and fare are positive, and it lasts at
most 12 hours. Exact duplicates are removed.

| Column | Type | Meaning |
|---|---|---|
| `pickup_ts`, `dropoff_ts` | timestamp | Meter on / off, New York local time |
| `pickup_zone_id`, `dropoff_zone_id` | int | TLC taxi zone IDs |
| `passenger_count` | int | Passengers reported by the driver |
| `trip_distance` | double | Miles |
| `fare_amount` | double | Metered fare, USD |
| `total_amount` | double | Total charged including taxes, tolls, surcharges and card tips, USD |
| `duration_min` | double | Trip length in minutes |
| `trip_date` | date | Pickup date |
| `pickup_hour` | int | Pickup hour, 0–23 |
| `trip_month` | string | `YYYY-MM`, partition column |

### `taxi_daily_zone` — `nb_silver_taxi`

One row per day and pickup zone.

| Column | Type | Meaning |
|---|---|---|
| `trip_date` | date | Pickup date |
| `zone_id` | int | Pickup zone |
| `trips` | long | Number of trips |
| `fare_amount`, `total_amount` | double | Sums, USD |
| `trip_distance` | double | Sum, miles |
| `avg_duration_min` | double | Average trip length |
| `passengers` | long | Sum of passenger counts |
| `trips_night` | long | Pickups 00:00–05:59 |
| `trips_am_rush` | long | Pickups 06:00–09:59 |
| `trips_midday` | long | Pickups 10:00–15:59 |
| `trips_pm_rush` | long | Pickups 16:00–19:59 |
| `trips_evening` | long | Pickups 20:00–23:59 |

### `taxi_zones` — `nb_silver_taxi`

| Column | Type | Meaning |
|---|---|---|
| `zone_id` | int | TLC LocationID (1–265) |
| `zone` | string | Zone name |
| `borough` | string | Borough, or `EWR` / `Unknown` / `N/A` |
| `service_zone` | string | TLC service zone |

### `air_quality_daily` — `nb_silver_air_quality`

One row per day, station and pollutant. All values are in µg/m³: gases reported in ppm or ppb are
converted at 25 °C and 1 atm (µg/m³ = ppb × molecular weight / 24.45). Negative readings are
dropped. Stations in New Jersey are excluded.

| Column | Type | Meaning |
|---|---|---|
| `date` | date | Local day |
| `location_id` | long | OpenAQ station ID |
| `location_name` | string | Station name |
| `latitude`, `longitude` | double | Station coordinates |
| `borough` | string | Borough whose centre is nearest to the station |
| `pollutant` | string | `pm25`, `no2` or `o3` |
| `avg_value` | double | Daily average |
| `min_value`, `max_value` | double | Daily minimum and maximum |
| `measurements` | int | Readings behind the average |

### `fx_daily` — `nb_silver_economy`

One row per calendar day. Weekends and holidays carry the last published rate forward.

| Column | Type | Meaning |
|---|---|---|
| `date` | date | Calendar day |
| `usd_per_eur` | double | US dollars per 1 euro |
| `eur_per_usd` | double | Euros per 1 US dollar |
| `is_filled` | boolean | True when the rate was carried forward |

### `gdp_yearly` — `nb_silver_economy`

| Column | Type | Meaning |
|---|---|---|
| `country_code` | string | ISO alpha-3 code |
| `year` | int | Calendar year |
| `gdp_usd` | double | GDP, current USD |
| `yoy_growth_pct` | double | Growth over the previous year, percent |

### `weather_hourly` — `nb_silver_weather`

One row per hour for New York City (Open-Meteo, latitude 40.7128, longitude −74.0060).

| Column | Type | Meaning |
|---|---|---|
| `ts` | timestamp | Hour, UTC |
| `temperature_c`, `precipitation_mm`, `wind_speed_kmh`, `relative_humidity_pct` | double | As in bronze |
| `local_date` | date | New York calendar day of the hour |

## Gold — `wh_gold` (star schema)

Loaded by `nb_gold_load`. Every table is fully reloaded on each run.

### `DimDate`

| Column | Type | Meaning |
|---|---|---|
| `date_key` | int | `YYYYMMDD`, key |
| `date` | date | Calendar day |
| `year`, `quarter`, `month`, `day` | int | Date parts |
| `weekday` | int | 1 = Monday … 7 = Sunday |
| `weekday_name` | varchar | Day name |
| `is_weekend` | bit | Saturday or Sunday |

### `DimZone`

| Column | Type | Meaning |
|---|---|---|
| `zone_key` | int | TLC LocationID, key |
| `zone`, `borough`, `service_zone` | varchar | As in `taxi_zones` |

### `DimFX`

| Column | Type | Meaning |
|---|---|---|
| `date_key` | int | Key, joins to `DimDate` |
| `usd_per_eur`, `eur_per_usd` | decimal(18,6) | Exchange rate both ways |
| `is_filled` | bit | Rate carried forward from the last business day |

### `DimGDP`

| Column | Type | Meaning |
|---|---|---|
| `country_code` | char(3) | Key part |
| `year` | int | Key part, joins to `DimDate.year` |
| `gdp_usd` | decimal(24,2) | GDP, current USD |
| `yoy_growth_pct` | decimal(9,4) | Year-over-year growth, percent |

### `FactTaxiDaily`

Grain: one row per day and pickup zone.

| Column | Type | Meaning |
|---|---|---|
| `date_key` | int | → `DimDate` |
| `zone_key` | int | → `DimZone` |
| `trips` | bigint | Trips |
| `fare_amount`, `total_amount` | decimal(18,2) | Sums, USD |
| `trip_distance` | decimal(18,2) | Sum, miles |
| `avg_duration_min` | decimal(9,2) | Average trip length |
| `passengers` | bigint | Sum of passengers |
| `trips_night` … `trips_evening` | bigint | Trips per time-of-day band |

### `FactAirQualityDaily`

Grain: one row per day, station and pollutant. Values in µg/m³.

| Column | Type | Meaning |
|---|---|---|
| `date_key` | int | → `DimDate` |
| `location_id` | int | OpenAQ station ID |
| `location_name` | varchar | Station name |
| `borough` | varchar | Nearest borough, joins to `DimZone.borough` |
| `pollutant` | varchar | `pm25`, `no2`, `o3` |
| `avg_value`, `min_value`, `max_value` | decimal(12,4) | Daily average, minimum, maximum |
| `measurements` | int | Readings behind the average |

### `FactWeatherHourly`

Grain: one row per hour.

| Column | Type | Meaning |
|---|---|---|
| `ts` | datetime2 | Hour, UTC |
| `date_key` | int | New York calendar day → `DimDate` |
| `temperature_c` | decimal(6,2) | °C |
| `precipitation_mm` | decimal(8,2) | mm in the hour |
| `wind_speed_kmh` | decimal(6,2) | km/h |
| `relative_humidity_pct` | decimal(5,2) | % |

### Views

| View | Grain | Content |
|---|---|---|
| `vw_city_daily` | day | City-wide trips, revenue, average fare, trips per time band, and mean PM2.5 / NO2 / O3 across stations |
| `vw_weather_enriched` | hour | Weather of the hour with that day's city-wide taxi trips, PM2.5 and NO2; copied to TimescaleDB by the external sync job |
| `vw_revenue_usd_eur` | day | Trips, revenue in USD and EUR, average revenue per trip in both currencies, and the day's rate |
