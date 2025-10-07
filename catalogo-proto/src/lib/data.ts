export const DEFAULT_PHONE = "5492914756102";

export type Product = {
  sku: string;
  name: string;
  price: number;
  gender: "Hombre" | "Mujer" | "Unisex" | string;
  category: string; // e.g., Remeras, Camperas
  subcategory: string; // e.g., Con capucha, Sin capucha
  image: string; // "/images/xxx.jpg"
  images?: string[]; // optional gallery
  tags?: string[]; // optional keywords for search
};

export async function loadProducts(): Promise<Product[]> {
  const data = await import("../../data/products.json");
  return data.default as Product[];
}

export function buildWaLink(p: Product, extra?: string) {
  const base = `Hola, consulto por ${p.sku} - ${p.name}`;
  const msg = extra?.trim() ? `${base}. ${extra.trim()}` : base;
  return `https://wa.me/${DEFAULT_PHONE}?text=${encodeURIComponent(msg)}`;
}

export function formatPrice(n: number) {
  return new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(n);
}
