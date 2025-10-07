"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import FilterTree, { type FilterValue } from "@/components/FilterTree";
import ProductCard from "@/components/ProductCard";
import type { Product } from "@/lib/data";

export default function CatalogClient() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  // URL params (read and manage on client only)
  const [q, setQ] = useState("");
  const [g, setG] = useState<string | undefined>(undefined);
  const [c, setC] = useState<string | undefined>(undefined);
  const [s, setS] = useState<string | undefined>(undefined);
  const currentFilters: FilterValue = { gender: g, category: c, subcategory: s };

  // On mount, parse current URL search params
  useEffect(() => {
    if (typeof window === "undefined") return;
    const sp = new URLSearchParams(window.location.search);
    setQ(sp.get("q") ?? "");
    setG(sp.get("g") || undefined);
    setC(sp.get("c") || undefined);
    setS(sp.get("s") || undefined);
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      // Fetch from API so changes via admin are reflected live
      const res = await fetch("/api/products", { cache: "no-store" });
      const data: Product[] = await res.json();
      setProducts(data);
      setLoading(false);
    })();
  }, []);

  // Debounced live search typing
  const [inputQ, setInputQ] = useState(q);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => setInputQ(q), [q]);
  const onInputChange = (val: string) => {
    setInputQ(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      updateParams({ q: val });
    }, 400);
  };

  const filtered = useMemo(() => {
    const normalize = (s: string) => s
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
    let out = products;
    if (q.trim()) {
      const nq = normalize(q.trim());
      out = out.filter((p) => {
        const haystack = [
          p.name,
          p.sku,
          p.category,
          p.subcategory,
          ...(p.tags ?? []),
        ]
          .filter(Boolean)
          .map((x) => normalize(String(x)));
        return haystack.some((h) => h.includes(nq));
      });
    }
    if (g) out = out.filter((p) => p.gender === g);
    if (c) out = out.filter((p) => p.category === c);
    if (s) out = out.filter((p) => p.subcategory === s);
    return out;
  }, [products, q, g, c, s]);

  const updateParams = (patch: Partial<{ q: string; g: string | undefined; c: string | undefined; s: string | undefined }>) => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (patch.q !== undefined) {
      const v = patch.q.trim();
      if (v) params.set("q", v); else params.delete("q");
      setQ(v);
    }
    if (patch.g !== undefined) {
      if (patch.g) params.set("g", patch.g); else params.delete("g");
      setG(patch.g);
    }
    if (patch.c !== undefined) {
      if (patch.c) params.set("c", patch.c); else params.delete("c");
      setC(patch.c);
    }
    if (patch.s !== undefined) {
      if (patch.s) params.set("s", patch.s); else params.delete("s");
      setS(patch.s);
    }
    const qs = params.toString();
    const url = `/catalog${qs ? `?${qs}` : ""}`;
    window.history.pushState({}, "", url);
  };

  // Redirect to no-results client-side only
  useEffect(() => {
    if (!loading && products.length > 0 && filtered.length === 0) {
      if (typeof window !== "undefined") {
        const params = window.location.search;
        window.location.href = `/no-results${params || ""}`;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, filtered.length]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
      <aside className="md:col-span-1">
        <div className="sticky top-20 space-y-4">
          <h2 className="font-semibold">Filtros</h2>
          <FilterTree
            products={products}
            value={currentFilters}
            onChange={(v) =>
              updateParams({ g: v.gender, c: v.category, s: v.subcategory })
            }
          />
        </div>
      </aside>
      <section className="md:col-span-3 space-y-4">
        <div className="flex items-center gap-2">
          <input
            className="w-full rounded-full border px-4 py-2 shadow-sm"
            placeholder="Buscar por nombre o SKU"
            value={inputQ}
            onChange={(e) => onInputChange(e.target.value)}
          />
        </div>
        {loading ? (
          <div className="text-sm text-gray-500">Cargando productos…</div>
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filtered.map((p) => (
              <ProductCard key={p.sku} product={p} />
            ))}
            {!filtered.length && (
              <div className="col-span-full text-sm text-gray-500">
                No hay resultados con los filtros actuales.
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
