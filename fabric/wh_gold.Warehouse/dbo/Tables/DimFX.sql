CREATE TABLE [dbo].[DimFX] (
    [date_key]    INT            NOT NULL,
    [usd_per_eur] DECIMAL(18, 6) NOT NULL,
    [eur_per_usd] DECIMAL(18, 6) NOT NULL,
    [is_filled]   BIT            NOT NULL
);

GO
