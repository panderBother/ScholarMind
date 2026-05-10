import clsx from "clsx";
import { BookOpen, FileText, LayoutDashboard, MessageSquare, User } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

/**
 * 移动端底部导航（原型 5 Tab）：对话 / 知识库 / 文献 / 报告 / 我的。
 * 大屏隐藏，由左侧 Sidebar 承担主导航；使用 safe-area 适配刘海屏。
 */
const TABS = [
  { to: "/chat", label: "对话", icon: MessageSquare },
  { to: "/knowledge-bases", label: "知识库", icon: BookOpen },
  { to: "/documents", label: "文献", icon: FileText },
  { to: "/reports", label: "报告", icon: LayoutDashboard },
  { to: "/settings", label: "我的", icon: User },
] as const;

export function MobileTabBar() {
  const { pathname } = useLocation();

  const isReports = pathname === "/reports" || pathname.startsWith("/reports/");

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur-md lg:hidden"
      style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
      aria-label="主导航"
    >
      <ul className="mx-auto flex max-w-lg items-stretch justify-around px-1 pt-1">
        {TABS.map((tab) => {
          const active =
            tab.to === "/reports"
              ? isReports
              : pathname === tab.to;

          return (
            <li key={tab.to} className="flex min-w-0 flex-1 justify-center">
              <NavLink
                to={tab.to}
                className={clsx(
                  "flex w-full max-w-[4.5rem] flex-col items-center gap-0.5 rounded-lg py-1.5 text-[10px] font-medium transition-colors",
                  active ? "text-primary" : "text-slate-500 hover:text-slate-800",
                )}
              >
                <tab.icon className="h-5 w-5 shrink-0" strokeWidth={active ? 2.25 : 1.75} />
                <span className="truncate">{tab.label}</span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
