import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE = "share_auth";
const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24;

async function authToken(password: string) {
  const data = new TextEncoder().encode(`share:${password}`);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function POST(request: NextRequest) {
  const configuredPassword = process.env.SHARE_PASSWORD;
  if (!configuredPassword) {
    return NextResponse.json({ detail: "SHARE_PASSWORD is not configured." }, { status: 503 });
  }

  const payload = (await request.json().catch(() => ({}))) as { password?: string };
  if (payload.password !== configuredPassword) {
    return NextResponse.json({ detail: "비밀번호가 맞지 않습니다." }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: AUTH_COOKIE,
    value: await authToken(configuredPassword),
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
  return response;
}
