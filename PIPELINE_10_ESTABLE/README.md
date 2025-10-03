# PIPELINE 10 ESTABLE

Loop estable y simplificado que ejecuta el flujo completo validado:

- __Sync ML (Pipeline 5)__: trae/actualiza últimas ventas reales de MercadoLibre
  - Estados reales de shipping (ready_to_print, printed, shipped, delivered, etc.)
  - Manejo de notas con `role=seller` y refresh automático de token
  - Extracción de ARTICULO, COLOR y TALLE desde ML y guardado en DB
  - Fallback seller_custom_field → seller_sku para barcode
- __Asignación + Movimiento__ (PASO 08):
  - Asigna depósito ganador (prioridades/stock real)
  - Ejecuta movimiento real __WOO→WOO__ en Dragonfish (espera la respuesta, sin reintentos automáticos)
  - Guarda `movimiento_realizado`, `numero_movimiento` y auditoría en `observacion_movimiento`
  - Completa columnas de stock por depósito
- __Backfill de visibilidad__: completa columnas de stock por depósito en órdenes ya asignadas (no toca flags)

## Configuración clave

Editar `modules/config.py` o usar variables de entorno:

- __Switch único__ de destino de movimiento:
  - `MOVIMIENTO_TARGET` = `WOO` | `MELI`
  - Deriva automáticamente:
    - `DRAGON_BASEDEDATOS` (Header BaseDeDatos y `InformacionAdicional.BaseDeDatos*`)
    - `MOV_ORIGENDESTINO_DEFAULT` (Body OrigenDestino)
- Intervalo entre ciclos: `SLEEP_BETWEEN_CYCLES` (segundos)

Ejemplo en PowerShell (sesión actual):

```powershell
$env:MOVIMIENTO_TARGET = "WOO"      # o "MELI"
$env:SLEEP_BETWEEN_CYCLES = "60"    # 60s
```

## Ejecución

Desde la carpeta `PIPELINE_7_FULL`:

```powershell
python .\PIPELINE_10_ESTABLE\main.py --limit 50 --interval 60 --log INFO
```

Parámetros:
- `--limit`: cuántas órdenes recientes sincronizar por ciclo (para Pipeline 5)
- `--interval`: intervalo entre ciclos (segundos). Si no se especifica, usa `SLEEP_BETWEEN_CYCLES` de config/env.
- `--log`: nivel de logs (`DEBUG` | `INFO` | `WARNING` | `ERROR`).

Cortar con `Ctrl + C`.

## Auditoría y verificación rápida

- Logs de movimiento (headers y body) quedan impresos por `modules/09_dragon_movement.py`.
- En DB `orders_meli`:
  - `movimiento_realizado = 1`
  - `numero_movimiento` (número grande en WOO)
  - `observacion_movimiento` incluye `od=<TARGET>` y `base=<TARGET>`

SQL de verificación:
```sql
SELECT TOP 10
  id, order_id, deposito_asignado, movimiento_realizado,
  numero_movimiento, observacion_movimiento, updated_at
FROM orders_meli
ORDER BY id DESC;
```

## Notas operativas

- El movimiento WOO→WOO se ejecuta **una sola vez** por orden. Si falla la API, queda auditoría sin marcar flag para reintento manual.
- Se espera la respuesta de Dragonfish (puede demorar minutos). No hay reintentos automáticos para evitar dobles movimientos.
- El pipeline de sync (Pipeline 5) actualiza estados/subestados/shipping/notas de órdenes existentes para mantener sincronización incremental.
