import { NextResponse } from "next/server";
import { readSite, writeSite } from "@/lib/site";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";

export async function GET() {
  const site = await readSite();
  return NextResponse.json(site);
}

export async function PUT(req: Request) {
  if (!(await isAuthed())) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.json();
  await writeSite(body);
  return NextResponse.json({ ok: true });
}
