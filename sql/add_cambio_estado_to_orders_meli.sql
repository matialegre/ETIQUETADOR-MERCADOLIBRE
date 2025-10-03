-- Adds CAMBIO_ESTADO column to dbo.orders_meli to flag manual/forced state changes
-- Idempotent: only adds if it doesn't exist

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns c
    JOIN sys.objects o ON o.object_id = c.object_id
    WHERE o.type = 'U' AND o.name = 'orders_meli' AND c.name = 'CAMBIO_ESTADO'
)
BEGIN
    ALTER TABLE dbo.orders_meli ADD CAMBIO_ESTADO INT NOT NULL CONSTRAINT DF_orders_meli_CAMBIO_ESTADO DEFAULT(0);
END
GO

-- Optional: small index if you plan to filter by CAMBIO_ESTADO often
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_CAMBIO_ESTADO' AND object_id = OBJECT_ID('dbo.orders_meli')
)
BEGIN
    CREATE INDEX IX_orders_meli_CAMBIO_ESTADO ON dbo.orders_meli (CAMBIO_ESTADO);
END
GO
