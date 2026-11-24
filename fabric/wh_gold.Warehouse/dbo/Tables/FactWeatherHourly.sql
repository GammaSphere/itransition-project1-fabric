CREATE TABLE [dbo].[FactWeatherHourly] (
    [ts]                    DATETIME2 (6)  NOT NULL,
    [date_key]              INT            NOT NULL,
    [temperature_c]         DECIMAL (6, 2) NULL,
    [precipitation_mm]      DECIMAL (8, 2) NULL,
    [wind_speed_kmh]        DECIMAL (6, 2) NULL,
    [relative_humidity_pct] DECIMAL (5, 2) NULL
);


GO