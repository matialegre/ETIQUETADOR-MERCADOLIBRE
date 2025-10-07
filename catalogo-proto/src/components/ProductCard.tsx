"use client";

import { useMemo, useState } from "react";
import { Product, buildWaLink, formatPrice } from "@/lib/data";
import GalleryLightbox from "@/components/GalleryLightbox";

export default function ProductCard({ product }: { product: Product }) {
  const slides = useMemo(() => {
    const arr = [product.image, ...(product.images ?? [])].filter(Boolean);
    // remove duplicates while preserving order
    return Array.from(new Set(arr));
  }, [product.image, product.images]);
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-2xl border shadow-sm overflow-hidden bg-white">
      <button type="button" className="aspect-[4/3] bg-gray-100 w-full" onClick={()=> setOpen(true)}>
        <img
          src={product.image}
          alt={product.name}
          className="w-full h-full object-cover"
          loading="lazy"
          onError={(e) => {
            const target = e.currentTarget as HTMLImageElement;
            if (target.src.endsWith("/images/placeholder.svg")) return;
            target.src = "/images/placeholder.svg";
          }}
        />
      </button>
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
      <GalleryLightbox images={slides} open={open} onClose={()=> setOpen(false)} />
    </div>
  );
}
