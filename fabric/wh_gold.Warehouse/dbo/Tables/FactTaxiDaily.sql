CREATE TABLE [dbo].[FactTaxiDaily] (
    [date_key]         INT            NOT NULL,
    [zone_key]         INT            NOT NULL,
    [trips]            BIGINT         NOT NULL,
    [fare_amount]      DECIMAL(18, 2) NOT NULL,
    [total_amount]     DECIMAL(18, 2) NOT NULL,
    [trip_distance]    DECIMAL(18, 2) NOT NULL,
    [avg_duration_min] DECIMAL(9, 2)  NULL,
    [passengers]       BIGINT         NULL,
    [trips_night]      BIGINT         NOT NULL,
    [trips_am_rush]    BIGINT         NOT NULL,
    [trips_midday]     BIGINT         NOT NULL,
    [trips_pm_rush]    BIGINT         NOT NULL,
    [trips_evening]    BIGINT         NOT NULL
);

GO
