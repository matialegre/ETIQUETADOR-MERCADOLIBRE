# 📊 BASE DE DATOS - ESQUEMA COMPLETO
## PIPELINE 4 - TABLA orders_meli

### 🔑 **COLUMNAS PRINCIPALES:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **id** | INT (PK) | ID único interno de la base de datos |
| **order_id** | NVARCHAR(50) | ID de la orden en MercadoLibre |
| **pack_id** | NVARCHAR(50) | ID del pack (para multiventas) |
| **item_id** | NVARCHAR(50) | ID del item específico |

### 📦 **INFORMACIÓN DEL PRODUCTO:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **sku** | NVARCHAR(100) | SKU del producto (formato: ART-COLOR-TALLE) |
| **producto_titulo** | NVARCHAR(500) | Título del producto en MercadoLibre |
| **qty** | INT | Cantidad vendida |
| **precio** | DECIMAL(10,2) | Precio unitario del producto |
| **barcode** | NVARCHAR(100) | Código de barras obtenido de Dragon DB |

### 📋 **ESTADOS Y SUBESTADOS:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **estado** | NVARCHAR(50) | Estado principal (paid, cancelled, etc) |
| **subestado** | NVARCHAR(50) | Subestado (ready_to_print, printed, shipped) |
| **shipping_estado** | NVARCHAR(50) | Estado del envío |
| **shipping_subestado** | NVARCHAR(50) | Subestado del envío |
| **venta_tipo** | NVARCHAR(50) | Tipo de venta (normal, multiventa, etc) |

### 🏪 **ASIGNACIÓN DE DEPÓSITO:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **deposito_asignado** | NVARCHAR(50) | Depósito elegido por el asignador |
| **stock_real** | INT | Stock real del depósito al momento de asignar |
| **stock_reservado** | INT | Stock reservado tras la asignación |
| **resultante** | INT | Stock resultante (real - reservado) |
| **asignado_flag** | BIT | 1 = Asignado, 0 = Pendiente |
| **agotamiento_flag** | BIT | 1 = Stock agotado, 0 = Stock disponible |

### 🔄 **CAMPOS DE MOVIMIENTO (NUEVOS):**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **movimiento_realizado** | BIT | 1 = Movimiento ML hecho, 0 = Pendiente |
| **observacion_movimiento** | NVARCHAR(500) | Log de todos los movimientos y cambios |
| **numero_movimiento** | NVARCHAR(100) | Número del movimiento en MercadoLibre |

### 📅 **FECHAS Y AUDITORÍA:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **fecha_orden** | DATETIME2 | Fecha de creación de la orden en ML |
| **fecha_asignacion** | DATETIME2 | Fecha de asignación al depósito |
| **fecha_actualizacion** | DATETIME2 | Última actualización por sync incremental |

### 📝 **INFORMACIÓN ADICIONAL:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **nota** | NVARCHAR(1000) | Notas del cliente obtenidas de ML |
| **multiventa_grupo** | NVARCHAR(50) | Grupo de multiventas relacionadas |
| **display_color** | NVARCHAR(20) | Color para visualización en GUI |

### 📊 **STOCK POR DEPÓSITO:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **MUNDOAL** | INT | Stock en depósito Mundo Outdoor Almagro |
| **DEP** | INT | Stock en depósito principal |
| **MONBAHIA** | INT | Stock en Montañas Bahía Blanca |
| **MTGBBPS** | INT | Stock en Montañas Bahía Blanca PS |
| **MUNDOCAB** | INT | Stock en Mundo Outdoor Caballito |
| **NQNSHOP** | INT | Stock en Neuquén Shop |
| **MTGCOM** | INT | Stock en Montañas COM |
| **MTGROCA** | INT | Stock en Montañas Roca |
| **MUNDOROC** | INT | Stock en Mundo Outdoor Roca |

---

## 🔥 **EJEMPLO DE REGISTRO COMPLETO:**

```sql
-- Orden asignada con todos los campos:
id: 1
order_id: '2000012577440698'
sku: '2027201-CC089-C10'
producto_titulo: 'Campera Outdoor Impermeable'
qty: 1
precio: 45000.00
estado: 'paid'
subestado: 'printed'
deposito_asignado: 'MUNDOCAB'
stock_real: 1
stock_reservado: 1
resultante: 0
asignado_flag: 1
agotamiento_flag: 1
movimiento_realizado: 0
observacion_movimiento: 'Orden asignada, pendiente movimiento en MercadoLibre; Sync ML (2025-01-07 14:10): subestado: ready_to_print → printed'
numero_movimiento: NULL
fecha_orden: '2025-01-07 10:30:00'
fecha_asignacion: '2025-01-07 11:15:00'
fecha_actualizacion: '2025-01-07 14:10:55'
```

---

## 🎯 **FLUJO DE ESTADOS:**

1. **NUEVA ORDEN:** Llega de MercadoLibre → Se inserta en BD
2. **READY_TO_PRINT:** Orden lista → Asignador busca depósito
3. **ASIGNADA:** Depósito elegido → Flags actualizados
4. **PRINTED:** Estado cambia → Sync incremental actualiza
5. **MOVIMIENTO ML:** Pendiente → Se resta stock en MercadoLibre
6. **SHIPPED/DELIVERED:** Estados finales → Auditoría completa

---

## 🔧 **ÍNDICES Y CONSTRAINTS:**

- **PRIMARY KEY:** id
- **UNIQUE:** (order_id, sku)
- **INDEX:** idx_ready (subestado, asignado_flag)
- **INDEX:** fecha_asignacion, fecha_actualizacion

---

**📊 TOTAL: 67 COLUMNAS** - Base de datos completa y robusta para manejo integral de órdenes MercadoLibre con asignación inteligente de depósitos y sincronización automática.
