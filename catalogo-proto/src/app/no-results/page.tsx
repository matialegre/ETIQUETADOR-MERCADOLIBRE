"use client";

import Link from "next/link";

export default function NoResultsPage() {
  return (
    <div className="max-w-2xl mx-auto text-center space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl md:text-3xl font-bold">No se encontraron resultados</h1>
        <p className="text-gray-600">No hay resultados con los filtros actuales.</p>
      </div>
      <div className="flex items-center justify-center gap-3">
        <Link href="/catalog" className="rounded-full border px-4 py-2">
          Volver al catálogo
        </Link>
        <Link href="/" className="rounded-full bg-black text-white px-4 py-2">
          Ir a inicio
        </Link>
      </div>
    </div>
  );
}

