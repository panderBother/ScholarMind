/**
 * 前端 API 封装层：统一 baseURL、错误处理与类型占位。
 * 开发环境通过 Vite proxy 转发到 FastAPI（/api -> 8000）。
 */

// 与 FastAPI `settings.api_v1_prefix`（默认 /api/v1）保持一致
const BASE = "/api/v1";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}
