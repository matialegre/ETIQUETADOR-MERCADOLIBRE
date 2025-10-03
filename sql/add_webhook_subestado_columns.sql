-- Adds columns to record shipping subestado before/after webhook-driven updates
-- Safe to run multiple times

IF COL_LENGTH('dbo.orders_meli', 'WEBHOOK_SUBESTADO_ANTES') IS NULL
BEGIN
    ALTER TABLE dbo.orders_meli
    ADD WEBHOOK_SUBESTADO_ANTES NVARCHAR(64) NULL;
END
GO

IF COL_LENGTH('dbo.orders_meli', 'WEBHOOK_SUBESTADO_DESPUES') IS NULL
BEGIN
    ALTER TABLE dbo.orders_meli
    ADD WEBHOOK_SUBESTADO_DESPUES NVARCHAR(64) NULL;
END
GO
