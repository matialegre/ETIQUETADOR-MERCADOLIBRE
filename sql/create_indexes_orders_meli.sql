-- Índices recomendados para acelerar la MEGA API sobre orders_meli (SQL Server)
-- Ejecutar en base meli_stock

USE [meli_stock];
GO

-- Helper: crear índice si no existe
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_id' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE UNIQUE NONCLUSTERED INDEX [IX_orders_meli_id] ON [dbo].[orders_meli]([id] DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_date_created' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_date_created] ON [dbo].[orders_meli]([date_created] DESC) INCLUDE([order_id]);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_date_closed' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_date_closed] ON [dbo].[orders_meli]([date_closed] DESC) INCLUDE([order_id]);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_order_id' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_order_id] ON [dbo].[orders_meli]([order_id]);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_pack_id' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_pack_id] ON [dbo].[orders_meli]([pack_id]);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_sku' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_sku] ON [dbo].[orders_meli]([sku]);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_seller_sku' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_seller_sku] ON [dbo].[orders_meli]([seller_sku]);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_barcode' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_barcode] ON [dbo].[orders_meli]([barcode]);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_deposito_asignado' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_deposito_asignado] ON [dbo].[orders_meli]([deposito_asignado]);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_shipping' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_shipping] ON [dbo].[orders_meli]([shipping_estado],[shipping_subestado]);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_orders_meli_flags' AND object_id = OBJECT_ID('dbo.orders_meli'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_orders_meli_flags] ON [dbo].[orders_meli]([ready_to_print],[printed],[agotamiento_flag]);
END
GO
