import { useState } from "react";
import clsx from "clsx";
import { ArrowLeft, Download, ExternalLink, Share2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

const TOC = ["研究背景", "核心发现", "方法对比", "实验与讨论", "结论与展望"];

type ReportTab = "report" | "refs" | "answer";

/**
 * 报告详情 + 溯源：桌面三栏；移动端顶栏（返回/分享/导出）+ 分段 Tab + 正文 + 底部引用与导出按钮。
 */
export function ReportPage() {
  const nav = useNavigate();
  const { id } = useParams();
  const [tab, setTab] = useState<ReportTab>("report");

  return (
    <div className="flex h-full min-h-0 flex-col bg-white lg:flex-row">
      {/* 桌面：目录 */}
      <nav className="hidden w-52 shrink-0 border-r border-slate-200 p-4 text-sm lg:block">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">目录</div>
        <ul className="mt-3 space-y-2 text-slate-600">
          {TOC.map((item) => (
            <li key={item}>
              <a href="#" className="block rounded px-2 py-1 hover:bg-slate-50 hover:text-primary">
                {item}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col lg:flex-row">
        {/* 移动端顶栏 */}
        <header className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2.5 lg:hidden">
          <button
            type="button"
            onClick={() => nav(-1)}
            className="rounded-full p-2 text-slate-600 hover:bg-slate-100"
            aria-label="返回"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">
            多模态基础模型综述
            <span className="ml-1 text-xs font-normal text-slate-400">#{id}</span>
          </h1>
          <button type="button" className="rounded-full p-2 text-slate-500 hover:bg-slate-100">
            <Share2 className="h-4 w-4" />
          </button>
          <button type="button" className="rounded-full p-2 text-slate-500 hover:bg-slate-100">
            <Download className="h-4 w-4" />
          </button>
        </header>

        {/* 移动端：报告 / 参考文献 / 原始回答 */}
        <div className="flex border-b border-slate-200 bg-slate-50 px-1 text-xs font-semibold lg:hidden">
          {(
            [
              ["report", "报告"],
              ["refs", "参考文献 (12)"],
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
            <p className="text-xs font-medium uppercase tracking-wide text-primary">报告</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-900">多模态基础模型方法综述（示意）</h1>
            <p className="mt-2 text-sm text-slate-500">自动生成 · 含表格与图表占位 · 段落可点击溯源</p>
          </header>

          {tab === "refs" && (
            <div className="space-y-3 lg:hidden">
              <SourceCard
                title="Attention Is All You Need"
                meta="Vaswani et al. · 2017"
                snippet="Self-attention 机制可在并行计算下捕获全局依赖关系…"
              />
              <SourceCard
                title="Swin Transformer: Hierarchical Vision Transformer"
                meta="Liu et al. · 2021"
                snippet="通过移位窗口将自注意力限制在局部区域以降低复杂度…"
              />
            </div>
          )}

          {tab === "answer" && (
            <p className="text-sm text-slate-600 lg:hidden">此处为生成前的原始模型回答（占位）。</p>
          )}

          <section
            className={clsx(
              "prose prose-slate max-w-none text-sm",
              tab !== "report" && "max-lg:hidden",
            )}
          >
              <h2 className="text-lg font-semibold text-slate-900">1. 研究背景</h2>
              <p className="text-slate-700">
                视觉 Transformer 及其变体在图像分类、检测与分割任务上取得显著进展；状态空间模型（SSM）为长序列建模提供了新的线性复杂度路径。
              </p>

              <h2 className="mt-8 text-lg font-semibold text-slate-900">2. 方法对比</h2>
              <div className="not-prose overflow-x-auto">
                <table className="mt-3 min-w-[480px] border-collapse text-xs lg:min-w-full">
                  <thead>
                    <tr className="bg-slate-50 text-left text-slate-500">
                      <th className="border border-slate-200 px-2 py-1">特性</th>
                      <th className="border border-slate-200 px-2 py-1">ViT</th>
                      <th className="border border-slate-200 px-2 py-1">Swin</th>
                      <th className="border border-slate-200 px-2 py-1">Mamba</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-800">
                    <tr>
                      <td className="border border-slate-200 px-2 py-1">注意力机制</td>
                      <td className="border border-slate-200 px-2 py-1">全局</td>
                      <td className="border border-slate-200 px-2 py-1">局部窗口</td>
                      <td className="border border-slate-200 px-2 py-1">选择性 SSM</td>
                    </tr>
                    <tr>
                      <td className="border border-slate-200 px-2 py-1">复杂度</td>
                      <td className="border border-slate-200 px-2 py-1">二次型（token）</td>
                      <td className="border border-slate-200 px-2 py-1">近似线性</td>
                      <td className="border border-slate-200 px-2 py-1">近线性</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <h2 className="mt-8 text-lg font-semibold text-slate-900">3. 性能趋势（示意）</h2>
              <div className="not-prose mt-3 flex h-40 items-end gap-2 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 pb-2 pt-4">
                {[40, 55, 48, 70, 62, 78].map((h, i) => (
                  <div key={i} className="flex flex-1 flex-col items-center gap-1">
                    <div
                      className="w-full rounded-t bg-primary/70"
                      style={{ height: `${h}%` }}
                      title={`epoch ${i + 1}`}
                    />
                    <span className="text-[10px] text-slate-400">{i + 1}</span>
                  </div>
                ))}
              </div>
          </section>

          {/* 移动端：正文 Tab 下展示引用源区块（原型底部 Sources） */}
          {tab === "report" && (
            <section className="mt-8 border-t border-slate-100 pt-6 lg:hidden">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">引用源</h3>
              <div className="mt-3 space-y-3">
                <SourceCard
                  title="Attention Is All You Need"
                  meta="Vaswani et al. · 2017"
                  snippet="Self-attention 机制可在并行计算下捕获全局依赖关系…"
                />
              </div>
            </section>
          )}

          <div className="sticky bottom-0 z-10 -mx-4 mt-8 flex gap-2 border-t border-slate-100 bg-white/95 px-4 py-3 backdrop-blur lg:static lg:mx-0 lg:mt-10 lg:border-0 lg:bg-transparent lg:px-0 lg:py-0">
            <button
              type="button"
              className="flex-1 rounded-xl border border-slate-200 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              导出 Markdown
            </button>
            <button
              type="button"
              className="flex-1 rounded-xl border border-slate-200 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              导出 PDF
            </button>
          </div>
        </article>

        {/* 桌面：右侧来源 */}
        <aside className="hidden w-80 shrink-0 flex-col bg-slate-50 lg:flex">
          <div className="flex border-b border-slate-200 bg-white text-xs font-semibold">
            <button type="button" className="flex-1 border-b-2 border-primary py-3 text-primary">
              当前页引用
            </button>
            <button type="button" className="flex-1 py-3 text-slate-500 hover:text-slate-800">
              全部来源
            </button>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4 text-xs">
            <SourceCard
              title="Attention Is All You Need"
              meta="Vaswani et al. · 2017"
              snippet="Self-attention 机制可在并行计算下捕获全局依赖关系…"
            />
            <SourceCard
              title="Swin Transformer: Hierarchical Vision Transformer"
              meta="Liu et al. · 2021"
              snippet="通过移位窗口将自注意力限制在局部区域以降低复杂度…"
            />
          </div>
        </aside>
      </div>
    </div>
  );
}

function SourceCard({ title, meta, snippet }: { title: string; meta: string; snippet: string }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <p className="mt-0.5 text-[11px] text-slate-500">{meta}</p>
        </div>
        <button
          type="button"
          className="rounded p-1 text-slate-400 hover:bg-slate-50 hover:text-primary"
          title="打开 PDF"
        >
          <ExternalLink className="h-4 w-4" />
        </button>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-slate-600">{snippet}</p>
    </article>
  );
}
