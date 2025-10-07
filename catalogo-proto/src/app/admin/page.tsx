"use client";

import { useEffect, useRef, useState } from "react";
import type { Product } from "@/lib/data";
import type { SiteSettings, SiteCategory } from "@/lib/site";

function LoginForm({ onLogged }: { onLogged: () => void }) {
  const [user, setUser] = useState("admin");
  const [pass, setPass] = useState("admin");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user, pass }),
      credentials: "same-origin",
    });
    setLoading(false);
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      setError(j?.error || "Login failed");
      return;
    }
    onLogged();
  };

  return (
    <form onSubmit={submit} className="max-w-sm mx-auto space-y-4">
      <h1 className="text-2xl font-bold text-center">Admin Login</h1>
      <input className="w-full border px-3 py-2 rounded" placeholder="Usuario" value={user} onChange={(e)=>setUser(e.target.value)} />
      <input className="w-full border px-3 py-2 rounded" placeholder="Contraseña" type="password" value={pass} onChange={(e)=>setPass(e.target.value)} />
      {error && <div className="text-red-600 text-sm">{error}</div>}
      <button disabled={loading} className="w-full rounded bg-black text-white py-2">{loading?"Ingresando…":"Ingresar"}</button>
    </form>
  );
}

function slugifyBase(name: string): string {
  return (name || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
}

function SiteSettingsEditor({ initial, onChange }:{ initial: SiteSettings, onChange:(v:SiteSettings)=>Promise<void> | void }){
  const [brandName, setBrandName] = useState(initial.brand.name);
  const [brandLogo, setBrandLogo] = useState(initial.brand.logo);
  const [instagram, setInstagram] = useState(initial.social?.instagram ?? "");
  const [heroImages, setHeroImages] = useState<string[]>(initial.hero.images ?? []);
  const [heroInterval, setHeroInterval] = useState<number>(initial.hero.intervalMs ?? 5000);
  const [categories, setCategories] = useState<SiteCategory[]>(initial.categories ?? []);
  const logoRef = useRef<HTMLInputElement|null>(null);
  const heroRef = useRef<HTMLInputElement|null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const uploadFile = async (file: File, opts?: { baseName?: string; folder?: "uploads"|"images"|"banners" }): Promise<string> => {
    const fd = new FormData();
    fd.append("file", file);
    if (opts?.baseName) fd.append("baseName", opts.baseName);
    if (opts?.folder) fd.append("folder", opts.folder);
    const res = await fetch("/api/upload", { method: "POST", body: fd, credentials: "same-origin" });
    if (!res.ok) throw new Error("Error subiendo archivo");
    const j = await res.json();
    return j.url as string;
  };

  const save = async () => {
    try {
      setSaving(true);
      setSaveMsg(null);
      const next: SiteSettings = {
        brand: { name: brandName, logo: brandLogo },
        social: { instagram },
        hero: { images: heroImages, intervalMs: Number(heroInterval)||5000 },
        categories,
      };
      await onChange(next);
      setSaveMsg("Ajustes guardados");
    } catch {
      setSaveMsg("No se pudo guardar ajustes");
    } finally {
      setSaving(false);
      // Ocultar mensaje luego de unos segundos
      setTimeout(()=>setSaveMsg(null), 3000);
    }
  };

  return (
    <section className="space-y-4">
      <h2 className="font-semibold">Ajustes del sitio</h2>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-3 p-4 border rounded bg-white text-black">
          <h3 className="font-medium">Marca</h3>
          <label className="block text-sm">Nombre<input className="w-full border px-2 py-1 rounded" value={brandName} onChange={(e)=>setBrandName(e.target.value)} /></label>
          <label className="block text-sm">Logo URL<input className="w-full border px-2 py-1 rounded" value={brandLogo} onChange={(e)=>setBrandLogo(e.target.value)} placeholder="/logo.svg" /></label>
          <div className="flex items-center gap-3">
            <input ref={logoRef} type="file" accept="image/*" className="sr-only" onChange={async (e)=>{
              const f = e.currentTarget.files?.[0];
              if (!f) return;
              const url = await uploadFile(f).catch(()=>"");
              if (url) setBrandLogo(url);
            }} />
            <button type="button" onClick={()=>logoRef.current?.click()} className="rounded-full bg-gray-900 text-white px-4 py-2 text-sm">Subir logo</button>
            {brandLogo && <img src={brandLogo} alt="Logo actual" className="h-8" />}
          </div>
        </div>

        <div className="space-y-3 p-4 border rounded bg-white text-black">
          <h3 className="font-medium">Redes</h3>
          <label className="block text-sm">Instagram<input className="w-full border px-2 py-1 rounded" value={instagram} onChange={(e)=>setInstagram(e.target.value)} placeholder="https://instagram.com/tu_cuenta" /></label>
        </div>

        <div className="space-y-3 p-4 border rounded bg-white text-black md:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Hero (banners)</h3>
            <label className="text-sm">Intervalo (ms)
              <input type="number" className="ml-2 border px-2 py-1 rounded w-28" value={heroInterval} onChange={(e)=>setHeroInterval(Number(e.target.value))} />
            </label>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {heroImages.map((img, idx)=> (
              <div key={idx} className="relative group">
                <img src={img} alt={`Banner ${idx+1}`} className="rounded border aspect-[16/9] object-cover w-full" />
                <button type="button" className="absolute top-2 right-2 rounded bg-red-600 text-white text-xs px-2 py-1 opacity-0 group-hover:opacity-100" onClick={()=>setHeroImages(heroImages.filter((_,i)=>i!==idx))}>Quitar</button>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <input ref={heroRef} type="file" accept="image/*" className="sr-only" onChange={async (e)=>{
              const f = e.currentTarget.files?.[0];
              if (!f) return;
              const nextIdx = (heroImages?.length ?? 0) + 1;
              const base = slugifyBase(`banner_${nextIdx}`) || `banner_${nextIdx}`;
              const url = await uploadFile(f, { baseName: base, folder: "uploads" }).catch(()=>"");
              if (url) setHeroImages(prev=>[...prev, url]);
            }} />
            <button type="button" onClick={()=>heroRef.current?.click()} className="rounded-full bg-gray-900 text-white px-4 py-2 text-sm">Agregar banner</button>
          </div>
        </div>

        <div className="space-y-3 p-4 border rounded bg-white text-black md:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Categorías</h3>
            <button type="button" className="rounded-full bg-gray-900 text-white px-4 py-2 text-sm" onClick={()=>setCategories(prev=>[...prev, { title: "Nueva", image: "/images/placeholder.svg", href: "/catalog" }])}>Agregar</button>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {categories.map((c, idx)=> (
              <div key={idx} className="p-3 border rounded space-y-2">
                <label className="block text-sm">Título<input className="w-full border px-2 py-1 rounded" value={c.title} onChange={(e)=>{
                  const v = e.target.value; setCategories(prev=>prev.map((x,i)=> i===idx? {...x, title:v}: x));
                }} /></label>
                <label className="block text-sm">Link<input className="w-full border px-2 py-1 rounded" value={c.href} onChange={(e)=>{
                  const v = e.target.value; setCategories(prev=>prev.map((x,i)=> i===idx? {...x, href:v}: x));
                }} /></label>
                <div className="flex items-center gap-3">
                  <img src={c.image} alt={c.title || "Imagen categoría"} className="h-12 w-12 rounded object-cover border" />
                  <button type="button" className="rounded bg-gray-900 text-white px-3 py-1 text-sm" onClick={async()=>{
                    const input = document.createElement("input");
                    input.type = "file"; input.accept = "image/*";
                    input.onchange = async () => {
                      const f = input.files?.[0]; if (!f) return;
                      const base = slugifyBase(categories[idx]?.title || `categoria_${idx+1}`) || `categoria_${idx+1}`;
                      const url = await uploadFile(f, { baseName: base, folder: "uploads" }).catch(()=>"");
                      if (url) setCategories(prev=>prev.map((x,i)=> i===idx? {...x, image:url}: x));
                    };
                    input.click();
                  }}>Subir imagen</button>
                  <button type="button" className="rounded bg-red-600 text-white px-3 py-1 text-sm" onClick={()=>setCategories(prev=>prev.filter((_,i)=>i!==idx))}>Eliminar</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3">
        {saveMsg && <span className="text-sm text-gray-300">{saveMsg}</span>}
        <button type="button" disabled={saving} onClick={save} className="rounded-full bg-black text-white px-5 py-2 disabled:opacity-60">
          {saving?"Guardando…":"Guardar ajustes"}
        </button>
      </div>
    </section>
  );
}

function ProductForm({initial, onSaved}:{initial?: Partial<Product>, onSaved: ()=>void}){
  const [sku, setSku] = useState(initial?.sku ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [price, setPrice] = useState<number>(Number(initial?.price ?? 0));
  const [gender, setGender] = useState(initial?.gender ?? "Unisex");
  const [category, setCategory] = useState(initial?.category ?? "");
  const [subcategory, setSubcategory] = useState(initial?.subcategory ?? "");
  const [tagsText, setTagsText] = useState<string>((initial?.tags ?? []).join(", "));
  const [imagesArr, setImagesArr] = useState<string[]>(initial?.images ?? (initial?.image ? [initial.image] : []));
  const [image, setImage] = useState(initial?.image ?? (imagesArr[0] ?? ""));
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadInfo, setUploadInfo] = useState<string | null>(null);

  const fileRef = useRef<HTMLInputElement|null>(null);
  const [fileName, setFileName] = useState<string>("");
  const galleryRef = useRef<HTMLInputElement|null>(null);

  const uploadImage = async () => {
    const f = fileRef.current?.files?.[0];
    if (!f) {
      // Si no hay archivo, abrimos el selector
      fileRef.current?.click();
      // Esperamos un tick para que el usuario elija y reintentamos luego manualmente
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const base = slugifyBase(name || sku || f.name) || "imagen";
      const fd = new FormData();
      fd.append("file", f);
      fd.append("baseName", base);
      fd.append("folder", "uploads");
      const res = await fetch("/api/upload", { method: "POST", body: fd, credentials: "same-origin" });
      if (!res.ok) {
        const j = await res.json().catch(()=>({}));
        throw new Error(j?.error || "Error al subir imagen");
      }
      const j = await res.json();
      // Verificamos que el archivo sea servible antes de setear
      try {
        const check = await fetch(j.url, { cache: "no-store" });
        if (!check.ok) throw new Error("No se puede acceder a la imagen");
      } catch {
        // seguimos igual, puede demorar un instante en estar servible
      }
      setImage(j.url);
      setImagesArr(prev=> prev.length? prev : [j.url]);
      setFileName("");
      setUploadInfo(`Subido en: ${j.dest ?? j.url}. Recordá presionar Guardar para asociarla.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al subir imagen";
      setUploadError(msg);
      setUploadInfo(null);
    } finally {
      setUploading(false);
    }
  };

  // Subir múltiples imágenes a la galería (ProductForm)
  const uploadGallery = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    try {
      const uploaded: string[] = [];
      for (const f of Array.from(files)) {
        const base = slugifyBase(name || sku || f.name) || "imagen";
        const fd = new FormData();
        fd.append("file", f);
        fd.append("baseName", base);
        fd.append("folder", "uploads");
        const res = await fetch("/api/upload", { method: "POST", body: fd, credentials: "same-origin" });
        if (!res.ok) {
          const j = await res.json().catch(()=>({}));
          throw new Error(j?.error || "Error al subir imagen");
        }
        const j = await res.json();
        uploaded.push(j.url as string);
      }
      setImagesArr(prev=>[...prev, ...uploaded]);
      if (!image && uploaded[0]) setImage(uploaded[0]);
      setUploadInfo(`Subidas: ${uploaded.length}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al subir imágenes";
      setUploadError(msg);
      setUploadInfo(null);
    } finally {
      setUploading(false);
    }
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    // tags desde texto (coma o espacio)
    const finalTags = tagsText
      .split(/[,;]+/)
      .map(s=>s.trim())
      .filter(Boolean);
    const normalizedPrimary = (()=>{
      const img = (image || imagesArr[0] || "").trim();
      return img ? (img.startsWith("/") ? img : "/" + img) : "/images/placeholder.svg";
    })();
    const normalizedGallery = imagesArr.map(u=> u.startsWith("/") ? u : "/"+u);
    const body: Product = {
      sku: sku.trim(),
      name: name.trim(),
      price: Number(price||0),
      gender,
      category,
      subcategory,
      image: normalizedPrimary,
      images: normalizedGallery,
      tags: finalTags,
    };
    const method = initial?.sku ? "PUT" : "POST";
    const res = await fetch("/api/products", { method, headers:{"Content-Type":"application/json"}, body: JSON.stringify(body), credentials: "same-origin" });
    if (!res.ok) { alert("Error guardando producto"); return; }
    onSaved();
    alert("Producto guardado");
  };

  return (
    <form onSubmit={save} className="space-y-3 p-4 border rounded bg-white text-black">
      <div className="grid md:grid-cols-2 gap-3">
        <label className="block text-sm">SKU<input className="w-full border px-2 py-1 rounded" value={sku} onChange={(e)=>setSku(e.target.value)} required disabled={!!initial?.sku} /></label>
        <label className="block text-sm">Nombre<input className="w-full border px-2 py-1 rounded" value={name} onChange={(e)=>setName(e.target.value)} required /></label>
        <label className="block text-sm">Precio<input type="number" className="w-full border px-2 py-1 rounded" value={price} onChange={(e)=>setPrice(Number(e.target.value))} required /></label>
        <label className="block text-sm">Género<input className="w-full border px-2 py-1 rounded" value={gender} onChange={(e)=>setGender(e.target.value)} /></label>
        <label className="block text-sm">Categoría<input className="w-full border px-2 py-1 rounded" value={category} onChange={(e)=>setCategory(e.target.value)} /></label>
        <label className="block text-sm">Subcategoría<input className="w-full border px-2 py-1 rounded" value={subcategory} onChange={(e)=>setSubcategory(e.target.value)} /></label>
        <label className="block text-sm md:col-span-2">Etiquetas (separadas por coma)
          <input className="w-full border px-2 py-1 rounded" value={tagsText} onChange={(e)=>setTagsText(e.target.value)} placeholder="HOMBRE, CUELLITO, POLAR" />
        </label>
      </div>
      <div className="space-y-2">
        <label className="block text-sm">Imagen URL<input className="w-full border px-2 py-1 rounded" value={image} onChange={(e)=>setImage(e.target.value)} placeholder="/images/uploads/xxx.jpg" /></label>
        <div className="flex items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="sr-only"
            onChange={async (e)=>{
              const f = e.currentTarget.files?.[0];
              setFileName(f ? f.name : "");
              if (f) {
                // auto-subida al seleccionar
                await uploadImage();
              }
            }}
          />
          <button
            type="button"
            onClick={()=>fileRef.current?.click()}
            className="rounded-full bg-gray-900 text-white px-4 py-2 text-sm hover:scale-[1.02] transition-transform"
          >
            Seleccionar archivo
          </button>
          <button
            type="button"
            onClick={uploadImage}
            disabled={uploading}
            className="rounded-full bg-green-600 text-white px-4 py-2 text-sm hover:bg-green-700 disabled:opacity-60"
          >
            {uploading?"Subiendo…":"Subir archivo"}
          </button>
          {fileName && <span className="text-xs text-gray-600 truncate max-w-[160px]">{fileName}</span>}
        </div>
        {uploadError && <div className="text-sm text-red-600">{uploadError}</div>}
        {uploadInfo && <div className="text-sm text-green-600">{uploadInfo}</div>}
        {image && <img src={image} alt="preview" className="h-24 object-cover rounded border" />}
      </div>

      {/* Galería de imágenes */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="font-medium">Galería (múltiples imágenes)</label>
          <input
            ref={galleryRef}
            type="file"
            multiple
            accept="image/*"
            className="sr-only"
            onChange={(e)=> uploadGallery(e.currentTarget.files)}
          />
          <button type="button" onClick={()=>galleryRef.current?.click()} className="rounded-full bg-gray-900 text-white px-4 py-2 text-sm">Agregar a galería</button>
        </div>
        {imagesArr.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {imagesArr.map((u, i)=> (
              <div key={i} className="relative">
                <img src={u} alt={`img-${i}`} className="h-20 w-20 object-cover rounded border" />
                <button type="button" className="absolute -top-2 -right-2 rounded-full bg-red-600 text-white text-xs px-2 py-0.5" onClick={()=> setImagesArr(prev=> prev.filter((_,idx)=> idx!==i))}>×</button>
              </div>
            ))}
          </div>
        )}
      </div>
      <button disabled={uploading} className="rounded bg-black text-white px-4 py-2 disabled:opacity-60">{uploading?"Subiendo…":"Guardar"}</button>
    </form>
  );
}

export default function AdminPage(){
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [refresh, setRefresh] = useState(0);
  const [editing, setEditing] = useState<Product | null>(null);
  const [site, setSite] = useState<SiteSettings | null>(null);

  const load = async () => {
    const r = await fetch("/api/me", { cache: "no-store", credentials: "same-origin" });
    const me = await r.json();
    setAuthed(!!me.authed);
    if (me.authed) {
      const p = await fetch("/api/products", { cache: "no-store", credentials: "same-origin" }).then(r=>r.json());
      setProducts(p);
      const s = await fetch("/api/site", { cache: "no-store", credentials: "same-origin" }).then(r=>r.json());
      setSite(s);
    }
  };

  useEffect(()=>{ load(); }, [refresh]);

  const logout = async () => {
    await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
    setAuthed(false);
  };

  if (authed === null) return <div className="p-6 text-sm text-gray-500">Cargando…</div>;
  if (!authed) return <LoginForm onLogged={()=>setRefresh(x=>x+1)} />;

  return (
    <div className="container-base py-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Panel de administración</h1>
        <button onClick={logout} className="rounded bg-gray-200 px-3 py-1">Cerrar sesión</button>
      </div>

      {/* Ajustes del sitio */}
      {site && (
        <SiteSettingsEditor
          initial={site}
          onChange={async (next: SiteSettings)=>{
            const res = await fetch("/api/site", { method: "PUT", credentials: "same-origin", headers: {"Content-Type":"application/json"}, body: JSON.stringify(next) });
            if (!res.ok) { alert("No se pudo guardar los ajustes del sitio"); return; }
            setSite(next);
          }}
        />
      )}

      <div>
        <h2 className="font-semibold mb-2">Crear nuevo producto</h2>
        <ProductForm onSaved={()=>{ setEditing(null); setRefresh(x=>x+1); }} />
      </div>

      <div>
        <h2 className="font-semibold mb-2">Productos</h2>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {products.map(p=> (
            <div key={p.sku} className="border rounded p-3 space-y-2 bg-white">
              <div className="flex gap-3">
                <img src={p.image} alt={p.name} className="h-20 w-20 object-cover rounded border" />
                <div className="text-sm">
                  <div className="font-semibold">{p.name}</div>
                  <div className="text-gray-600">{p.sku}</div>
                  <div className="font-mono">${p.price}</div>
                </div>
              </div>
              <div className="flex gap-2">
                <button className="rounded bg-gray-800 text-white px-3 py-1" onClick={()=>setEditing(p)}>Editar</button>
                <button className="rounded bg-red-600 text-white px-3 py-1" onClick={async()=>{
                  if (!confirm(`Eliminar ${p.name}?`)) return;
                  const res = await fetch(`/api/products?sku=${encodeURIComponent(p.sku)}`, { method: "DELETE", credentials: "same-origin" });
                  if (!res.ok) { alert("Error eliminando"); return; }
                  setRefresh(x=>x+1);
                }}>Eliminar</button>
              </div>
              {editing?.sku === p.sku && (
                <div>
                  <h3 className="font-semibold">Editar</h3>
                  <ProductForm initial={p} onSaved={()=>{ setEditing(null); setRefresh(x=>x+1); }} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
