import { Outlet } from "react-router-dom";
import { MobileTabBar } from "./MobileTabBar";
import { Sidebar } from "./Sidebar";

/**
 * 后台统一壳层：
 * - lg+：左侧 Sidebar + 主内容
 * - 移动端：全宽主内容 + 底部固定 TabBar（预留 safe-area 与内容 padding）
 */
export function AppShell() {
  return (
    <div className="flex h-full min-h-0 flex-col bg-slate-50 lg:flex-row">
      <Sidebar />
      <main className="min-h-0 flex-1 overflow-y-auto pb-[calc(4.25rem+env(safe-area-inset-bottom,0px))] lg:pb-0">
        <Outlet />
      </main>
      <MobileTabBar />
    </div>
  );
}
