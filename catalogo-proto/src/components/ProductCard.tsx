"use client";
import { useState } from "react";
import { Product, buildWaLink, formatPrice } from "@/lib/data";

export default function ProductCard({ product }: { product: Product }) {
  const [open, setOpen] = useState(false);
  const gallery = (product.images && product.images.length ? product.images : [product.image]).filter(Boolean);
  const [gi, setGi] = useState(0);
  const ACCENT = "#d0c8b1";
  return (
    <div className="rounded-2xl border shadow-sm overflow-hidden bg-white">
      <div className="aspect-square bg-gray-100 cursor-zoom-in" onClick={()=>{ setOpen(true); setGi(0); }}>
        <img
          src={gallery[0]}
          alt={product.name}
          className="w-full h-full object-cover"
          loading="lazy"
          onError={(e) => {
            const target = e.currentTarget as HTMLImageElement;
            if (target.src.endsWith("/images/placeholder.svg")) return;
            target.src = "/images/placeholder.svg";
          }}
        />
      </div>
      <div className="p-4 space-y-2">
        <div className="text-sm text-gray-500">{product.sku}</div>
        <h3 className="font-semibold leading-tight">{product.name}</h3>
        <div className="text-lg font-bold">{formatPrice(product.price)}</div>
        <button
          onClick={() => {
            const extra = window.prompt("Mensaje para el vendedor (opcional):", "");
            const url = buildWaLink(product, extra ?? undefined);
            window.open(url, "_blank");
          }}
          className="inline-flex items-center justify-center rounded-full bg-green-600 text-white px-4 py-2 text-sm hover:bg-green-700"
        >
          Consultar por WhatsApp
        </button>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-[100] bg-black/80 grid place-items-center p-4"
          onClick={()=>setOpen(false)}
        >
          <div className="relative w-full h-full max-h-[90vh] max-w-[90vw] grid place-items-center" onClick={(e)=> e.stopPropagation()}>
            <img
              src={gallery[gi]}
              alt={product.name}
              className="max-h-[90vh] max-w-[90vw] object-contain rounded shadow-2xl"
            />
            {gallery.length > 1 && (
              <>
                <button
                  aria-label="Anterior"
                  onClick={()=>setGi((i)=> (i-1+gallery.length)%gallery.length)}
                  className="absolute left-3 top-1/2 -translate-y-1/2 grid place-items-center w-10 h-10 rounded-full shadow"
                  style={{ backgroundColor: ACCENT, color: "#000" }}
                >
                  ‹
                </button>
                <button
                  aria-label="Siguiente"
                  onClick={()=>setGi((i)=> (i+1)%gallery.length)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 grid place-items-center w-10 h-10 rounded-full shadow"
                  style={{ backgroundColor: ACCENT, color: "#000" }}
                >
                  ›
                </button>
                <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-2">
                  {gallery.map((_, i)=> (
                    <button key={i} onClick={()=>setGi(i)} className="h-2.5 w-2.5 rounded-full border" style={{ backgroundColor: i===gi? ACCENT : "#ffffff99", borderColor: ACCENT }} />
                  ))}
                </div>
              </>
            )}
          </div>
          <button
            aria-label="Cerrar"
            onClick={()=>setOpen(false)}
            className="absolute top-4 right-4 rounded-full px-3 py-1 text-black"
            style={{ backgroundColor: "#d0c8b1" }}
          >
            Cerrar
          </button>
        </div>
      )}
    </div>
  );
}
