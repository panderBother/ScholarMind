/**
 * JWT 与鉴权相关 API（与 FastAPI `/api/v1/auth` 对齐）。
 */

const BASE = "/api/v1";
export const ACCESS_TOKEN_KEY = "knowmind_access_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export type UserPublic = {
  id: string;
  email: string;
  created_at: string;
};

export type AuthOkResponse = {
  user: UserPublic;
  access_token: string;
  token_type: string;
  expires_in: number;
};

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) {
      return String((d as { message: string }).message);
    }
    if (Array.isArray(d)) return d.map((x) => JSON.stringify(x)).join("; ");
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function authRegister(email: string, password: string): Promise<AuthOkResponse> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as AuthOkResponse;
}

export async function authLogin(email: string, password: string): Promise<AuthOkResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as AuthOkResponse;
}

export async function authMe(): Promise<UserPublic> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  const res = await fetch(`${BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as UserPublic;
}
