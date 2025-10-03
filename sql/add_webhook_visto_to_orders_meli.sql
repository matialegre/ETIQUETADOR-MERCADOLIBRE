-- Adds a flag column to mark rows updated as a result of webhook processing
-- Safe to run multiple times: checks for column existence

IF COL_LENGTH('dbo.orders_meli', 'WEBHOOK_VISTO') IS NULL
BEGIN
    ALTER TABLE dbo.orders_meli
    ADD WEBHOOK_VISTO BIT NOT NULL CONSTRAINT DF_orders_meli_WEBHOOK_VISTO DEFAULT (0);
END
GO

-- Optional helpful index if you plan to query by this flag often
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_WEBHOOK_VISTO' AND object_id = OBJECT_ID('dbo.orders_meli')
)
BEGIN
    CREATE INDEX IX_orders_meli_WEBHOOK_VISTO ON dbo.orders_meli(WEBHOOK_VISTO) INCLUDE(order_id, shipping_subestado, date_created);
END
GO
