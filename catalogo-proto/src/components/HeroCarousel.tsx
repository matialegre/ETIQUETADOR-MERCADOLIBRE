"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export default function HeroCarousel({
  images,
  intervalMs = 5000,
}: {
  images: string[];
  intervalMs?: number;
}) {
  const safeImages = useMemo(() => (images.length ? images : ["/hero.svg"]), [images]);
  const [index, setIndex] = useState(0);
  const timer = useRef<NodeJS.Timeout | null>(null);
  const ACCENT = "#d0c8b1"; // brand accent color

  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(() => {
      setIndex((i) => (i + 1) % safeImages.length);
    }, Math.max(1500, intervalMs));
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [intervalMs, safeImages.length]);

  const prev = () => setIndex((i) => (i - 1 + safeImages.length) % safeImages.length);
  const next = () => setIndex((i) => (i + 1) % safeImages.length);

  return (
    <div className="relative w-full h-[60vh] min-h-[420px] overflow-hidden rounded-2xl">
      {safeImages.map((src, i) => (
        <img
          key={src + i}
          src={src}
          alt={`Banner ${i + 1}`}
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-700"
          style={{ opacity: i === index ? 1 : 0 }}
        />
      ))}
      {/* overlay */}
      <div className="absolute inset-0 bg-black/30" />
      {/* arrows */}
      <button
        aria-label="Anterior"
        onClick={prev}
        className="absolute left-3 top-1/2 -translate-y-1/2 grid place-items-center w-10 h-10 rounded-full shadow"
        style={{ backgroundColor: ACCENT, color: "#000" }}
      >
        ‹
      </button>
      <button
        aria-label="Siguiente"
        onClick={next}
        className="absolute right-3 top-1/2 -translate-y-1/2 grid place-items-center w-10 h-10 rounded-full shadow"
        style={{ backgroundColor: ACCENT, color: "#000" }}
      >
        ›
      </button>
      {/* dots */}
      <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-2">
        {safeImages.map((_, i) => (
          <button
            key={i}
            onClick={() => setIndex(i)}
            className={`h-2.5 w-2.5 rounded-full border`}
            style={{ backgroundColor: i === index ? ACCENT : "#ffffff99", borderColor: ACCENT }}
            aria-label={`Ir a banner ${i + 1}`}
          />)
        )}
      </div>
    </div>
  );
}
