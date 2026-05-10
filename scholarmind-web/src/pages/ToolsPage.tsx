import { Plug } from "lucide-react";

/** 工具聚合页：后续挂载 MCP 工具配置、API Key 与调用配额等 */
export function ToolsPage() {
  return (
    <div className="p-4 pb-6 lg:p-8">
      <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">工具与集成</h1>
      <p className="mt-2 max-w-2xl text-xs text-slate-600 lg:text-sm">
        此页面对接 <code className="rounded bg-slate-100 px-1">scholarmind-mcp</code>{" "}
        中的 arXiv、Semantic Scholar、联网搜索与文件写入等能力，当前为占位布局。
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:mt-6 lg:gap-4">
        {["arXiv", "Semantic Scholar", "Web Search", "File Writer"].map((name) => (
          <div
            key={name}
            className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:rounded-xl"
          >
            <Plug className="mt-0.5 h-5 w-5 text-primary" />
            <div>
              <div className="text-sm font-semibold text-slate-900">{name} MCP</div>
              <p className="mt-1 text-xs text-slate-500">未连接 · 在服务端注册后即可启用</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
