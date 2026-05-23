import { useEffect, useState } from "react";
import clsx from "clsx";
import { ArrowLeft, Download, ExternalLink, Loader2, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { DocumentPreviewDrawer } from "@/components/DocumentPreviewDrawer";
import { MarkdownPreview } from "@/components/MarkdownPreview";
import { useUi } from "@/components/ui/UiProvider";
import { getDocument, type DocumentDto } from "@/services/documents";
import {
  deleteReport,
  downloadReportMarkdown,
  fetchReport,
  type ReportCitationDto,
  type ResearchReportDto,
} from "@/services/reports";
import { stripReportMarkdown } from "@/utils/stripReportMarkdown";

type ReportTab = "report" | "refs" | "answer";

export function ReportPage() {
  const nav = useNavigate();
  const { id } = useParams();
  const { confirm, message } = useUi();
  const [tab, setTab] = useState<ReportTab>("report");
  const [report, setReport] = useState<ResearchReportDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [openingCitation, setOpeningCitation] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<DocumentDto | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setErr(null);
      try {
        const data = await fetchReport(id);
        if (!cancelled) setReport(data);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const onExportMd = async () => {
    if (!report) return;
    setExporting(true);
    try {
      await downloadReportMarkdown(report.id, report.title);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExporting(false);
    }
  };

  const onDelete = async () => {
    if (!report) return;
    const ok = await confirm({
      title: "删除报告",
      message: `确定删除「${report.title}」？此操作不可恢复。`,
      confirmText: "删除",
      type: "danger",
    });
    if (!ok) return;
    setDeleting(true);
    try {
      await deleteReport(report.id);
      message.success("报告已删除");
      nav("/reports", { replace: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  const openCitation = async (citation: ReportCitationDto) => {
    if (!report) return;
    if (!citation.item_id && !citation.document_id) {
      message.warning("该引用无法定位到知识库原文");
      return;
    }
    if (citation.item_id) {
      nav(`/documents/items/${report.kb_id}/${citation.item_id}`);
      return;
    }
    setOpeningCitation(true);
    setErr(null);
    try {
      if (citation.document_id) {
        const doc = await getDocument(report.kb_id, citation.document_id);
        setPreviewDoc(doc);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "打开原文失败");
    } finally {
      setOpeningCitation(false);
    }
  };

  const openCitationPdf = async (citation: ReportCitationDto) => {
    if (!report?.kb_id || !citation.document_id) return;
    setOpeningCitation(true);
    try {
      const doc = await getDocument(report.kb_id, citation.document_id);
      setPreviewDoc(doc);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "打开 PDF 失败");
    } finally {
      setOpeningCitation(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin" />
        加载报告…
      </div>
    );
  }

  if (err && !report) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6">
        <p className="text-sm text-red-600">{err}</p>
        <button type="button" onClick={() => nav("/reports")} className="text-sm text-primary">
          返回列表
        </button>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6">
        <p className="text-sm text-slate-600">报告不存在</p>
        <button type="button" onClick={() => nav("/reports")} className="text-sm text-primary">
          返回列表
        </button>
      </div>
    );
  }

  const outline = report.outline.length > 0 ? report.outline : ["研究背景", "核心发现", "结论与展望"];
  const refsLabel = `参考文献 (${report.citations.length})`;

  return (
    <>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-white lg:flex-row">
        <nav className="hidden w-52 shrink-0 border-r border-slate-200 p-4 text-sm lg:block">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">目录</div>
          <ul className="mt-3 space-y-2 text-slate-600">
            {outline.map((item) => (
              <li key={item}>
                <span className="block rounded px-2 py-1">{item}</span>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col lg:flex-row">
          <header className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2.5 lg:hidden">
            <button
              type="button"
              onClick={() => nav(-1)}
              className="rounded-full p-2 text-slate-600 hover:bg-slate-100"
              aria-label="返回"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <h1 className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">{report.title}</h1>
            <button
              type="button"
              disabled={exporting}
              onClick={() => void onExportMd()}
              className="rounded-full p-2 text-slate-500 hover:bg-slate-100 disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
            </button>
            <button
              type="button"
              disabled={deleting}
              onClick={() => void onDelete()}
              className="rounded-full p-2 text-red-500 hover:bg-red-50 disabled:opacity-50"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </header>

          <div className="flex border-b border-slate-200 bg-slate-50 px-1 text-xs font-semibold lg:hidden">
            {(
              [
                ["report", "报告"],
                ["refs", refsLabel],
                ["answer", "原始回答"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={
                  tab === key
                    ? "flex-1 border-b-2 border-primary py-3 text-primary"
                    : "flex-1 py-3 text-slate-500"
                }
              >
                {label}
              </button>
            ))}
          </div>

          <article className="min-h-0 flex-1 overflow-y-auto border-slate-200 p-4 lg:border-r lg:p-10">
            <header className="mb-6 hidden lg:block">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-primary">报告</p>
                  <h1 className="mt-1 text-2xl font-bold text-slate-900">{report.title}</h1>
                  {report.summary ? <p className="mt-2 text-sm text-slate-500">{report.summary}</p> : null}
                  <p className="mt-2 text-xs text-slate-400">
                    更新于 {new Date(report.updated_at).toLocaleString()} · {report.citations.length} 条引用
                  </p>
                </div>
                <button
                  type="button"
                  disabled={deleting}
                  onClick={() => void onDelete()}
                  className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                  {deleting ? "删除中…" : "删除"}
                </button>
              </div>
            </header>

            {err ? <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p> : null}

            {tab === "refs" && (
              <div className="space-y-3 lg:hidden">
                {report.citations.map((c) => (
                  <SourceCard
                    key={c.index}
                    citation={c}
                    loading={openingCitation}
                    onOpen={() => void openCitation(c)}
                    onOpenPdf={c.document_id ? () => void openCitationPdf(c) : undefined}
                  />
                ))}
              </div>
            )}

            {tab === "answer" && (
              <div className="lg:hidden">
                {report.raw_answer_md ? (
                  <MarkdownPreview markdown={report.raw_answer_md} />
                ) : (
                  <p className="text-sm text-slate-500">无保存的原始回答。</p>
                )}
              </div>
            )}

            <section className={clsx(tab !== "report" && "max-lg:hidden")}>
              <MarkdownPreview markdown={stripReportMarkdown(report.content_md)} />
            </section>

            {tab === "report" && report.citations.length > 0 && (
              <section className="mt-8 border-t border-slate-100 pt-6 lg:hidden">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">引用源</h3>
                <div className="mt-3 space-y-3">
                  {report.citations.slice(0, 3).map((c) => (
                    <SourceCard
                      key={c.index}
                      citation={c}
                      loading={openingCitation}
                      onOpen={() => void openCitation(c)}
                      onOpenPdf={c.document_id ? () => void openCitationPdf(c) : undefined}
                    />
                  ))}
                </div>
              </section>
            )}

            <div className="sticky bottom-0 z-10 -mx-4 mt-8 flex gap-2 border-t border-slate-100 bg-white/95 px-4 py-3 backdrop-blur lg:static lg:mx-0 lg:mt-10 lg:border-0 lg:bg-transparent lg:px-0 lg:py-0">
              <button
                type="button"
                disabled={exporting}
                onClick={() => void onExportMd()}
                className="flex-1 rounded-xl border border-slate-200 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                {exporting ? "导出中…" : "导出 Markdown"}
              </button>
              <button
                type="button"
                disabled
                title="PDF 导出将在后续版本提供"
                className="flex-1 rounded-xl border border-slate-200 py-2.5 text-xs font-semibold text-slate-400"
              >
                导出 PDF（即将推出）
              </button>
            </div>
          </article>

          <aside className="hidden w-80 shrink-0 flex-col bg-slate-50 lg:flex">
            <div className="border-b border-slate-200 bg-white px-4 py-3 text-xs font-semibold text-slate-700">
              引用来源 ({report.citations.length})
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto p-4 text-xs">
              {report.citations.length === 0 ? (
                <p className="text-slate-500">本次报告未绑定知识库摘录。</p>
              ) : (
                report.citations.map((c) => (
                  <SourceCard
                    key={c.index}
                    citation={c}
                    loading={openingCitation}
                    onOpen={() => void openCitation(c)}
                    onOpenPdf={c.document_id ? () => void openCitationPdf(c) : undefined}
                  />
                ))
              )}
            </div>
          </aside>
        </div>
      </div>

      {previewDoc && report ? (
        <DocumentPreviewDrawer
          kbId={report.kb_id}
          doc={previewDoc}
          onClose={() => setPreviewDoc(null)}
          onEditItems={(doc) => {
            setPreviewDoc(null);
            nav("/documents", {
              state: {
                kbId: report.kb_id,
                viewTab: "条目视图",
                itemDocFilter: { id: doc.id, name: doc.filename },
              },
            });
          }}
        />
      ) : null}
    </>
  );
}

function SourceCard({
  citation,
  loading,
  onOpen,
  onOpenPdf,
}: {
  citation: ReportCitationDto;
  loading?: boolean;
  onOpen: () => void;
  onOpenPdf?: () => void;
}) {
  const canOpen = Boolean(citation.item_id || citation.document_id);
  return (
    <article
      className={clsx(
        "rounded-xl border border-slate-200 bg-white p-3 shadow-sm",
        canOpen && "cursor-pointer hover:border-primary/40 hover:shadow-md",
      )}
      onClick={canOpen ? onOpen : undefined}
      onKeyDown={
        canOpen
          ? (e) => {
              if (e.key === "Enter") onOpen();
            }
          : undefined
      }
      role={canOpen ? "button" : undefined}
      tabIndex={canOpen ? 0 : undefined}
    >
      <div className="flex items-start gap-2">
        <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
          [{citation.index}]
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-slate-900">{citation.title}</h3>
          {citation.meta ? <p className="mt-0.5 text-[11px] text-slate-500">{citation.meta}</p> : null}
          <p className="mt-2 text-[11px] leading-relaxed text-slate-600">{citation.snippet}</p>
          {canOpen ? (
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-primary">
                {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <ExternalLink className="h-3 w-3" />}
                查看原文
              </span>
              {onOpenPdf ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenPdf();
                  }}
                  className="text-[11px] font-medium text-slate-600 underline hover:text-primary"
                >
                  打开 PDF
                </button>
              ) : null}
            </div>
          ) : (
            <p className="mt-2 text-[11px] text-slate-400">无法定位原文</p>
          )}
        </div>
      </div>
    </article>
  );
}
