import { NextResponse } from "next/server";
import { UPLOAD_BASE_DIR } from "@/lib/fsdb";
import { isAuthed } from "@/lib/auth";
import path from "path";
import { promises as fs } from "fs";

export const runtime = "nodejs";

function inferExtFromMime(mime: string | undefined | null): string {
  const m = (mime || "").toLowerCase();
  if (m === "image/png") return ".png";
  if (m === "image/jpeg" || m === "image/jpg") return ".jpg";
  if (m === "image/webp") return ".webp";
  if (m === "image/gif") return ".gif";
  if (m === "image/svg+xml") return ".svg";
  return ""; // unknown
}

function safeSlugBase(name: string): string {
  // remove extension first
  const base = name.replace(/\.[^./\\]+$/, "");
  // normalize accents, remove diacritics, keep only a-z0-9 separator
  return base
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // strip diacritics
    .replace(/[^a-zA-Z0-9]+/g, "_") // non-alnum -> _
    .replace(/_+/g, "_") // collapse _
    .replace(/^_+|_+$/g, "") // trim _
    .toLowerCase();
}

function resolveTargetDir(folder: string | null | undefined): { dir: string; publicBase: string } {
  const f = String(folder || "uploads").toLowerCase();
  if (f === "images") {
    return { dir: path.join(UPLOAD_BASE_DIR, "images"), publicBase: "/images/images" };
  }
  if (f === "banners") {
    return { dir: path.join(UPLOAD_BASE_DIR, "banners"), publicBase: "/images/banners" };
  }
  // default to uploads
  return { dir: path.join(UPLOAD_BASE_DIR, "uploads"), publicBase: "/images/uploads" };
}

export async function POST(req: Request) {
  if (!(await isAuthed())) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }
  const form = await req.formData();
  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ ok: false, error: "Missing file" }, { status: 400 });
  }
  // Optional client hints
  const baseNameRaw = (form.get("baseName") as string | null) || null; // desired base name (will be slugified)
  const folder = (form.get("folder") as string | null) || null; // uploads|images|banners

  // Build safe filename
  const origName = String(file.name || "upload");
  const extFromName = (origName.match(/\.[^./\\]+$/) || [""])[0];
  const ext = (extFromName || inferExtFromMime((file as File).type || "")).toLowerCase();
  const baseNormalized = safeSlugBase(baseNameRaw ?? origName) || "file";
  // Always include timestamp to avoid overwriting files across different products
  const ts = Date.now();
  const fname = `${ts}_${baseNormalized}${ext}`;
  try {
    const { dir, publicBase } = resolveTargetDir(folder);
    await fs.mkdir(dir, { recursive: true });
    const dest = path.join(dir, fname);
    const arrayBuffer = await file.arrayBuffer();
    await fs.writeFile(dest, Buffer.from(arrayBuffer));
    // Verify write
    await fs.stat(dest);
    const publicUrl = `${publicBase}/${fname}`;
    const res = NextResponse.json({ ok: true, url: publicUrl, dest, cwd: process.cwd() });
    res.headers.set("Cache-Control", "no-store");
    return res;
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}

