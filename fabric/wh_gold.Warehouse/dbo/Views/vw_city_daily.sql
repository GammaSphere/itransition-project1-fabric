-- One row per day for the whole city: taxi activity next to pollutant levels (µg/m³).
CREATE VIEW [dbo].[vw_city_daily] AS
WITH taxi AS (
    SELECT
        f.[date_key]           AS [date_key],
        SUM(f.[trips])         AS [trips],
        SUM(f.[total_amount])  AS [total_amount],
        SUM(f.[fare_amount])   AS [fare_amount],
        SUM(f.[trips_night])   AS [trips_night],
        SUM(f.[trips_am_rush]) AS [trips_am_rush],
        SUM(f.[trips_midday])  AS [trips_midday],
        SUM(f.[trips_pm_rush]) AS [trips_pm_rush],
        SUM(f.[trips_evening]) AS [trips_evening]
    FROM [dbo].[FactTaxiDaily] AS f
    GROUP BY f.[date_key]
),
air AS (
    SELECT
        a.[date_key] AS [date_key],
        AVG(CASE WHEN a.[pollutant] = 'pm25' THEN a.[avg_value] END) AS [pm25],
        AVG(CASE WHEN a.[pollutant] = 'no2'  THEN a.[avg_value] END) AS [no2],
        AVG(CASE WHEN a.[pollutant] = 'o3'   THEN a.[avg_value] END) AS [o3]
    FROM [dbo].[FactAirQualityDaily] AS a
    GROUP BY a.[date_key]
)
SELECT
    d.[date]            AS [date],
    d.[date_key]        AS [date_key],
    t.[trips]           AS [trips],
    t.[total_amount]    AS [total_amount],
    CAST(t.[fare_amount] / NULLIF(t.[trips], 0) AS DECIMAL(18, 2)) AS [avg_fare],
    t.[trips_night]     AS [trips_night],
    t.[trips_am_rush]   AS [trips_am_rush],
    t.[trips_midday]    AS [trips_midday],
    t.[trips_pm_rush]   AS [trips_pm_rush],
    t.[trips_evening]   AS [trips_evening],
    a.[pm25]            AS [pm25],
    a.[no2]             AS [no2],
    a.[o3]              AS [o3]
FROM [dbo].[DimDate] AS d
LEFT JOIN taxi AS t ON t.[date_key] = d.[date_key]
LEFT JOIN air  AS a ON a.[date_key] = d.[date_key]
WHERE t.[date_key] IS NOT NULL OR a.[date_key] IS NOT NULL;

GO