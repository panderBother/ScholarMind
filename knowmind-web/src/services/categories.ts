import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

export type CategoryTreeNode = {
  id: string;
  kb_id: string;
  parent_id: string | null;
  name: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
  children: CategoryTreeNode[];
};

export type CategoryOption = { id: string; label: string };

function authHeaders(json = false): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  const h: HeadersInit = { Authorization: `Bearer ${token}` };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    if (typeof j.detail === "string") return j.detail;
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

export function flattenCategoryTree(nodes: CategoryTreeNode[], depth = 0): CategoryOption[] {
  const out: CategoryOption[] = [];
  for (const n of nodes) {
    out.push({ id: n.id, label: `${"—".repeat(depth)}${depth ? " " : ""}${n.name}` });
    if (n.children?.length) out.push(...flattenCategoryTree(n.children, depth + 1));
  }
  return out;
}

export async function listCategoryTree(kbId: string): Promise<CategoryTreeNode[]> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/categories`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as CategoryTreeNode[];
}

export async function createCategory(
  kbId: string,
  body: { name: string; parent_id?: string | null },
): Promise<void> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/categories`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function deleteCategory(kbId: string, categoryId: string): Promise<void> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/categories/${categoryId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
}
