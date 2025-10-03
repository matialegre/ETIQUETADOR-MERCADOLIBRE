import Link from "next/link";
import HeroCarousel from "@/components/HeroCarousel";
import { readSite } from "@/lib/site";
import { readProducts } from "@/lib/fsdb";
import { formatPrice, buildWaLink } from "@/lib/data";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function Home() {
  const site = await readSite();
  const products = await readProducts();
  const featured = products.slice(-6).reverse();
  return (
    <div className="space-y-10">
      {/* Hero */}
      <section>
        <HeroCarousel images={site.hero.images} intervalMs={site.hero.intervalMs} />
      </section>

      {/* Categorías */}
      <section className="container-base">
        <h2 className="text-2xl font-bold text-white mb-4">Categorías</h2>
        <div className="grid gap-6 md:grid-cols-3">
          {site.categories.slice(0,6).map((cat) => (
            <Link key={cat.title} href={cat.href} className="group relative rounded-2xl overflow-hidden border shadow-sm">
              {/* background */}
              <div className="aspect-[4/3]">
                <img src={cat.image} alt={cat.title} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
              </div>
              {/* overlay title */}
              <div className="absolute inset-0 bg-black/50" />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-white text-xl md:text-2xl font-extrabold tracking-wide drop-shadow-lg">{cat.title}</div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Destacados */}
      <section className="container-base space-y-4">
        <h2 className="text-2xl font-bold text-white">Destacados</h2>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((p) => (
            <div key={p.sku} className="group rounded-2xl overflow-hidden border bg-black/40 text-white">
              <div className="relative aspect-[4/5] bg-gray-800">
                <img src={p.image} alt={p.name} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                <span className="absolute left-3 top-3 inline-flex items-center rounded-full bg-white/90 text-black text-xs font-semibold px-2 py-0.5">NUEVO</span>
              </div>
              <div className="p-4 space-y-1">
                <div className="text-sm text-gray-300">{p.sku}</div>
                <div className="font-semibold">{p.name}</div>
                <div className="text-lg font-bold">{formatPrice(p.price)}</div>
                <a href={buildWaLink(p)} target="_blank" className="inline-flex mt-2 items-center justify-center rounded-full bg-green-600 text-white px-4 py-2 text-sm hover:bg-green-700">
                  Consultar por WhatsApp
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
