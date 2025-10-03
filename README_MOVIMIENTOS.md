# Contador diario de movimientos y regla MUNDOCAB

Este documento describe los cambios recientes para:

- Contar paquetes con movimiento real por día (excluye reimpresiones).
- Persistir y exponer el conteo vía endpoints en el backend.
- Sellar timestamp de movimiento (`mov_depo_ts`) idempotente.
- Forzar depósito `MUNDOCAB` para el seller de MercadoLibre `756086955` y publicarlo en la nota.

---

## 1) Base de datos

Tabla: `dbo.orders_meli`

- Campo nuevo recomendado: `mov_depo_ts DATETIME2 NULL` (timestamp del primer movimiento real).
- Índices:
  - `IX_orders_meli_mov_depo_ts (mov_depo_ts)`
  - `IX_orders_meli_pack_id (pack_id)`

SQL idempotente:

```sql
-- Columna
IF COL_LENGTH('dbo.orders_meli', 'mov_depo_ts') IS NULL
BEGIN
  ALTER TABLE dbo.orders_meli
  ADD mov_depo_ts DATETIME2 NULL;
END
GO

-- Índices
IF NOT EXISTS (
  SELECT 1 FROM sys.indexes 
  WHERE name='IX_orders_meli_mov_depo_ts' AND object_id = OBJECT_ID('dbo.orders_meli')
)
BEGIN
  CREATE INDEX IX_orders_meli_mov_depo_ts ON dbo.orders_meli(mov_depo_ts);
END
GO

IF NOT EXISTS (
  SELECT 1 FROM sys.indexes 
  WHERE name='IX_orders_meli_pack_id' AND object_id = OBJECT_ID('dbo.orders_meli')
)
BEGIN
  CREATE INDEX IX_orders_meli_pack_id ON dbo.orders_meli(pack_id);
END
GO
```

Opcional backfill conservador:

```sql
UPDATE dbo.orders_meli
SET mov_depo_ts = COALESCE(date_closed, SYSUTCDATETIME())
WHERE mov_depo_hecho = 1 AND mov_depo_ts IS NULL;
```

---

## 2) Backend (FastAPI)

Archivos relevantes:
- `server/services.py` → `update_order_service()` sella `mov_depo_ts` cuando `mov_depo_hecho=1`, idempotente, solo si la columna existe.
- `server/app.py` → nuevos endpoints de estadísticas:
  - `GET /stats/movements` (rango)
  - `GET /stats/movements/today` (hoy)

Variables de entorno:
- `SERVER_API_TOKEN` → token Bearer para proteger endpoints.
- `SERVER_TZ` → zona horaria para “hoy”. Default: `Argentina Standard Time`.

### 2.1 Endpoints

- `POST /orders/{order_id}/printed-moved`
  - Acepta: `printed`, `mov_depo_hecho`, `mov_depo_numero`, `mov_depo_obs`, `asignacion_detalle`.
  - Al recibir `mov_depo_hecho=1`, el servidor sella `mov_depo_ts` si está NULL.

- `GET /stats/movements/today`
  - Devuelve `{ "date": "YYYY-MM-DD", "count": N }`.
  - Cuenta `COUNT(DISTINCT pack_id)` si existe; si no, `order_id`.
  - Usa `mov_depo_ts` como fuente de fecha.

- `GET /stats/movements?from=YYYY-MM-DDTHH:mm:ss&to=YYYY-MM-DDTHH:mm:ss&depot=...&include_packs=0|1`
  - Devuelve `{ from, to, count, packs? }`.
  - Filtra por rango de `mov_depo_ts`. Si no existe, cae a `date_closed/date_created`.
  - `include_packs=1` devuelve una muestra de filas para debug.

---

## 3) Cliente (uso esperado)

- En movimiento real (no reimpresión):
  - Enviar a `POST /orders/{id}/printed-moved` con `mov_depo_hecho=1`.
  - El servidor sellará `mov_depo_ts` automáticamente e idempotente.

Ejemplo JSON:

```http
POST /orders/123456789/printed-moved
Authorization: Bearer <SERVER_API_TOKEN>
Content-Type: application/json

{
  "printed": 1,
  "mov_depo_hecho": 1,
  "mov_depo_numero": "MOV-2025-000123",
  "mov_depo_obs": "Salida DEPO CENTRAL",
  "asignacion_detalle": "DEPO=CENTRAL;UBIC=PASILLO-3;OPERARIO=Juan"
}
```

- Reimpresión: no enviar `mov_depo_hecho` (no debe contar).

Consulta del contador:

```http
GET /stats/movements/today
Authorization: Bearer <SERVER_API_TOKEN>
```

---

## 4) Regla MUNDOCAB para seller 756086955

Objetivo: toda venta de la cuenta `756086955` se asigna a `MUNDOCAB` y la nota publicada a ML lo refleja.

Implementado en `modules/08_assign_tx.py`:
- `assign_pack_multiventa()` (L238–L246): si todo el pack es de 756086955, fuerza depósito `MUNDOCAB` sin evaluar clusters.
- Publicación de nota (L301–L315): `publish_note_upsert(..., deposito_asignado='MUNDOCAB', ...)`.
- Camino por ítem (L803–L810): fuerza ganador `MUNDOCAB` para seller 756086955.

Si se requiere además persistir una columna `deposito_asignado` en DB, se puede agregar al `UPDATE orders_meli` (actualmente opcional según esquema instalado).

---

## 5) Verificación rápida

PowerShell:

```powershell
$token = "<SERVER_API_TOKEN>"

# 1) Registrar movimiento real
Invoke-RestMethod "http://localhost:8000/orders/123456789/printed-moved" `
  -Method POST `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body (@{ printed=1; mov_depo_hecho=1; mov_depo_numero="MOV-2025-000123"; mov_depo_obs="Salida" } | ConvertTo-Json)

# 2) Ver conteo de hoy
Invoke-RestMethod "http://localhost:8000/stats/movements/today" -Headers @{ Authorization = "Bearer $token" }
```

---

## 6) Troubleshooting

- "Column 'mov_depo_ts' ... specified more than once": la columna ya existe. Usar el SQL idempotente provisto.
- No incrementa el contador: revisar que el cliente envíe `mov_depo_hecho=1` solo en movimientos reales (no reimpresiones) y que `mov_depo_ts` esté presente.
- TZ del día: configurar `SERVER_TZ` (default: `Argentina Standard Time`).

---

## 7) Contexto y decisiones

- La fuente de verdad es la base de datos (`orders_meli`).
- `mov_depo_ts` se sella una sola vez por orden/pack cuando se marca movimiento real.
- El conteo diario usa `COUNT(DISTINCT pack_id)` en la fecha local del servidor.
- Reimpresiones no envían movimiento y no cuentan.
- Para la cuenta `756086955`, se fuerza `MUNDOCAB` en asignación y nota, para coherencia operativa en CABA.
