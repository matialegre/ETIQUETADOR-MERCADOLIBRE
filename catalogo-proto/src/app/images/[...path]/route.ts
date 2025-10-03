import { NextResponse } from "next/server";
import { UPLOAD_BASE_DIR } from "@/lib/fsdb";
import path from "path";
import { promises as fs } from "fs";

export const runtime = "nodejs";

function contentTypeFromExt(ext: string): string {
  const e = ext.toLowerCase();
  if (e === ".png") return "image/png";
  if (e === ".jpg" || e === ".jpeg") return "image/jpeg";
  if (e === ".webp") return "image/webp";
  if (e === ".gif") return "image/gif";
  if (e === ".svg") return "image/svg+xml";
  return "application/octet-stream";
}

export async function GET(
  _req: Request,
  context: unknown
) {
  try {
    type Params = { path?: string[] };
    type ParamsOrPromise = Params | Promise<Params> | undefined;
    const ctx = context as { params?: ParamsOrPromise };
    const raw: ParamsOrPromise = ctx?.params;
    const isPromise = raw && typeof (raw as Promise<Params>).then === "function";
    const params: Params | undefined = isPromise
      ? await (raw as Promise<Params>)
      : (raw as Params | undefined);
    const parts = params?.path || [];
    // Map /images/<sub>/<file> -> <UPLOAD_BASE_DIR>/<sub>/<file>
    // Fallback: if only one segment, assume uploads/<file>
    const fileRel = parts.length === 1
      ? path.join("uploads", parts[0])
      : path.join(...parts);
    // Prevent path traversal
    const absPath = path.join(UPLOAD_BASE_DIR, fileRel);
    const relCheck = path.relative(UPLOAD_BASE_DIR, absPath);
    if (relCheck.startsWith("..") || path.isAbsolute(relCheck)) {
      return NextResponse.json({ ok: false, error: "Invalid path" }, { status: 400 });
    }
    const data = await fs.readFile(absPath);
    const ext = path.extname(absPath);
    const ct = contentTypeFromExt(ext);
    const body = new Uint8Array(data);
    return new NextResponse(body, {
      status: 200,
      headers: {
        "Content-Type": ct,
        // Let browser cache images but allow updates with same name after deploy
        "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
      },
    });
  } catch {
    return NextResponse.json({ ok: false, error: "Not Found" }, { status: 404 });
  }
}
