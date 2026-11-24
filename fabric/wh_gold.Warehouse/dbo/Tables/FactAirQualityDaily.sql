CREATE TABLE [dbo].[FactAirQualityDaily] (
    [date_key]      INT             NOT NULL,
    [location_id]   INT             NOT NULL,
    [location_name] VARCHAR (200)   NULL,
    [borough]       VARCHAR (50)    NULL,
    [pollutant]     VARCHAR (10)    NOT NULL,
    [avg_value]     DECIMAL (12, 4) NOT NULL,
    [min_value]     DECIMAL (12, 4) NULL,
    [max_value]     DECIMAL (12, 4) NULL,
    [measurements]  INT             NULL
);


GO