import { Archive, CheckCircle2, Eye, Pencil, RefreshCw, Trash2 } from "lucide-react";

type Props = {
  onPreview?: () => void;
  onEdit?: () => void;
  onPublish?: () => void;
  onReindex?: () => void;
  onArchive?: () => void;
  onDelete?: () => void;
};

const btn =
  "rounded-lg p-1.5 text-slate-400 transition disabled:opacity-40 disabled:pointer-events-none";

/** 列表行 / 卡片右上角操作图标 */
export function ActionIcons({ onPreview, onEdit, onPublish, onReindex, onArchive, onDelete }: Props) {
  if (!onPreview && !onEdit && !onPublish && !onReindex && !onArchive && !onDelete) return null;

  return (
    <div className="flex shrink-0 items-center gap-0.5">
      {onPreview ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onPreview();
          }}
          className={`${btn} hover:bg-violet-50 hover:text-violet-600`}
          title="预览"
          aria-label="预览"
        >
          <Eye className="h-4 w-4" />
        </button>
      ) : null}
      {onEdit ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onEdit();
          }}
          className={`${btn} hover:bg-primary-soft hover:text-primary`}
          title="编辑"
          aria-label="编辑"
        >
          <Pencil className="h-4 w-4" />
        </button>
      ) : null}
      {onPublish ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onPublish();
          }}
          className={`${btn} hover:bg-emerald-50 hover:text-emerald-600`}
          title="发布"
          aria-label="发布"
        >
          <CheckCircle2 className="h-4 w-4" />
        </button>
      ) : null}
      {onReindex ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onReindex();
          }}
          className={`${btn} hover:bg-sky-50 hover:text-sky-600`}
          title="重建检索索引"
          aria-label="重建检索索引"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      ) : null}
      {onArchive ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onArchive();
          }}
          className={`${btn} hover:bg-red-50 hover:text-red-600`}
          title="下架"
          aria-label="下架"
        >
          <Archive className="h-4 w-4" />
        </button>
      ) : null}
      {onDelete ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className={`${btn} hover:bg-red-50 hover:text-red-500`}
          title="删除"
          aria-label="删除"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}

/** @deprecated 使用 ActionIcons */
export function CardActionIcons({
  onEdit,
  onDelete,
}: {
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  return <ActionIcons onEdit={onEdit} onDelete={onDelete} />;
}
