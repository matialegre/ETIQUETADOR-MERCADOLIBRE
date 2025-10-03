/*
Allow admin-forced change of deposito_asignado using SESSION_CONTEXT('ALLOW_DEPO_CHANGE')=1.
Keeps the original protection (write-once) unless the session flag is set.

Usage from app (already implemented):
  EXEC sp_set_session_context N'ALLOW_DEPO_CHANGE', 1;
  UPDATE dbo.orders_meli SET deposito_asignado = @new WHERE id = @id;

Run this against your orders database (e.g., meli_stock) as a user with permission to ALTER TRIGGER.
*/

IF OBJECT_ID(N'dbo.trg_orders_meli_block_depo_change', N'TR') IS NULL
BEGIN
    PRINT 'Creating trigger dbo.trg_orders_meli_block_depo_change...';
END
ELSE
BEGIN
    PRINT 'Altering trigger dbo.trg_orders_meli_block_depo_change...';
END
GO

CREATE OR ALTER TRIGGER dbo.trg_orders_meli_block_depo_change
ON dbo.orders_meli
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- Admin override: if the caller set this session flag, allow the change
    DECLARE @allow_override INT = 0;
    BEGIN TRY
        SELECT @allow_override = CONVERT(INT, SESSION_CONTEXT(N'ALLOW_DEPO_CHANGE'));
    END TRY
    BEGIN CATCH
        SET @allow_override = 0;
    END CATCH;

    IF (@allow_override = 1)
        RETURN;

    -- Protect deposito_asignado: block changes after movement/printed
    IF (UPDATE(deposito_asignado))
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM inserted i
            JOIN deleted d ON i.id = d.id
            WHERE
                ISNULL(d.mov_depo_hecho, 0) = 1
                OR ISNULL(d.printed, 0) = 1
                OR ISNULL(NULLIF(LTRIM(RTRIM(d.numero_movimiento)), ''), '') <> ''
                OR ISNULL(NULLIF(LTRIM(RTRIM(d.mov_depo_numero)), ''), '') <> ''
        )
        BEGIN
            THROW 50000, 'deposito_asignado cannot be changed after movement/printed', 1;
        END
    END
END
GO
