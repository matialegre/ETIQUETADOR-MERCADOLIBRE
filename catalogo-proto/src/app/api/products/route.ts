import { NextResponse } from "next/server";
import { deleteProduct, readProducts, upsertProduct } from "@/lib/fsdb";
import type { Product } from "@/lib/data";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";

export async function GET() {
  const list = await readProducts();
  return NextResponse.json(list);
}

export async function POST(req: Request) {
  if (!(await isAuthed())) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }
  const body = (await req.json()) as Product;
  if (!body?.sku) {
    return NextResponse.json({ ok: false, error: "Missing sku" }, { status: 400 });
  }
  await upsertProduct(body);
  return NextResponse.json({ ok: true });
}

export async function PUT(req: Request) {
  if (!(await isAuthed())) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }
  const body = (await req.json()) as Product;
  if (!body?.sku) {
    return NextResponse.json({ ok: false, error: "Missing sku" }, { status: 400 });
  }
  await upsertProduct(body);
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: Request) {
  if (!(await isAuthed())) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }
  const { searchParams } = new URL(req.url);
  const sku = searchParams.get("sku");
  if (!sku) {
    return NextResponse.json({ ok: false, error: "Missing sku" }, { status: 400 });
  }
  await deleteProduct(sku);
  return NextResponse.json({ ok: true });
}
