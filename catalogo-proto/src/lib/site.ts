import { promises as fs } from "fs";
import path from "path";

export type SiteCategory = { title: string; image: string; href: string };
export type SiteSettings = {
  brand: { name: string; logo: string };
  social: { instagram?: string };
  hero: { images: string[]; intervalMs: number };
  categories: SiteCategory[];
};

const ROOT = process.cwd();
const SITE_FILE = process.env.SITE_FILE_PATH
  ? path.resolve(process.env.SITE_FILE_PATH)
  : path.join(ROOT, "runtime_data", "site.json");
const LEGACY_SITE_FILE = path.join(ROOT, "data", "site.json");

export async function readSite(): Promise<SiteSettings> {
  try {
    const raw = await fs.readFile(SITE_FILE, "utf8");
    return JSON.parse(raw) as SiteSettings;
  } catch (e: unknown) {
    // Si no existe aún, crear con defaults mínimos
    const err = e as NodeJS.ErrnoException;
    if (err && err.code === "ENOENT") {
      // Intentar migración desde archivo legacy (data/site.json)
      try {
        const rawLegacy = await fs.readFile(LEGACY_SITE_FILE, "utf8");
        const legacy = JSON.parse(rawLegacy) as SiteSettings;
        await writeSite(legacy);
        return legacy;
      } catch (e2: unknown) {
        const err2 = e2 as NodeJS.ErrnoException;
        if (err2 && err2.code !== "ENOENT") throw err2;
        // No hay legacy: crear defaults mínimos
        const initial: SiteSettings = {
          brand: { name: "Catálogo", logo: "/logo.svg" },
          social: { instagram: "" },
          hero: { images: [], intervalMs: 5000 },
          categories: [],
        };
        await writeSite(initial);
        return initial;
      }
    }
    throw err;
  }
}

export async function writeSite(v: SiteSettings) {
  const json = JSON.stringify(v, null, 2);
  // Asegurar carpeta contenedora
  const dir = path.dirname(SITE_FILE);
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(SITE_FILE, json, "utf8");
}
