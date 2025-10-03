import { cookies } from "next/headers";

export const DEFAULT_USER = process.env.ADMIN_USER || "admin";
export const DEFAULT_PASS = process.env.ADMIN_PASS || "admin";
export const COOKIE_NAME = "catalog_admin";

export async function isAuthed() {
  const store = await cookies();
  const v = store.get(COOKIE_NAME)?.value;
  return v === "1";
}

export function checkCreds(user: string, pass: string) {
  return user === DEFAULT_USER && pass === DEFAULT_PASS;
}
