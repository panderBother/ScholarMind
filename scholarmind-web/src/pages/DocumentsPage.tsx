import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  ChevronDown,
  FileText,
  Filter,
  UploadCloud,
  XCircle,
} from "lucide-react";

import { getAccessToken } from "@/services/auth";
import { listDocuments, retryDocumentParse, uploadDocuments, type DocumentDto } from "@/services/documents";
import { listKnowledgeBases, type KnowledgeBaseDto } from "@/services/knowledgeBases";

/** 与移动原型一致的筛选 Tab */
const TABS_MOBILE = ["全部", "解析中", "已完成", "失败"] as const;
const TABS_DESKTOP = ["全部", "处理中", "待处理", "已完成", "失败"] as const;

function mapApiStatus(s: string): "Completed" | "Processing" | "Failed" | "Pending" {
  if (s === "done") return "Completed";
  if (s === "processing") return "Processing";
  if (s === "failed") return "Failed";
  return "Pending";
}

/**
 * 文献上传与管理：选择知识库、上传 PDF、查看解析状态（对接 FastAPI）。
 */
export function DocumentsPage() {
  const nav = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [kbs, setKbs] = useState<KnowledgeBaseDto[]>([]);
  const [kbId, setKbId] = useState<string>("");
  const [docs, setDocs] = useState<DocumentDto[]>([]);
  const [tab, setTab] = useState<string>("全部");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const loadKbs = useCallback(async () => {
    if (!getAccessToken()) {
      nav("/login", { replace: true });
      return;
    }
    setErr(null);
    try {
      const rows = await listKnowledgeBases();
      setKbs(rows);
      setKbId((cur) => cur || rows[0]?.id || "");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载知识库失败");
    }
  }, [nav]);

  const loadDocs = useCallback(async (options?: { silent?: boolean }) => {
    if (!kbId) return;
    const silent = options?.silent ?? false;
    if (!silent) {
      setLoading(true);
      setErr(null);
    }
    try {
      const rows = await listDocuments(kbId);
      setDocs(rows);
    } catch (e) {
      if (!silent) {
        setErr(e instanceof Error ? e.message : "加载文献失败");
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    void loadKbs();
  }, [loadKbs]);

  useEffect(() => {
    void loadDocs();
  }, [loadDocs]);

  const hasQueuedDocs = useMemo(
    () => docs.some((d) => d.status === "pending" || d.status === "processing"),
    [docs],
  );

  /** 有待处理/解析中文献时定时拉状态（Worker 跑完后界面会自动变为已完成） */
  useEffect(() => {
    if (!kbId || !hasQueuedDocs) return;
    const t = window.setInterval(() => void loadDocs({ silent: true }), 3000);
    return () => window.clearInterval(t);
  }, [kbId, hasQueuedDocs, loadDocs]);

  const filtered = useMemo(() => {
    if (tab === "全部") return docs;
    // 移动端「解析中」：排队(pending) 与真正解析(processing) 都归入此类，避免「一直在解析却看不到条目」
    if (tab === "解析中") {
      return docs.filter((d) => d.status === "pending" || d.status === "processing");
    }
    const map: Record<string, string> = {
      处理中: "processing",
      待处理: "pending",
      已完成: "done",
      失败: "failed",
    };
    const want = map[tab];
    return docs.filter((d) => d.status === want);
  }, [docs, tab]);

  const onRetryParse = async (docId: string) => {
    if (!kbId) return;
    setErr(null);
    try {
      await retryDocumentParse(kbId, docId);
      await loadDocs();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "重试失败");
    }
  };

  const onPickFiles = async (files: FileList | null) => {
    if (!kbId || !files?.length) return;
    setUploading(true);
    setErr(null);
    try {
      const arr = Array.from(files).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
      if (!arr.length) {
        setErr("请选择 PDF 文件");
        return;
      }
      await uploadDocuments(kbId, arr);
      await loadDocs();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "上传失败");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const kbName = kbs.find((k) => k.id === kbId)?.name ?? "选择知识库";

  return (
    <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 lg:space-y-6 lg:p-8">
      <div className="flex items-start justify-between gap-3 lg:block">
        <div>
          <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">文献管理</h1>
          <p className="mt-0.5 text-xs text-slate-500 lg:text-sm">
            PDF 单文件最大 50MB · 单次最多 20 个 · 解析异步（Celery）
          </p>
        </div>
        <button
          type="button"
          className="rounded-full border border-slate-200 bg-white p-2 text-slate-500 shadow-sm lg:hidden"
          aria-label="筛选"
        >
          <Filter className="h-5 w-5" />
        </button>
      </div>

      {err ? (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {err}
        </p>
      ) : null}

      {hasQueuedDocs ? (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 lg:px-4"
          role="status"
        >
          <p className="font-medium">文献处于「待处理 / 解析中」时，需要后台 Worker 才会继续</p>
          <p className="mt-1 text-xs leading-relaxed text-amber-800">
            默认上传会把任务放进 <strong>Redis</strong>，须另开终端运行 <strong>Celery Worker</strong>（与 API 同目录、同{" "}
            <code className="rounded bg-white/80 px-1">.env</code>）。本机开发可在{" "}
            <code className="rounded bg-white/80 px-1">.env</code> 设置{" "}
            <code className="rounded bg-white/80 px-1">INGEST_BACKGROUND_THREAD=true</code> 免 Worker（后台线程解析）。
            若状态卡在「解析中」很久，可看 API 终端日志是否卡在首次下载嵌入模型；也可点「重新解析」重排队列。
            本页每 3 秒自动刷新。
          </p>
        </div>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3 lg:gap-6">
        <div className="space-y-3 lg:col-span-2 lg:space-y-4">
          <div className="hidden lg:block">
            <label className="mb-1 block text-xs font-medium text-slate-600">目标知识库</label>
            <div className="relative max-w-md">
              <select
                className="w-full appearance-none rounded-lg border border-slate-200 bg-white px-3 py-2 pr-9 text-left text-sm text-slate-800"
                value={kbId}
                onChange={(e) => setKbId(e.target.value)}
              >
                <option value="" disabled>
                  请选择
                </option>
                {kbs.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-2.5 h-4 w-4 text-slate-400" />
            </div>
          </div>

          <div className="lg:hidden">
            <label className="mb-1 block text-xs font-medium text-slate-600">知识库</label>
            <select
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
              value={kbId}
              onChange={(e) => setKbId(e.target.value)}
            >
              <option value="" disabled>
                请选择
              </option>
              {kbs.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name}
                </option>
              ))}
            </select>
          </div>

          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            className="hidden"
            onChange={(e) => void onPickFiles(e.target.files)}
          />

          <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white p-6 text-center lg:rounded-xl lg:p-10">
            <UploadCloud className="mx-auto mb-2 h-9 w-9 text-primary lg:h-10 lg:w-10" />
            <p className="text-sm text-slate-600">选择 PDF 上传至「{kbName}」</p>
            <p className="mt-1 text-xs text-slate-400">需先选择知识库</p>
            <button
              type="button"
              disabled={!kbId || uploading}
              onClick={() => fileRef.current?.click()}
              className="mt-3 w-full max-w-xs rounded-xl bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-50 lg:mt-4 lg:w-auto lg:px-6"
            >
              {uploading ? "上传中…" : "选择 PDF"}
            </button>
          </div>
        </div>

        <aside className="hidden rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-600 shadow-card lg:block">
          <h2 className="text-sm font-semibold text-slate-900">说明</h2>
          <p className="mt-2 leading-relaxed">
            上传后 API 把解析任务发到 <strong>Redis</strong>，须另有终端运行{" "}
            <strong>Celery Worker</strong> 才会把「待处理」变成「已完成」。Worker 与 uvicorn 须共用同一{" "}
            <code className="rounded bg-slate-100 px-1">.env</code>（含 <code className="rounded bg-slate-100 px-1">
              DATABASE_URL
            </code>、<code className="rounded bg-slate-100 px-1">REDIS_URL</code>、<code className="rounded bg-slate-100 px-1">
              CELERY_TASK_ALWAYS_EAGER=false
            </code>
            ）。
          </p>
        </aside>
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card lg:rounded-xl">
        <div className="flex gap-1 overflow-x-auto border-b border-slate-100 px-2 py-2 lg:flex-wrap lg:px-4 lg:py-3">
          <div className="flex gap-1 lg:hidden">
            {TABS_MOBILE.map((t) => (
              <TabBtn key={t} t={t} tab={tab} setTab={setTab} />
            ))}
          </div>
          <div className="hidden gap-2 lg:flex lg:flex-wrap">
            {TABS_DESKTOP.map((t) => (
              <TabBtn key={t} t={t} tab={tab} setTab={setTab} />
            ))}
          </div>
        </div>

        <ul className="divide-y divide-slate-100 lg:hidden">
          {loading ? (
            <li className="p-4 text-sm text-slate-500">加载中…</li>
          ) : (
            filtered.map((row) => {
              const st = mapApiStatus(row.status);
              const mb = (row.file_bytes / (1024 * 1024)).toFixed(2);
              const title = row.title || row.filename;
              return (
                <li key={row.id} className="flex gap-3 p-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-600">
                    <FileText className="h-6 w-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium leading-snug text-slate-900">{row.filename}</div>
                    <div className="mt-0.5 text-xs text-slate-500">
                      {mb} MB · {title.slice(0, 40)}
                      {title.length > 40 ? "…" : ""}
                    </div>
                    {st === "Processing" && (
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full w-1/2 rounded-full bg-amber-400" />
                      </div>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <StatusBadge status={st} />
                      {(row.status === "pending" ||
                        row.status === "processing" ||
                        row.status === "failed") && (
                        <button
                          type="button"
                          onClick={() => void onRetryParse(row.id)}
                          className="text-xs font-semibold text-primary hover:underline"
                        >
                          重新解析
                        </button>
                      )}
                    </div>
                    {row.error_message ? (
                      <p className="mt-1 text-xs text-red-600">{row.error_message}</p>
                    ) : null}
                  </div>
                  {st === "Completed" && <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" />}
                  {st === "Failed" && <XCircle className="h-5 w-5 shrink-0 text-red-500" />}
                </li>
              );
            })
          )}
        </ul>

        <div className="hidden overflow-x-auto lg:block">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">文件名</th>
                <th className="px-4 py-3">标题</th>
                <th className="px-4 py-3">大小</th>
                <th className="px-4 py-3">块数</th>
                <th className="px-4 py-3">状态</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-slate-500">
                    加载中…
                  </td>
                </tr>
              ) : (
                filtered.map((row) => {
                  const st = mapApiStatus(row.status);
                  const mb = (row.file_bytes / (1024 * 1024)).toFixed(2);
                  return (
                    <tr key={row.id} className="hover:bg-slate-50/80">
                      <td className="px-4 py-3 font-medium text-slate-900">{row.filename}</td>
                      <td className="px-4 py-3 text-slate-600">{row.title || "—"}</td>
                      <td className="px-4 py-3 text-slate-600">{mb} MB</td>
                      <td className="px-4 py-3 text-slate-600">{row.chunk_count}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <StatusBadge status={st} />
                          {(row.status === "pending" ||
                            row.status === "processing" ||
                            row.status === "failed") && (
                            <button
                              type="button"
                              onClick={() => void onRetryParse(row.id)}
                              className="text-xs font-semibold text-primary hover:underline"
                            >
                              重新解析
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
          <span>共 {filtered.length} 条</span>
        </div>
      </section>
    </div>
  );
}

function TabBtn({
  t,
  tab,
  setTab,
}: {
  t: string;
  tab: string;
  setTab: (s: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => setTab(t)}
      className={
        t === tab
          ? "shrink-0 rounded-full bg-primary-soft px-3 py-1.5 text-xs font-semibold text-primary"
          : "shrink-0 rounded-full px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-50"
      }
    >
      {t}
    </button>
  );
}

function StatusBadge({ status }: { status: "Completed" | "Processing" | "Failed" | "Pending" }) {
  const cls =
    status === "Completed"
      ? "bg-emerald-50 text-emerald-700"
      : status === "Processing"
        ? "bg-amber-50 text-amber-700"
        : status === "Failed"
          ? "bg-red-50 text-red-700"
          : "bg-slate-100 text-slate-600";
  const label =
    status === "Completed"
      ? "已完成"
      : status === "Processing"
        ? "解析中"
        : status === "Failed"
          ? "失败"
          : "排队中";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}
