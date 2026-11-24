-- Hourly weather (UTC) enriched with the taxi trips and pollutant levels of the same New York day.
CREATE VIEW [dbo].[vw_weather_enriched] AS
SELECT
    w.[ts]                    AS [ts],
    w.[temperature_c]         AS [temperature_c],
    w.[precipitation_mm]      AS [precipitation_mm],
    w.[wind_speed_kmh]        AS [wind_speed_kmh],
    w.[relative_humidity_pct] AS [relative_humidity_pct],
    c.[trips]                 AS [trips_day],
    c.[pm25]                  AS [pm25_day],
    c.[no2]                   AS [no2_day]
FROM [dbo].[FactWeatherHourly] AS w
LEFT JOIN [dbo].[vw_city_daily] AS c ON c.[date_key] = w.[date_key];

GO