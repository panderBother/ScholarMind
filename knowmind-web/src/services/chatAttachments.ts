import { apiFetch, parseApiError } from "@/services/http";

export type ChatAttachmentDto = {
  id: string;
  filename: string;
  file_type: string;
  size: number;
};

export async function uploadChatAttachment(file: File): Promise<ChatAttachmentDto> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch("/chat/attachments", {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ChatAttachmentDto;
}
