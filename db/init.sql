CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Hourly weather for New York City, enriched with that day's taxi trips and pollutant levels.
CREATE TABLE IF NOT EXISTS weather_enriched (
    time                  TIMESTAMPTZ PRIMARY KEY,
    temperature_c         DOUBLE PRECISION,
    precipitation_mm      DOUBLE PRECISION,
    wind_speed_kmh        DOUBLE PRECISION,
    relative_humidity_pct DOUBLE PRECISION,
    trips_day             BIGINT,
    pm25_day              DOUBLE PRECISION,
    no2_day               DOUBLE PRECISION
);

SELECT create_hypertable('weather_enriched', 'time', if_not_exists => TRUE);
