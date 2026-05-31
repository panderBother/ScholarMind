/**
 * 前端 API 封装层：统一 baseURL、鉴权刷新与错误处理。
 */

export { apiFetch, apiJson, apiBase, parseApiError } from "@/services/http";
import { apiFetch, apiJson, parseApiError } from "@/services/http";

export async function apiGet<T>(path: string): Promise<T> {
  return apiJson<T>(path);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function apiDelete(path: string): Promise<void> {
  const res = await apiFetch(path, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseApiError(res));
}
