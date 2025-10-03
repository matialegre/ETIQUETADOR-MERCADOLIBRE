import { NextResponse } from "next/server";
import { isAuthed } from "@/lib/auth";

export async function GET() {
  const ok = await isAuthed();
  return NextResponse.json({ authed: ok });
}
