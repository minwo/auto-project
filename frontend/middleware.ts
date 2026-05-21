import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE = "share_auth";

async function authToken(password: string) {
  const data = new TextEncoder().encode(`share:${password}`);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function isPublicPath(pathname: string) {
  return (
    pathname === "/login" ||
    pathname === "/api/auth/login" ||
    pathname.startsWith("/_next/") ||
    pathname === "/favicon.ico"
  );
}

export async function middleware(request: NextRequest) {
  const password = process.env.SHARE_PASSWORD;
  if (!password || isPublicPath(request.nextUrl.pathname)) {
    return NextResponse.next();
  }

  const expectedToken = await authToken(password);
  const actualToken = request.cookies.get(AUTH_COOKIE)?.value;
  if (actualToken === expectedToken) {
    return NextResponse.next();
  }

  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "Authentication required." }, { status: 401 });
  }

  const nextPath = encodeURIComponent(`${request.nextUrl.pathname}${request.nextUrl.search}`);
  const host = request.headers.get("x-forwarded-host") || request.headers.get("host") || request.nextUrl.host;
  const protocol =
    request.headers.get("x-forwarded-proto") || (host.includes("trycloudflare.com") ? "https" : "http");
  return NextResponse.redirect(new URL(`/login?next=${nextPath}`, `${protocol}://${host}`));
}

export const config = {
  matcher: ["/((?!.*\\..*).*)", "/api/:path*"],
};
