import { useState } from "react";
import { ExternalLink } from "lucide-react";
import type { ChatMediaItem } from "@/utils/extractToolResultMedia";

type Props = {
  items: ChatMediaItem[];
};

function ChatMediaImage({ url }: { url: string }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-primary hover:bg-slate-100"
      >
        <ExternalLink className="h-4 w-4 shrink-0" />
        图片加载失败，点击在新标签页打开
      </a>
    );
  }

  return (
    <a href={url} target="_blank" rel="noopener noreferrer">
      <img
        src={url}
        alt=""
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
        className="max-h-96 max-w-full rounded-xl border border-slate-200 object-contain"
      />
    </a>
  );
}

export function ChatMediaGallery({ items }: Props) {
  if (!items.length) return null;

  return (
    <div className="mb-3 flex flex-col gap-3">
      {items.map((item) =>
        item.type === "video" ? (
          <video
            key={item.url}
            src={item.url}
            controls
            playsInline
            className="max-h-96 max-w-full rounded-xl border border-slate-200 bg-black/5"
          />
        ) : (
          <ChatMediaImage key={item.url} url={item.url} />
        ),
      )}
    </div>
  );
}
