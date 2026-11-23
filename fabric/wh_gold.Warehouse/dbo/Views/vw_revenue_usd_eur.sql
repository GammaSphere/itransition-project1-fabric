-- Daily taxi revenue in USD and converted to EUR with that day's ECB reference rate.
CREATE VIEW [dbo].[vw_revenue_usd_eur] AS
WITH taxi AS (
    SELECT
        f.[date_key]          AS [date_key],
        SUM(f.[trips])        AS [trips],
        SUM(f.[total_amount]) AS [revenue_usd]
    FROM [dbo].[FactTaxiDaily] AS f
    GROUP BY f.[date_key]
)
SELECT
    d.[date]          AS [date],
    d.[date_key]      AS [date_key],
    t.[trips]         AS [trips],
    t.[revenue_usd]   AS [revenue_usd],
    CAST(t.[revenue_usd] * x.[eur_per_usd] AS DECIMAL(18, 2)) AS [revenue_eur],
    CAST(t.[revenue_usd] / NULLIF(t.[trips], 0) AS DECIMAL(18, 2)) AS [avg_revenue_per_trip_usd],
    CAST(t.[revenue_usd] * x.[eur_per_usd] / NULLIF(t.[trips], 0) AS DECIMAL(18, 2)) AS [avg_revenue_per_trip_eur],
    x.[usd_per_eur]   AS [usd_per_eur]
FROM taxi AS t
JOIN [dbo].[DimDate] AS d ON d.[date_key] = t.[date_key]
LEFT JOIN [dbo].[DimFX] AS x ON x.[date_key] = t.[date_key];

GO
