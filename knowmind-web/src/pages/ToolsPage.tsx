import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, Download, Plug, Trash2, Upload } from "lucide-react";
import {
  downloadMcpManifest,
  downloadSkillJson,
  downloadSkillMarkdown,
  fetchSkillJson,
  type SkillExportJsonDto,
} from "@/services/knowledgeExport";
import { listKnowledgeBases, type KnowledgeBaseDto } from "@/services/knowledgeBases";
import {
  deleteCustomMcp,
  fetchMcpTools,
  importMcpJson,
  setBuiltinMcpEnabled,
  setCustomMcpEnabled,
  type BuiltinMcpTool,
  type CustomMcpTool,
} from "@/services/mcpTools";

function Toggle({
  on,
  disabled,
  onToggle,
  label,
}: {
  on: boolean;
  disabled?: boolean;
  onToggle: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={onToggle}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
        disabled ? "cursor-not-allowed opacity-40" : "cursor-pointer"
      } ${on ? "bg-primary" : "bg-slate-300"}`}
    >
      <span
        className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
          on ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function ToolCard({
  title,
  description,
  enabled,
  available,
  onToggle,
  badge,
  footer,
}: {
  title: string;
  description: string;
  enabled: boolean;
  available: boolean;
  onToggle: () => void;
  badge?: string;
  footer?: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-2xl border bg-white p-4 shadow-card lg:rounded-xl ${
        enabled ? "border-primary/40 ring-1 ring-primary/10" : "border-slate-200"
      }`}
    >
      <div className="flex items-start gap-3">
        <Plug className={`mt-0.5 h-5 w-5 shrink-0 ${enabled ? "text-primary" : "text-slate-400"}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
            <Toggle
              on={enabled}
              disabled={!available}
              onToggle={onToggle}
              label={`${title} 开关`}
            />
          </div>
          {badge ? (
            <span className="mt-1 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
              {badge}
            </span>
          ) : null}
          <p className="mt-2 text-xs leading-relaxed text-slate-500">{description}</p>
          {footer}
        </div>
      </div>
    </div>
  );
}

/** 工具聚合页：可选内置 MCP + 外部 mcp.json 导入 */
export function ToolsPage() {
  const [builtin, setBuiltin] = useState<BuiltinMcpTool[]>([]);
  const [custom, setCustom] = useState<CustomMcpTool[]>([]);
  const [kbs, setKbs] = useState<KnowledgeBaseDto[]>([]);
  const [exportKbId, setExportKbId] = useState("");
  const [skillPreview, setSkillPreview] = useState<SkillExportJsonDto | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const [data, kbList] = await Promise.all([fetchMcpTools(), listKnowledgeBases()]);
      setBuiltin(data.builtin);
      setCustom(data.custom);
      setKbs(kbList);
      setExportKbId((prev) => prev || kbList[0]?.id || "");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!exportKbId) {
      setSkillPreview(null);
      return;
    }
    void fetchSkillJson(exportKbId)
      .then(setSkillPreview)
      .catch(() => setSkillPreview(null));
  }, [exportKbId]);

  const runExport = async (kind: "skill-md" | "skill-json" | "mcp") => {
    if (!exportKbId) return;
    setExporting(kind);
    setErr(null);
    try {
      if (kind === "skill-md") await downloadSkillMarkdown(exportKbId);
      else if (kind === "skill-json") await downloadSkillJson(exportKbId);
      else await downloadMcpManifest(exportKbId);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExporting(null);
    }
  };

  useEffect(() => {
    void load();
  }, [load]);

  const toggleBuiltin = async (id: string, next: boolean) => {
    try {
      const data = await setBuiltinMcpEnabled(id, next);
      setBuiltin(data.builtin);
      setCustom(data.custom);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "更新失败");
    }
  };

  const toggleCustom = async (id: string, next: boolean) => {
    try {
      const data = await setCustomMcpEnabled(id, next);
      setBuiltin(data.builtin);
      setCustom(data.custom);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "更新失败");
    }
  };

  const handleImport = async () => {
    if (!importText.trim()) return;
    setImporting(true);
    setErr(null);
    try {
      await importMcpJson(importText.trim());
      setImportText("");
      setImportOpen(false);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导入失败");
    } finally {
      setImporting(false);
    }
  };

  const handleFilePick = (file: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      setImportText(text);
      setImportOpen(true);
    };
    reader.readAsText(file, "utf-8");
  };

  const exportTemplate = () => {
    const sample = {
      mcpServers: {
        "example-remote": {
          url: "https://example.com/mcp",
        },
      },
    };
    const blob = new Blob([JSON.stringify(sample, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mcp.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4 pb-6 lg:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">工具与集成</h1>
          <p className="mt-1 max-w-2xl text-xs text-slate-600 lg:text-sm">
            选择要在 KnowMind 中启用的能力；可粘贴带{" "}
            <code className="rounded bg-slate-100 px-1">url</code> 的远程 MCP 配置（对话页「外部 MCP」开关生效）。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setImportOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm hover:border-primary/30"
          >
            <Upload className="h-4 w-4" />
            从外部导入
          </button>
          <button
            type="button"
            onClick={exportTemplate}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm"
          >
            <Download className="h-4 w-4" />
            示例 mcp.json
          </button>
        </div>
      </div>

      {err ? (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {err}
        </p>
      ) : null}

      {importOpen ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 lg:rounded-xl">
          <p className="text-xs font-medium text-slate-700">
            粘贴 mcp.json（仅导入含 <code className="rounded bg-slate-200 px-0.5">url</code> 的远程服务；本地 command 配置会跳过）
          </p>
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            rows={8}
            className="mt-2 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 font-mono text-xs text-slate-800 outline-none focus:border-primary"
            placeholder='{"mcpServers": { "my-remote": { "url": "https://example.com/mcp" } } }'
          />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={importing || !importText.trim()}
              onClick={() => void handleImport()}
              className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
            >
              {importing ? "导入中…" : "确认导入"}
            </button>
            <button
              type="button"
              className="text-xs text-slate-500 underline"
              onClick={() => fileRef.current?.click()}
            >
              或选择本地文件
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".json,application/json"
              className="hidden"
              onChange={(e) => handleFilePick(e.target.files?.[0] ?? null)}
            />
          </div>
        </div>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-slate-500">加载中…</p>
      ) : (
        <>
          <section className="mt-6 rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/5 to-white p-4 shadow-card lg:rounded-xl lg:p-5">
            <div className="flex flex-wrap items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                <BookOpen className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-sm font-semibold text-slate-900">Skill / MCP 导出</h2>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">
                  将知识库检索能力导出为 Cursor Skill 或{" "}
                  <code className="rounded bg-white/80 px-1">mcp.json</code> 片段；MCP 配置内含{" "}
                  <code className="rounded bg-white/80 px-1">search_kb</code> 工具，需填入 JWT。
                </p>
              </div>
            </div>

            {kbs.length === 0 ? (
              <p className="mt-4 text-xs text-slate-500">请先创建知识库后再导出。</p>
            ) : (
              <>
                <div className="mt-4 flex flex-wrap items-end gap-3">
                  <label className="flex min-w-[12rem] flex-1 flex-col gap-1 text-xs text-slate-600">
                    选择知识库
                    <select
                      value={exportKbId}
                      onChange={(e) => setExportKbId(e.target.value)}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800"
                    >
                      {kbs.map((kb) => (
                        <option key={kb.id} value={kb.id}>
                          {kb.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={!exportKbId || exporting !== null}
                      onClick={() => void runExport("skill-md")}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white hover:bg-primary-hover disabled:opacity-50"
                    >
                      <Download className="h-3.5 w-3.5" />
                      {exporting === "skill-md" ? "导出中…" : "SKILL.md"}
                    </button>
                    <button
                      type="button"
                      disabled={!exportKbId || exporting !== null}
                      onClick={() => void runExport("skill-json")}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      <Download className="h-3.5 w-3.5" />
                      {exporting === "skill-json" ? "导出中…" : "Skill JSON"}
                    </button>
                    <button
                      type="button"
                      disabled={!exportKbId || exporting !== null}
                      onClick={() => void runExport("mcp")}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      <Download className="h-3.5 w-3.5" />
                      {exporting === "mcp" ? "导出中…" : "mcp.json"}
                    </button>
                  </div>
                </div>

                {skillPreview ? (
                  <div className="mt-4 rounded-xl border border-slate-200/80 bg-white/90 p-3">
                    <p className="text-[11px] font-medium text-slate-500">预览（JSON）</p>
                    <pre className="mt-2 max-h-40 overflow-auto font-mono text-[11px] leading-relaxed text-slate-700">
                      {JSON.stringify(
                        {
                          name: skillPreview.name,
                          kb_id: skillPreview.kb_id,
                          kb_name: skillPreview.kb_name,
                          endpoint: skillPreview.endpoint,
                        },
                        null,
                        2,
                      )}
                    </pre>
                    <p className="mt-2 text-[11px] text-slate-500">
                      MCP 导出后请将 <code className="rounded bg-slate-100 px-1">KNOWMIND_ACCESS_TOKEN</code>{" "}
                      替换为登录 Token，并将配置合并到 Cursor 的 mcp.json。
                    </p>
                  </div>
                ) : null}
              </>
            )}
          </section>

          <h2 className="mt-8 text-sm font-semibold text-slate-800">内置工具</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:gap-4">
            {builtin.map((t) => (
              <ToolCard
                key={t.id}
                title={`${t.name} MCP`}
                description={t.description}
                enabled={t.enabled}
                available={t.available}
                onToggle={() => void toggleBuiltin(t.id, !t.enabled)}
                badge={t.available ? (t.enabled ? "已启用" : "已关闭") : "即将接入"}
              />
            ))}
          </div>

          <h2 className="mt-8 text-sm font-semibold text-slate-800">外部导入</h2>
          <p className="mt-1 text-xs text-slate-500">
            仅支持远程 URL 型 MCP；在对话页打开「外部 MCP」后，模型可调用此处已启用服务的工具。
          </p>
          {custom.length === 0 ? (
            <p className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-xs text-slate-500">
              暂无外部 MCP，点击「从外部导入」粘贴配置
            </p>
          ) : (
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:gap-4">
              {custom.map((t) => (
                <ToolCard
                  key={t.id}
                  title={t.name}
                  description={
                    t.config.command
                      ? `command: ${t.config.command} ${(t.config.args ?? []).join(" ")}`.trim()
                      : t.config.url
                        ? `url: ${t.config.url}`
                        : t.description
                  }
                  enabled={t.enabled}
                  available
                  onToggle={() => void toggleCustom(t.id, !t.enabled)}
                  badge={t.enabled ? "已启用" : "已关闭"}
                  footer={
                    <button
                      type="button"
                      onClick={() => void deleteCustomMcp(t.id).then(load)}
                      className="mt-3 inline-flex items-center gap-1 text-xs text-red-600 hover:underline"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      删除
                    </button>
                  }
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
