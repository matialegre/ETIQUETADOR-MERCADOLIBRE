"use client";

import { Product } from "@/lib/data";
import { useMemo } from "react";

export type FilterValue = {
  gender?: string;
  category?: string;
  subcategory?: string;
};

export default function FilterTree({
  products,
  value,
  onChange,
}: {
  products: Product[];
  value: FilterValue;
  onChange: (v: FilterValue) => void;
}) {
  const genders = useMemo(() =>
    Array.from(new Set(products.map((p) => p.gender))).sort(), [products]);
  const categories = useMemo(() => {
    const filtered = value.gender
      ? products.filter((p) => p.gender === value.gender)
      : products;
    return Array.from(new Set(filtered.map((p) => p.category))).sort();
  }, [products, value.gender]);
  const subcategories = useMemo(() => {
    let filtered = products;
    if (value.gender) filtered = filtered.filter((p) => p.gender === value.gender);
    if (value.category) filtered = filtered.filter((p) => p.category === value.category);
    return Array.from(new Set(filtered.map((p) => p.subcategory))).sort();
  }, [products, value.gender, value.category]);

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm font-medium mb-1">Género</label>
        <select
          value={value.gender ?? ""}
          onChange={(e) => onChange({ gender: e.target.value || undefined, category: undefined, subcategory: undefined })}
          className="w-full rounded-lg border px-3 py-2"
        >
          <option value="">Todos</option>
          {genders.map((g) => (
            <option key={g} value={g}>{g}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Categoría</label>
        <select
          value={value.category ?? ""}
          onChange={(e) => onChange({ ...value, category: e.target.value || undefined, subcategory: undefined })}
          className="w-full rounded-lg border px-3 py-2"
        >
          <option value="">Todas</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Subcategoría</label>
        <select
          value={value.subcategory ?? ""}
          onChange={(e) => onChange({ ...value, subcategory: e.target.value || undefined })}
          className="w-full rounded-lg border px-3 py-2"
        >
          <option value="">Todas</option>
          {subcategories.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
