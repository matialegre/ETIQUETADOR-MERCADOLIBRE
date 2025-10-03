"use client";

import { useEffect, useState } from "react";

export default function GalleryLightbox({ images, open, initialIndex = 0, onClose }: { images: string[]; open: boolean; initialIndex?: number; onClose: () => void; }) {
  const safe = images && images.length ? images : [];
  const [idx, setIdx] = useState(initialIndex);

  useEffect(() => setIdx(initialIndex), [initialIndex, open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") setIdx((i) => (i + 1) % safe.length);
      if (e.key === "ArrowLeft") setIdx((i) => (i - 1 + safe.length) % safe.length);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, safe.length, onClose]);

  if (!open || safe.length === 0) return null;

  const go = (delta: number) => setIdx((i) => (i + delta + safe.length) % safe.length);

  return (
    <div className="fixed inset-0 z-[100] bg-black/90 flex flex-col" onClick={onClose}>
      <button className="absolute top-4 right-4 text-white text-2xl" aria-label="Cerrar" onClick={(e)=>{ e.stopPropagation(); onClose(); }}>×</button>
      <div className="flex-1 flex items-center justify-center" onClick={(e)=>e.stopPropagation()}>
        <button aria-label="Anterior" className="hidden md:block absolute left-6 text-white/80 hover:text-white text-3xl" onClick={()=>go(-1)}>‹</button>
        <img src={safe[idx]} alt="Imagen del producto" className="max-h-[85vh] max-w-[92vw] object-contain" />
        <button aria-label="Siguiente" className="hidden md:block absolute right-6 text-white/80 hover:text-white text-3xl" onClick={()=>go(1)}>›</button>
      </div>
      <div className="p-4 flex items-center justify-center gap-2" onClick={(e)=>e.stopPropagation()}>
        {safe.map((_, i) => (
          <button key={i} aria-label={`Ir a ${i+1}`} onClick={()=>setIdx(i)} className={`h-2 w-2 rounded-full ${i===idx?"bg-white":"bg-white/40"}`} />
        ))}
      </div>
    </div>
  );
}
