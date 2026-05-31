/**
 * 带鉴权与 401 自动刷新的 fetch 封装。
 */

import {
  authRefresh,
  clearAccessToken,
  getAccessToken,
  getRefreshToken,
  storeAuthTokens,
} from "@/services/auth";

const BASE = "/api/v1";

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  if (!getRefreshToken()) return false;
  if (!refreshPromise) {
    refreshPromise = authRefresh()
      .then((res) => {
        storeAuthTokens(res);
        return true;
      })
      .catch(() => {
        clearAccessToken();
        return false;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function parseApiError(res: Response): Promise<string> {
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

export type ApiFetchInit = RequestInit & {
  /** 设为 true 时不附带 Authorization（如登录） */
  skipAuth?: boolean;
  /** 内部重试标记 */
  _retried?: boolean;
};

/**
 * 请求 `/api/v1` 路径；401 时尝试 refresh 一次后重试。
 */
export async function apiFetch(path: string, init: ApiFetchInit = {}): Promise<Response> {
  const { skipAuth, _retried, ...fetchInit } = init;
  const headers = new Headers(fetchInit.headers);
  if (!skipAuth) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const url = path.startsWith("http") ? path : `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, { ...fetchInit, headers });
  if (res.status !== 401 || skipAuth || _retried) return res;
  const ok = await tryRefreshToken();
  if (!ok) return res;
  return apiFetch(path, { ...init, _retried: true });
}

export function apiBase(): string {
  return BASE;
}

/** JSON 请求：失败时抛出 parseApiError 文本 */
export async function apiJson<T>(path: string, init: ApiFetchInit = {}): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as T;
}
