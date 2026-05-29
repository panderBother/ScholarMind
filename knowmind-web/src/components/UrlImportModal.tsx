import { UrlImportPanel, type UrlImportCategory } from "@/components/UrlImportPanel";

type Props = {
  kbId: string;
  categories: UrlImportCategory[];
  onClose: () => void;
  onImported: () => void;
};

/** 弹窗形态的 URL 采集（文档条目视图快捷入口） */
export function UrlImportModal({ kbId, categories, onClose, onImported }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">URL 网页采集</h2>
            <p className="mt-0.5 text-xs text-slate-500">也可在「知识生产」工作台中使用完整流程</p>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-slate-500">
            关闭
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <UrlImportPanel
            kbId={kbId}
            categories={categories}
            layout="compact"
            onImported={() => {
              onImported();
              onClose();
            }}
          />
        </div>
      </div>
    </div>
  );
}
