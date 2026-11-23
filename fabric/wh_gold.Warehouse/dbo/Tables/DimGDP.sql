CREATE TABLE [dbo].[DimGDP] (
    [country_code]   CHAR(3)        NOT NULL,
    [year]           INT            NOT NULL,
    [gdp_usd]        DECIMAL(24, 2) NOT NULL,
    [yoy_growth_pct] DECIMAL(9, 4)  NULL
);

GO
