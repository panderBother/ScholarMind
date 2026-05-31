import { useCallback, useRef, useState } from "react";
import { UploadCloud } from "lucide-react";

import { filterSupportedFiles } from "@/services/documents";

type Props = {
  kbName: string;
  disabled?: boolean;
  uploading: boolean;
  uploadProgress: number;
  onSelectFiles: (files: File[]) => void | Promise<void>;
  onBrowseClick: () => void;
};

export function DocumentUploadZone({
  kbName,
  disabled,
  uploading,
  uploadProgress,
  onSelectFiles,
  onBrowseClick,
}: Props) {
  const [dragOver, setDragOver] = useState(false);
  const dragDepth = useRef(0);

  const handleFiles = useCallback(
    (files: FileList | File[] | null) => {
      if (!files?.length || disabled || uploading) return;
      const arr = filterSupportedFiles(files);
      if (arr.length) void onSelectFiles(arr);
    },
    [disabled, onSelectFiles, uploading],
  );

  const onDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current += 1;
    setDragOver(true);
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragOver(false);
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = disabled || uploading ? "none" : "copy";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current = 0;
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const zoneCls = [
    "rounded-2xl border-2 border-dashed p-6 text-center transition-colors lg:rounded-xl lg:p-10",
    dragOver && !disabled && !uploading
      ? "border-primary bg-primary-soft/40"
      : "border-slate-200 bg-white",
    disabled ? "opacity-50" : "",
  ].join(" ");

  return (
    <div
      role="button"
      tabIndex={0}
      className={zoneCls}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onBrowseClick();
        }
      }}
    >
      <UploadCloud
        className={`mx-auto mb-2 h-9 w-9 lg:h-10 lg:w-10 ${dragOver ? "text-primary" : "text-primary"}`}
      />
      <p className="text-sm text-slate-600">
        {dragOver ? "松开鼠标即可上传" : `拖拽文件到此处，或选择上传至「${kbName}」`}
      </p>
      <p className="mt-1 text-xs text-slate-400">
        支持 PDF、DOCX、Excel、CSV、Markdown、TXT、图片
      </p>

      {uploading ? (
        <div className="mx-auto mt-4 w-full max-w-xs">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>上传进度</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-primary transition-all duration-200"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      ) : null}

      <button
        type="button"
        disabled={disabled || uploading}
        onClick={onBrowseClick}
        className="mt-3 w-full max-w-xs rounded-xl bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-50 lg:mt-4 lg:w-auto lg:px-6"
      >
        {uploading ? `上传中 ${uploadProgress}%` : "选择文件"}
      </button>
    </div>
  );
}
