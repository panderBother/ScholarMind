import { apiFetch, parseApiError } from "@/services/http";
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

export function flattenCategoryTree(nodes: CategoryTreeNode[], depth = 0): CategoryOption[] {
  const out: CategoryOption[] = [];
  for (const n of nodes) {
    out.push({ id: n.id, label: `${"—".repeat(depth)}${depth ? " " : ""}${n.name}` });
    if (n.children?.length) out.push(...flattenCategoryTree(n.children, depth + 1));
  }
  return out;
}

export async function listCategoryTree(kbId: string): Promise<CategoryTreeNode[]> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/categories`, {
    });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as CategoryTreeNode[];
}

export async function createCategory(
  kbId: string,
  body: { name: string; parent_id?: string | null },
): Promise<void> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/categories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
}

export async function deleteCategory(kbId: string, categoryId: string): Promise<void> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/categories/${categoryId}`, {
    method: "DELETE",
    });
  if (!res.ok) throw new Error(await parseApiError(res));
}
