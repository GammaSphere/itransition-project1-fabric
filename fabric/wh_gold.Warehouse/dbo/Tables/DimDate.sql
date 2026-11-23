CREATE TABLE [dbo].[DimDate] (
    [date_key]     INT         NOT NULL,
    [date]         DATE        NOT NULL,
    [year]         INT         NOT NULL,
    [quarter]      INT         NOT NULL,
    [month]        INT         NOT NULL,
    [day]          INT         NOT NULL,
    [weekday]      INT         NOT NULL,
    [weekday_name] VARCHAR(10) NOT NULL,
    [is_weekend]   BIT         NOT NULL
);

GO
