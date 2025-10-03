"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Product } from "@/lib/data";

export default function SearchBox() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [list, setList] = useState<Product[]>([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const boxRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    (async () => {
      const res = await fetch("/api/products", { cache: "no-store" });
      const data: Product[] = await res.json();
      setList(data);
    })();
  }, []);

  const results = useMemo(() => {
    if (!q.trim()) return [] as Product[];
    const qq = q.toLowerCase();
    return list
      .filter(p => p.name.toLowerCase().includes(qq) || p.sku.toLowerCase().includes(qq))
      .slice(0, 8);
  }, [q, list]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!boxRef.current) return;
      if (!boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const goCatalog = (query?: string) => {
    const qs = new URLSearchParams();
    const text = (query ?? q).trim();
    if (text) qs.set("q", text);
    router.push(`/catalog${qs.toString() ? `?${qs.toString()}` : ""}`);
    setOpen(false);
  };

  return (
    <div ref={boxRef} className="relative w-full max-w-sm">
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setHighlight(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setHighlight(h => Math.min(h+1, Math.max(0, results.length-1))); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setHighlight(h => Math.max(0, h-1)); }
          else if (e.key === "Enter") {
            if (results[highlight]) goCatalog(results[highlight].name);
            else goCatalog();
          }
        }}
        placeholder="Buscar por nombre o SKU"
        className="w-full rounded-full bg-white/90 text-black px-4 py-2 outline-none"
      />
      {open && results.length > 0 && (
        <div className="absolute left-0 right-0 mt-1 rounded-xl border bg-white text-black shadow-lg overflow-hidden">
          {results.map((p, i) => (
            <button
              key={p.sku}
              onMouseDown={(e)=>{ e.preventDefault(); goCatalog(p.name); }}
              className={`w-full text-left px-3 py-2 hover:bg-gray-100 ${i===highlight?"bg-gray-100":""}`}
            >
              <div className="text-sm font-medium">{p.name}</div>
              <div className="text-xs text-gray-600">{p.sku}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
