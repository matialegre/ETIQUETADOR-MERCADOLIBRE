import { promises as fs } from "fs";
import path from "path";
import type { Product } from "@/lib/data";

const ROOT = process.cwd();
const DATA_FILE = path.join(ROOT, "data", "products.json");
export const UPLOAD_DIR = path.join(ROOT, "public", "images", "uploads");
// Writable base for runtime uploads (outside of public). In production builds,
// writing into public/ may be read-only. Use this base for storage and serve via API.
export const UPLOAD_BASE_DIR = process.env.UPLOAD_BASE_DIR
  ? path.resolve(process.env.UPLOAD_BASE_DIR)
  : path.join(ROOT, "runtime_uploads");

export async function ensureUploadDir() {
  await fs.mkdir(UPLOAD_DIR, { recursive: true });
}

export async function readProducts(): Promise<Product[]> {
  const raw = await fs.readFile(DATA_FILE, "utf8");
  return JSON.parse(raw) as Product[];
}

export async function writeProducts(products: Product[]) {
  const json = JSON.stringify(products, null, 2);
  await fs.writeFile(DATA_FILE, json, "utf8");
}

export async function upsertProduct(p: Product) {
  const list = await readProducts();
  const idx = list.findIndex((x) => x.sku === p.sku);
  if (idx >= 0) list[idx] = p; else list.push(p);
  await writeProducts(list);
}

export async function deleteProduct(sku: string) {
  const list = await readProducts();
  const next = list.filter((x) => x.sku !== sku);
  await writeProducts(next);
}
