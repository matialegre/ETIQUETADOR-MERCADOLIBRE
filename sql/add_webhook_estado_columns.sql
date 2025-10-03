-- Adds columns to record shipping estado before/after webhook-driven updates
-- Safe to run multiple times

IF COL_LENGTH('dbo.orders_meli', 'WEBHOOK_ESTADO_ANTES') IS NULL
BEGIN
    ALTER TABLE dbo.orders_meli
    ADD WEBHOOK_ESTADO_ANTES NVARCHAR(64) NULL;
END
GO

IF COL_LENGTH('dbo.orders_meli', 'WEBHOOK_ESTADO_DESPUES') IS NULL
BEGIN
    ALTER TABLE dbo.orders_meli
    ADD WEBHOOK_ESTADO_DESPUES NVARCHAR(64) NULL;
END
GO

-- Optional: if you also want to track substatus, uncomment below
--IF COL_LENGTH('dbo.orders_meli', 'WEBHOOK_SUBESTADO_ANTES') IS NULL
--BEGIN
--    ALTER TABLE dbo.orders_meli
--    ADD WEBHOOK_SUBESTADO_ANTES NVARCHAR(64) NULL;
--END
--GO
--
--IF COL_LENGTH('dbo.orders_meli', 'WEBHOOK_SUBESTADO_DESPUES') IS NULL
--BEGIN
--    ALTER TABLE dbo.orders_meli
--    ADD WEBHOOK_SUBESTADO_DESPUES NVARCHAR(64) NULL;
--END
--GO
