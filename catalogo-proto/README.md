## Arranque rápido

Carpeta donde ejecutar los comandos:
`C:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\catalogo-proto`

Comandos de inicio (modo servidor Next):
```
npm ci
npm run build && npm start
```

URLs:
- Sitio: http://localhost:3000
- Admin: http://localhost:3000/admin (usuario: `admin`, contraseña: `admin`)

Notas importantes:
- No usar `npx serve`. Para que funcionen las APIs (upload, productos, ajustes del sitio) debe correrse con `npm start`.
- Las imágenes subidas quedan en `public/images/uploads/` y se sirven como `/images/uploads/...`.

## Catálogo Proto — Next.js + Tailwind

Catálogo web simple con portada (hero), header sticky con logo y búsqueda, página de catálogo con filtros encadenados y grilla de productos. Datos mock desde `data/products.json`. Imágenes locales desde `public/images/`.

### Stack
- Next.js 14 (App Router) + TypeScript
- Tailwind CSS
- (Opcional) shadcn/ui para futuros componentes

### Estructura
- `public/logo.png` y `public/hero.jpg` (agregar tus imágenes)
- `public/images/` fotos de productos
- `src/app/layout.tsx` header sticky + estilos base
- `src/app/page.tsx` portada con hero + búsqueda + CTA
- `src/app/catalog/page.tsx` catálogo con filtros y grilla responsive
- `src/components/Header.tsx` logo + búsqueda compacta
- `src/components/FilterTree.tsx` filtros: Género → Categoría → Subcategoría
- `src/components/ProductCard.tsx` card con imagen, nombre, precio, WhatsApp
- `src/lib/data.ts` carga JSON, helpers de precio y WhatsApp
- `data/products.json` datos mock

### Requisitos previos
- Node 18+

### Instalación
1) Instalar dependencias Tailwind y utilidades:
```bash
npm i tailwindcss postcss autoprefixer class-variance-authority lucide-react
```

2) Ejecutar en desarrollo:
```bash
npm run dev
```

Abrí http://localhost:3000

### Cómo agregar imágenes y datos
- Copiá tus fotos a `public/images/` y asegurate de referenciarlas en el JSON.
- Editá `data/products.json` para agregar o modificar artículos. Ejemplo de item:
```json
{
  "sku": "CAM-CIAN-001",
  "name": "Campera Cian",
  "price": 99999,
  "gender": "Mujer",
  "category": "Camperas",
  "subcategory": "Con capucha",
  "image": "/images/campera_cian.jpg"
}
```

### Uso de búsqueda y filtros
- Búsqueda por nombre y SKU (`?q=` en URL)
- Filtros encadenados: `?g=` (género), `?c=` (categoría), `?s=` (subcategoría)
- La UI actualiza resultados al cambiar cualquier filtro o query.

### WhatsApp por artículo
El botón arma un link `wa.me`:
```
https://wa.me/<DEFAULT_PHONE>?text=encodeURIComponent("Hola, consulto por <sku> - <name>")
```
`DEFAULT_PHONE` se cambia en `src/lib/data.ts`.

### Notas
- Este prototipo no usa DB ni backend. Todo en memoria y archivos locales.
- Si querés sumar shadcn/ui más adelante, seguí la guía en https://ui.shadcn.com
